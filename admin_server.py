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

import os, sys, re, json, tempfile, datetime, time, threading, queue
import http.server

HERE   = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
PORT   = 8799
PUSH   = "--push" in sys.argv

sys.path.insert(0, HERE)
import doc_to_md                       # 同目录转码器
from kb_common import plain_text, slugify, git, Supabase

SB = Supabase()                        # 从 sb_config.json 读 url+key，统一错误处理

ALLOWED_EXT = {".pptx", ".docx", ".pdf", ".ppt", ".doc", ".xlsx", ".xls",
               ".csv", ".txt", ".md", ".markdown", ".rtf", ".html", ".htm"}


def _push_assets(files, note):
    """把新抽出的图片 git add + commit + push（--push 模式下）。返回日志。"""
    if not files:
        return "无图片，跳过推送"
    if not PUSH:
        return f"已存本地 assets/（{len(files)} 张），未推送（加 --push 可推线上）"
    git("add", "assets")
    r = git("commit", "-m", f"上传文档配图：{note}")
    if "nothing to commit" in (r.stdout + r.stderr):
        return "图片已在仓库，无需重复提交"
    p = git("push", "origin", "main")
    if p.returncode != 0:
        return f"图片 push 失败：{(p.stderr or p.stdout)[-200:]}（图片已在本地，稍后可手动 push）"
    return f"{len(files)} 张图片已推送到仓库"


# ============ 异步任务队列：上传秒回，后台线程逐个转码入库 ============
# 上传接口只做“落地临时文件 + 入队”这点轻活，立即返回 job_id；真正耗时的
# 解析/抽图/入库/推图在后台 worker 线程里跑，前端轮询 /api/upload/status 看进度。
JOBS = {}                       # job_id -> {items:[...], created, done}
JOBS_LOCK = threading.Lock()
WORK_Q = queue.Queue()          # 队列元素：(job_id, item_index)


def _new_job(entries):
    """entries: [{filename, tmp, ext, title}]，返回 job dict。"""
    jid = f"job{int(time.time()*1000)}{len(JOBS)}"
    items = [{
        "idx": i, "file": e["filename"], "status": "queued",
        "title": e["title"], "images": 0, "chars": 0, "error": "",
        "tmp": e["tmp"], "ext": e["ext"],
    } for i, e in enumerate(entries)]
    job = {"id": jid, "items": items, "created": time.time(),
           "done": False, "push_log": "", "cat": None}
    with JOBS_LOCK:
        JOBS[jid] = job
    return job


def _job_public(job):
    """给前端的精简视图（去掉 tmp 等内部字段）。"""
    return {
        "id": job["id"], "done": job["done"], "push_log": job["push_log"],
        "items": [{k: it[k] for k in ("idx", "file", "status", "title", "images", "chars", "error")}
                  for it in job["items"]],
    }


def _worker():
    """单后台线程：从队列取任务，串行转码入库。串行是有意的——
    避免多个 git/DB 写并发，也让 doc_id 生成简单可控。"""
    while True:
        jid, i = WORK_Q.get()
        try:
            _process_item(jid, i)
        except Exception as e:
            with JOBS_LOCK:
                it = JOBS[jid]["items"][i]
                it["status"] = "error"; it["error"] = str(e)
        finally:
            _maybe_finish_job(jid)
            WORK_Q.task_done()


def _process_item(jid, i):
    job = JOBS[jid]
    it = job["items"][i]
    with JOBS_LOCK:
        it["status"] = "processing"
    ext, tmp, title, cat = it["ext"], it["tmp"], it["title"], job["cat"]
    if ext not in ALLOWED_EXT:
        with JOBS_LOCK:
            it["status"] = "error"; it["error"] = f"不支持的格式 {ext}"
        return
    try:
        conv = doc_to_md.convert(tmp, slug=slugify(f"{cat}-{title}"), title=title)
        md = conv["md"]
        if not md.strip():
            with JOBS_LOCK:
                it["status"] = "error"; it["error"] = "未抽取到内容"
            return
        doc_id = 910000000 + int(time.time() * 1000) % 90000000
        SB.insert("ab_articles", {
            "doc_id": doc_id, "title": title, "cat": cat,
            "keywords": (title + " 上传文档").strip(),
            "md": md, "body_text": plain_text(md),
            "updated": datetime.date.today().isoformat(),
            "source_url": "", "is_internal": True,
        }, upsert_on="doc_id")
        with JOBS_LOCK:
            it["status"] = "done"; it["doc_id"] = doc_id
            it["images"] = len(conv["images"]); it["chars"] = len(md)
            job.setdefault("_imgs", []).extend(conv["images"])
    finally:
        try: os.remove(tmp)
        except Exception: pass


def _maybe_finish_job(jid):
    """一个 job 的所有 item 处理完后：推图片、标记 done。"""
    with JOBS_LOCK:
        job = JOBS[jid]
        if job["done"]:
            return
        if any(it["status"] in ("queued", "processing") for it in job["items"]):
            return
        imgs = job.get("_imgs", [])
        ok_n = sum(1 for it in job["items"] if it["status"] == "done")
    # 推图片放锁外（git 可能慢）
    push_log = _push_assets(imgs, f"{ok_n} 篇文档")
    with JOBS_LOCK:
        job["push_log"] = push_log
        job["done"] = True


# 起后台 worker（daemon：主进程退出即随之结束）
threading.Thread(target=_worker, daemon=True).start()


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

    # 所有响应都带上 CORS，这样从 github.io 线上页 / 双击本地文件打开时，
    # 也能跨源访问本机后台（localhost 是浏览器信任源，https 页面也允许）。
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

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
        if p == "/api/upload/status":
            return self._upload_status()
        if p in ("/", "/index.html"):
            self.path = "/dev.html"      # 根路径给主站开发模板
        return super().do_GET()

    def do_POST(self):
        p = self.path.split("?")[0]
        if p == "/api/upload":
            return self._upload()
        return self._json(404, {"ok": False, "error": "not found"})

    # 批量上传：只落地临时文件 + 入队，立即返回 job（“丝滑成功”）；
    # 后台 worker 线程再慢慢转码入库，前端轮询 status 看进度。
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

            # 快速落地每个上传文件到临时路径（仅 IO，不解析）
            entries = []
            for f in files:
                fn = f["filename"]
                ext = os.path.splitext(fn)[1].lower()
                fd, tmp = tempfile.mkstemp(prefix="abkb_", suffix=ext)
                with os.fdopen(fd, "wb") as w:
                    w.write(f["data"])
                entries.append({"filename": fn, "tmp": tmp, "ext": ext,
                                "title": os.path.splitext(os.path.basename(fn))[0]})

            job = _new_job(entries)
            job["cat"] = default_cat
            for it in job["items"]:              # 入队交给后台 worker
                WORK_Q.put((job["id"], it["idx"]))

            # 秒回：告诉前端已收下，去轮询进度
            return self._json(200, {"ok": True, "job": job["id"],
                                    "total": len(entries),
                                    "status": _job_public(job)})
        except Exception as e:
            return self._json(500, {"ok": False, "error": str(e)})

    def _upload_status(self):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        jid = (q.get("job") or [""])[0]
        with JOBS_LOCK:
            job = JOBS.get(jid)
            pub = _job_public(job) if job else None
        if not pub:
            return self._json(404, {"ok": False, "error": "job 不存在"})
        return self._json(200, {"ok": True, "status": pub})


class _Server(http.server.ThreadingHTTPServer):
    # 多线程：上传在读大 body 时，状态轮询仍能被响应
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    os.chdir(HERE)
    url = f"http://localhost:{PORT}/admin.html"
    with _Server(("127.0.0.1", PORT), Handler) as httpd:
        tip = "图片推送 GitHub（线上生效）" if PUSH else "图片仅存本地（不推线上）"
        print(f"管理后台服务已启动（{tip}）")
        print(f"   请从这个地址访问（务必用这个，才能上传转码）：{url}")
        print(f"   批量上传文档 → 上传秒回，后台转码成带图文章入库。Ctrl+C 停止。")
        # 自动打开浏览器到正确地址，省去“该开哪个网址”的困惑
        try:
            import webbrowser, threading
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")
