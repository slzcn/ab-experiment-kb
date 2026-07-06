#!/usr/bin/env python3
# 管理后台本地服务：给 admin.html 提供「批量上传文档→转码入库」等需要本机能力的接口。
#
# 为什么要本地后台：解析 PPT/Word/PDF 二进制、抽图存盘、把图片 git push 到仓库
# （让 raw.githubusercontent 的图片 URL 生效），这些都无法在公开静态站上做。
# 文章增删改 / 分类配置 是纯数据操作，admin.html 直连 Supabase 即可，不经过这里。
#
# 用法：
#   cd ~/ab-experiment-kb
#   python3 admin_server.py            # 图片存本地 assets/，不推 GitHub（本地预览转码效果）
#   python3 admin_server.py --push     # 转码后把图片 git push 到仓库（线上图片 URL 生效）★推荐
#
# 然后浏览器打开 http://localhost:8799/admin.html
#
# 安全：只在本机 127.0.0.1 监听，不对外。公开站没有这个服务，也就没有上传转码入口。

import json, os, re, sys, io, subprocess, datetime, time
import http.server, socketserver

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
PORT   = 8799
PUSH   = "--push" in sys.argv

sys.path.insert(0, HERE)
import doc_to_md  # 同目录转码器

# Supabase（与前端同一套 publishable key，可写）
_cfg = json.load(open(os.path.join(HERE, "sb_config.json"), encoding="utf-8"))
SB_URL, SB_KEY = _cfg["url"], _cfg["key"]

ALLOWED_EXT = {".pptx", ".docx", ".pdf", ".ppt", ".doc", ".xlsx", ".xls",
               ".csv", ".txt", ".md", ".markdown", ".rtf", ".html", ".htm"}


def _slug_title(title, cat):
    safe = re.sub(r'[\\/:*?"<>|\s]+', "-", (title or "").strip()).strip("-")[:32] or "doc"
    return f"{cat}-{safe}"


def _plain_text(md):
    md = md or ""
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)      # 去图片
    md = re.sub(r"```[\s\S]*?```", "", md)             # 去代码块
    md = re.sub(r"<[^>]+>", "", md)
    md = re.sub(r"[#>*`|\-]{1,}", " ", md)
    return re.sub(r"\s+", " ", md).strip()


def _git(*args):
    return subprocess.run(["git", "-C", HERE, *args],
                          capture_output=True, text=True,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def _push_assets(files, note):
    """把新抽出的图片 git add + commit + push（--push 模式下）。返回日志。"""
    if not files:
        return "无图片，跳过推送"
    if not PUSH:
        return f"已存本地 assets/（{len(files)} 张），未推送（加 --push 可推线上）"
    _git("add", "assets")
    r = _git("commit", "-m", f"上传文档配图：{note}")
    if "nothing to commit" in (r.stdout + r.stderr):
        return "图片已在仓库，无需重复提交"
    p = _git("push", "origin", "main")
    if p.returncode != 0:
        return f"⚠️ 图片 push 失败：{(p.stderr or p.stdout)[-200:]}（图片已在本地，稍后可手动 push）"
    return f"✅ {len(files)} 张图片已推送到仓库"


def _sb_insert(row):
    import urllib.request
    body = json.dumps(row, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        SB_URL + "/rest/v1/ab_articles", data=body, method="POST",
        headers={"apikey": SB_KEY, "Authorization": "Bearer " + SB_KEY,
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    with urllib.request.urlopen(req) as resp:
        if resp.status not in (200, 201, 204):
            raise RuntimeError(f"数据库写入 HTTP {resp.status}")


# ---------- 极简 multipart/form-data 解析（Py3.13+ 移除了 cgi 模块）----------
def _parse_multipart(body, boundary):
    parts = body.split(b"--" + boundary)
    fields, files = {}, []
    for part in parts:
        if not part or part in (b"--\r\n", b"--"):
            continue
        if b"\r\n\r\n" not in part:
            continue
        head, data = part.split(b"\r\n\r\n", 1)
        data = data.rstrip(b"\r\n")
        head_s = head.decode("utf-8", "replace")
        mname = re.search(r'name="([^"]*)"', head_s)
        mfile = re.search(r'filename="([^"]*)"', head_s)
        if not mname:
            continue
        name = mname.group(1)
        if mfile:
            files.append({"field": name, "filename": mfile.group(1), "data": data})
        else:
            fields[name] = data.decode("utf-8", "replace").strip()
    return fields, files


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/health":
            return self._json(200, {"ok": True, "push": PUSH,
                                    "formats": sorted(ALLOWED_EXT)})
        if p in ("/", "/index.html"):
            self.path = "/dev.html"      # 根路径给主站开发模板
        return super().do_GET()

    def do_POST(self):
        p = self.path.split("?")[0]
        if p == "/api/upload":
            return self._upload()
        return self._json(404, {"ok": False, "error": "not found"})

    # 批量上传文档 → 逐个转码 → 图片推仓库 → 文章入库
    def _upload(self):
        try:
            ctype = self.headers.get("Content-Type", "")
            m = re.search(r"boundary=(.+)$", ctype)
            if not m:
                return self._json(400, {"ok": False, "error": "需要 multipart 上传"})
            boundary = m.group(1).strip('"').encode()
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            fields, files = _parse_multipart(body, boundary)
            default_cat = (fields.get("cat") or "misc").strip()
            if not files:
                return self._json(400, {"ok": False, "error": "未收到文件"})

            results, all_imgs = [], []
            for f in files:
                fn = f["filename"]
                ext = os.path.splitext(fn)[1].lower()
                title = os.path.splitext(os.path.basename(fn))[0]
                if ext not in ALLOWED_EXT:
                    results.append({"file": fn, "ok": False, "error": f"不支持的格式 {ext}"})
                    continue
                # 落地临时文件供转码器读取
                tmp = os.path.join("/tmp", f"abkb_{int(time.time()*1000)}_{re.sub(r'[^A-Za-z0-9._-]','_',fn)}")
                with open(tmp, "wb") as w:
                    w.write(f["data"])
                try:
                    slug = _slug_title(title, default_cat)
                    conv = doc_to_md.convert(tmp, slug=slug, title=title)
                    md = conv["md"]
                    if not md.strip():
                        results.append({"file": fn, "ok": False, "error": "未抽取到内容"})
                        continue
                    today = datetime.date.today().isoformat()
                    doc_id = 910000000 + int(time.time() * 1000) % 90000000
                    _sb_insert({
                        "doc_id": doc_id, "title": title, "cat": default_cat,
                        "keywords": (title + " 上传文档").strip(),
                        "md": md, "body_text": _plain_text(md),
                        "updated": today, "source_url": "", "is_internal": True,
                    })
                    all_imgs += conv["images"]
                    results.append({"file": fn, "ok": True, "title": title,
                                    "doc_id": doc_id, "images": len(conv["images"]),
                                    "chars": len(md)})
                    time.sleep(0.002)   # 保证 doc_id 唯一
                except Exception as e:
                    results.append({"file": fn, "ok": False, "error": str(e)})
                finally:
                    try: os.remove(tmp)
                    except Exception: pass

            push_log = _push_assets(all_imgs, f"{len([r for r in results if r.get('ok')])} 篇文档")
            ok_n = len([r for r in results if r.get("ok")])
            return self._json(200, {
                "ok": ok_n > 0, "count": ok_n, "total": len(files),
                "images": len(all_imgs), "push_log": push_log,
                "results": results,
                "msg": f"成功转码入库 {ok_n}/{len(files)} 篇，抽出 {len(all_imgs)} 张图。"
                       + ("约十几秒后线上自动同步。" if PUSH else "（本地模式，图片未推线上）"),
            })
        except Exception as e:
            return self._json(500, {"ok": False, "error": str(e)})


if __name__ == "__main__":
    os.chdir(HERE)
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        tip = "图片推送 GitHub（线上生效）" if PUSH else "图片仅存本地（不推线上）"
        print(f"🛠  管理后台服务已启动（{tip}）")
        print(f"   打开：http://localhost:{PORT}/admin.html")
        print(f"   批量上传文档 → 自动转码成带图文章入库。Ctrl+C 停止。")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")
