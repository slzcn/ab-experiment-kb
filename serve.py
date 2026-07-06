#!/usr/bin/env python3
# 本地发布服务：在你自己的电脑上打开知识库，点「提交并发布」即可直接入库，无需下载文件。
#
# 用法：
#   cd ~/ab-experiment-kb
#   python3 serve.py            # 提交后只入本地库+打包（本地预览）
#   python3 serve.py --push     # 提交后自动推送 GitHub Pages（线上一步更新）
#   python3 serve.py --push --miaoda   # 再顺带更新飞书妙搭
#
# 然后浏览器打开 http://localhost:8799 ，写文章 → 点「提交并发布」。
#
# 安全说明：这个写入接口只在本机 localhost 监听，不对外。线上公开版（GitHub Pages/妙搭）
# 没有这个服务，编辑器会自动回退成「导出 .md」，任何人都无法直接改你的库。

import json, os, re, sys, subprocess, datetime, http.server, socketserver, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ART  = os.path.join(HERE, "articles")
PORT = 8799
PUSH   = "--push" in sys.argv
MIAODA = "--miaoda" in sys.argv

def slug(title, cat):
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("_")[:40] or "article"
    return f"{cat}_{safe}.md"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, *a):  # 静音默认日志
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # 健康探测：前端据此判断“有后端 → 可直接提交”
        if self.path.split("?")[0] == "/api/health":
            return self._json(200, {"ok": True, "push": PUSH, "miaoda": MIAODA})
        # 根路径返回开发模板（读同目录 kb.json，改完刷新即见）
        if self.path in ("/", "/index.html"):
            self.path = "/dev.html"
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/publish":
            return self._json(404, {"ok": False, "error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            title = (data.get("title") or "").strip()
            cat   = (data.get("cat") or "misc").strip()
            kw    = (data.get("keywords") or "").strip()
            md    = (data.get("md") or "").strip()
            if not title:  return self._json(400, {"ok": False, "error": "标题不能为空"})
            if not md:     return self._json(400, {"ok": False, "error": "正文不能为空"})

            os.makedirs(ART, exist_ok=True)
            fn = slug(title, cat)
            today = datetime.date.today().isoformat()
            front = f"---\ntitle: {title}\ncat: {cat}\nkeywords: {kw}\ndate: {today}\n---\n\n"
            with open(os.path.join(ART, fn), "w", encoding="utf-8") as f:
                f.write(front + md)

            # 跑 publish.py 合并+打包（带上服务启动时的 --push/--miaoda）
            cmd = [sys.executable, os.path.join(HERE, "publish.py")]
            if PUSH:   cmd.append("--push")
            if MIAODA: cmd.append("--miaoda")
            r = subprocess.run(cmd, capture_output=True, text=True)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode != 0:
                return self._json(500, {"ok": False, "error": "发布脚本出错", "log": out[-800:]})
            return self._json(200, {
                "ok": True, "file": fn, "pushed": PUSH, "miaoda": MIAODA,
                "msg": f"《{title}》已入库" + ("，并推送线上" if PUSH else "（本地）"),
                "log": out[-800:],
            })
        except Exception as e:
            return self._json(500, {"ok": False, "error": str(e)})

if __name__ == "__main__":
    os.chdir(HERE)
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        tip = "推送线上" if PUSH else "仅本地"
        print(f"📝 本地发布服务已启动（{tip}）")
        print(f"   浏览器打开：http://localhost:{PORT}")
        print(f"   写文章 → 点「提交并发布」即可直接入库，无需下载文件。Ctrl+C 停止。")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止。")
