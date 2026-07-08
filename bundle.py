#!/usr/bin/env python3
# 把 dev.html 模板 + 共享 app.css/app.js/marked.min.js + kb.json 打包成产物:
#   - index.html      (仓库根, GitHub Pages)  → 外链引用共享模板文件, 不内嵌全量正文,
#     首屏 fetch 同目录 kb_index.json (轻量列表), 正文点开时按需拉 kb_docs.json。
#   - a/<id>.html     (每篇一个真实静态页)   → 外链引用 ../ 上的共享模板文件,
#     head 注入 SEO 元数据 + window.INIT_DOC + window.INIT_MD (本篇正文内嵌),
#     直达打开秒渲染无需二次 fetch, SEO 能收录全文。
#   - dist/index.html (妙搭发布 / 本地双击)  → 占位符替换为内嵌全量:静态托管子路径 fallback
#     到 index.html 拿不到独立文件, 只能靠内嵌自足。
#
# 【形态二】a/*.html 只装「这篇文章的东西」(元数据 + 本篇正文),模板样式/逻辑走共享外链;
# 改模板只动 dev.html/app.css/app.js 三个文件, 205 篇静态页无变化, 秒部署。
import os, json, html as _html, re

HERE = os.path.dirname(os.path.abspath(__file__))
tpl    = open(os.path.join(HERE,"dev.html"), encoding="utf-8").read()
kb     = open(os.path.join(HERE,"kb.json"), encoding="utf-8").read()
app_css= open(os.path.join(HERE,"app.css"), encoding="utf-8").read()
app_js = open(os.path.join(HERE,"app.js"), encoding="utf-8").read()
marked = open(os.path.join(HERE,"marked.min.js"), encoding="utf-8").read()
SITE = "https://slzcn.github.io/ab-experiment-kb"


def render(base_prefix, kb_data_block, extra_head_inject=""):
    """按占位符渲染模板。
      base_prefix: 共享文件的相对前缀 ('' 表根目录; '../' 表 a/ 子目录)
      kb_data_block: <script id=kbdata> 内容 (根/文章页留空; dist 内嵌全量 kb)
      extra_head_inject: 追加到 <title> 之后 </head> 之前的额外 head 内容
                        (仅文章页用, 含 SEO meta + INIT_DOC + INIT_MD 脚本)
    对占位符替换:
      <!--APP_CSS-->    → <link rel=stylesheet href=base_prefix+app.css>
      <!--MARKED_JS-->  → <script src=base_prefix+marked.min.js></script>
      <!--APP_JS-->     → <script src=base_prefix+app.js></script>
      <!--KB_DATA-->    → kb_data_block
    """
    out = tpl
    out = out.replace("<!--APP_CSS-->", f'<link rel="stylesheet" href="{base_prefix}app.css">')
    out = out.replace("<!--MARKED_JS-->", f'<script src="{base_prefix}marked.min.js"></script>')
    out = out.replace("<!--APP_JS-->", f'<script src="{base_prefix}app.js"></script>')
    out = out.replace("<!--KB_DATA-->", kb_data_block)
    if extra_head_inject:
        # 注入到 </head> 之前
        out = out.replace("</head>", extra_head_inject + "\n</head>", 1)
    return out


def render_inline(kb_data_block, data_base_script=""):
    """dist 用: 占位符替换成内嵌全部内容 (妙搭静态托管取不到外链, 必须内嵌)。"""
    out = tpl
    out = out.replace("<!--APP_CSS-->", f'<style>{app_css}</style>')
    out = out.replace("<!--MARKED_JS-->", f'<script>{marked}</script>')
    out = out.replace("<!--APP_JS-->", f'<script>{app_js}</script>')
    out = out.replace("<!--KB_DATA-->", kb_data_block)
    if data_base_script:
        out = out.replace("</head>", data_base_script + "\n</head>", 1)
    return out


# --- 1) 仓库根 index.html (GitHub Pages) ---
root_html = render(base_prefix="", kb_data_block="")
root_out = os.path.join(HERE, "index.html")
open(root_out, "w", encoding="utf-8").write(root_html)

# --- 2) dist/index.html (妙搭内嵌 + 远程 DATA_BASE 数据同步) ---
kb_safe = kb.replace("</", "<\\/")  # 转义 </script 防止提前闭合
dist_data_base = '<script>window.DATA_BASE="%s/";</script>' % SITE
dist_html = render_inline(kb_data_block=kb_safe, data_base_script=dist_data_base)
os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
open(os.path.join(HERE, "dist", "index.html"), "w", encoding="utf-8").write(dist_html)

# --- 3) 每篇文章静态页 a/<id>.html ---
kbj = json.loads(kb)
docs = kbj.get("docs", [])
# 本篇正文从 kb_docs.json 读 (kb.json 里也有, 但 kb_docs.json 是权威的按 id 索引)
docs_map_path = os.path.join(HERE, "kb_docs.json")
if os.path.exists(docs_map_path):
    docs_map = json.load(open(docs_map_path, encoding="utf-8"))
else:
    # fallback: 从 kb.json 的 docs 里取 md
    docs_map = {str(d.get("id")): d.get("md","") for d in docs if d.get("id") is not None}

ART_DIR = os.path.join(HERE, "a")
if os.path.isdir(ART_DIR):
    for fn in os.listdir(ART_DIR):
        if fn.endswith(".html"):
            os.remove(os.path.join(ART_DIR, fn))
else:
    os.makedirs(ART_DIR, exist_ok=True)

# d/<id>.json: 每篇一个单独正文文件(仅 {"md":...})，供前端按需/分片预热
# （只拉可见那几篇，不一把拉 2.1MB 全量 kb_docs.json，省流量）。
D_DIR = os.path.join(HERE, "d")
if os.path.isdir(D_DIR):
    for fn in os.listdir(D_DIR):
        if fn.endswith(".json"):
            os.remove(os.path.join(D_DIR, fn))
else:
    os.makedirs(D_DIR, exist_ok=True)


def esc(s):
    return _html.escape(str(s or ""), quote=True)


for d in docs:
    did = d.get("id")
    if did is None:
        continue
    title = d.get("title", "")
    desc = re.sub(r"\s+", " ", (d.get("text", "") or "")[:110]).strip()
    md = docs_map.get(str(did), "") or d.get("md", "") or ""
    # 用 JSON 序列化保证 md 里的特殊字符 (反引号/${}/</script> 等) 安全嵌入 JS
    md_js = json.dumps(md, ensure_ascii=False)
    # 防止字符串里出现 </script 提前闭合 (JSON 转义规则允许 \/)
    md_js = md_js.replace("</script", "<\\/script").replace("</SCRIPT", "<\\/SCRIPT")

    head_inject = (
        f'<title>{esc(title)} · A/B 实验知识库</title>\n'
        f'<meta name="description" content="{esc(desc)}">\n'
        f'<link rel="canonical" href="{SITE}/a/{did}.html">\n'
        f'<meta property="og:title" content="{esc(title)}">\n'
        f'<meta property="og:description" content="{esc(desc)}">\n'
        f'<meta property="og:type" content="article">\n'
        f'<meta property="og:url" content="{SITE}/a/{did}.html">\n'
        f'<script>window.DATA_BASE="../";window.INIT_DOC={int(did)};window.INIT_MD={md_js};</script>'
    )
    # 用注入块替换模板里的 <title>...</title> (其它 head 内容原样复用)
    # 注意: 文章页要用 ../ 前缀引用共享文件
    page = render(base_prefix="../", kb_data_block="")
    # ⬇ 用 lambda 避免替换串里的反斜杠被 re.sub 当转义序列解析(正文含 \u/$/\1 时会炒)
    page = re.sub(r"<title>.*?</title>", lambda m: head_inject, page, count=1, flags=re.S)
    open(os.path.join(ART_DIR, f"{did}.html"), "w", encoding="utf-8").write(page)
    # 同时写单篇正文 JSON（前端按需预热用，比拉整份 kb_docs.json 省流量）
    open(os.path.join(D_DIR, f"{did}.json"), "w", encoding="utf-8").write(
        json.dumps({"md": md}, ensure_ascii=False)
    )

# --- 完成 ---
root_kb = os.path.getsize(root_out) // 1024
dist_kb = os.path.getsize(os.path.join(HERE, "dist", "index.html")) // 1024
# 抽样单篇大小
sample_id = str(docs[0].get("id")) if docs else None
sample_kb = (os.path.getsize(os.path.join(ART_DIR, f"{sample_id}.html")) // 1024) if sample_id else 0
total_a = sum(os.path.getsize(os.path.join(ART_DIR, f)) for f in os.listdir(ART_DIR) if f.endswith(".html"))
print(f"✅ 打包完成:")
print(f"   index.html ({root_kb} KB, 外链 app.css/app.js)")
print(f"   dist/index.html ({dist_kb} KB, 妙搭内嵌全量)")
print(f"   a/*.html ({len(docs)} 篇, 抽样单篇 {sample_kb} KB, 目录合计 {total_a//1024} KB)")
