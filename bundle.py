#!/usr/bin/env python3
# 把 dev.html + kb.json + marked.js 打包成单文件 standalone，并生成每篇文章的静态页。
# 输出：
#   - index.html      （仓库根，GitHub Pages）——★不内嵌全量正文★，首屏只 fetch
#     同目录的 kb_index.json（轻量列表），正文点开时按需拉 kb_docs.json。
#   - dist/index.html （妙搭发布 / 本地双击）——必须内嵌全量：静态托管会把子路径
#     fallback 到 index.html，拿不到独立 kb.json，只能靠内嵌数据离线自足。
#   - a/<id>.html     （每篇一个真实静态页）——就是完整站本身（侧栏+搜索），打开即
#     直达该篇；注入 DATA_BASE='../' 让数据从根目录取、INIT_DOC 指定打开哪篇、
#     并把标题/摘要写进 <head> 供 SEO/分享预览。真实文件 → 可被搜索引擎单独收录。
import os, json, html as _html, re

HERE = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HERE,"dev.html"), encoding="utf-8").read()
kb   = open(os.path.join(HERE,"kb.json"), encoding="utf-8").read()
marked = open(os.path.join(HERE,"marked.min.js"), encoding="utf-8").read()
SITE = "https://slzcn.github.io/ab-experiment-kb"

# 用本地 marked 替换 CDN 引用（内网可用、更快、离线可打开）——都要
html = html.replace(
    '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>',
    f'<script>{marked}</script>'
)

# 1) 仓库根 index.html（GitHub Pages）：占位符替换成空串，不内嵌全量数据。
root_html = html.replace("<!--KB_DATA-->", "")
root_out = os.path.join(HERE, "index.html")
open(root_out, "w", encoding="utf-8").write(root_html)

# 2) dist/index.html（妙搭/本地双击）：
#    - 注入 window.DATA_BASE 指向 GitHub Pages，让妙搭页运行时 fetch 那份"数据库变化即自动刷新"的
#      kb_*.json —— 后台上下线/删除文章后，妙搭首页也能约 1 分钟内自动同步（不再需要手动 --miaoda）。
#    - 仍内嵌全量正文作离线兜底：boot() 的 fetch 链全部失败（断网/Pages 不可达）时回退到内嵌数据，不白屏。
#    妙搭静态托管会把子路径 fallback 到 index.html，本身取不到独立 kb.json，DATA_BASE 指远程正好补上。
kb_safe = kb.replace("</", "<\\/")   # 转义 </script 防止提前闭合
# DATA_BASE 末尾带 /；Pages 的 json 有 CDN 缓存(max-age=600)，boot()/按需加载里会自动 append ?v= 破缓存。
dist_data_base = '<script>window.DATA_BASE="%s/";</script>' % SITE
dist_html = html.replace("<!--KB_DATA-->", kb_safe).replace("</head>", dist_data_base + "\n</head>", 1)
os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
open(os.path.join(HERE, "dist", "index.html"), "w", encoding="utf-8").write(dist_html)

# 3) 每篇文章静态页 a/<id>.html —— 复用根 index.html（完整站），注入：
#    <base>? 不用——改用 window.DATA_BASE='../' 让 fetch 回根目录取数据（不影响 hash 路由）；
#    window.INIT_DOC 指定打开哪篇；<head> 里补该篇 title/description/canonical/og 供 SEO。
kbj = json.loads(kb)
docs = kbj.get("docs", [])
ART_DIR = os.path.join(HERE, "a")
# 全量重建：清掉旧的 a/*.html（下线/删除的文章静态页随之消失）
if os.path.isdir(ART_DIR):
    for fn in os.listdir(ART_DIR):
        if fn.endswith(".html"): os.remove(os.path.join(ART_DIR, fn))
else:
    os.makedirs(ART_DIR, exist_ok=True)

def esc(s): return _html.escape(str(s or ""), quote=True)

for d in docs:
    did = d.get("id");
    if did is None: continue
    title = d.get("title", "")
    desc = re.sub(r"\s+", " ", (d.get("text", "") or "")[:110]).strip()
    head_inject = (
        f'<title>{esc(title)} · A/B 实验知识库</title>\n'
        f'<meta name="description" content="{esc(desc)}">\n'
        f'<link rel="canonical" href="{SITE}/a/{did}.html">\n'
        f'<meta property="og:title" content="{esc(title)}">\n'
        f'<meta property="og:description" content="{esc(desc)}">\n'
        f'<meta property="og:type" content="article">\n'
        f'<meta property="og:url" content="{SITE}/a/{did}.html">\n'
        f'<script>window.DATA_BASE="../";window.INIT_DOC={int(did)};</script>'
    )
    # 用注入块替换掉根模板里的 <title>...</title>（其余 head/CSS/JS 原样复用）
    page = re.sub(r"<title>.*?</title>", head_inject, root_html, count=1, flags=re.S)
    open(os.path.join(ART_DIR, f"{did}.html"), "w", encoding="utf-8").write(page)

print(f"✅ 打包完成: index.html ({os.path.getsize(root_out)//1024} KB) "
      f"+ dist/index.html ({os.path.getsize(os.path.join(HERE,'dist','index.html'))//1024} KB, 妙搭内嵌) "
      f"+ a/*.html ({len(docs)} 篇文章静态页)")
