#!/usr/bin/env python3
# 把 dev.html + kb.json + marked.js 打包成单文件 standalone。
# 输出两份完全相同的成品：
#   - index.html      （仓库根，GitHub Pages 直接托管）
#   - dist/index.html （妙搭发布用，也可本地双击打开）
# 之所以内嵌数据，是因为静态托管会把子路径 fallback 到 index.html，拿不到独立 kb.json。
import json, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HERE,"dev.html"), encoding="utf-8").read()
kb   = open(os.path.join(HERE,"kb.json"), encoding="utf-8").read()
marked = open(os.path.join(HERE,"marked.min.js"), encoding="utf-8").read()

# 1) 内嵌 kb.json 到占位符（转义 </script 防止提前闭合）
kb_safe = kb.replace("</", "<\\/")
html = html.replace("<!--KB_DATA-->", kb_safe)

# 2) 用本地 marked 替换 CDN 引用（内网可用、更快、离线可打开）
html = html.replace(
    '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>',
    f'<script>{marked}</script>'
)

# 输出到仓库根 index.html（GitHub Pages）与 dist/index.html（妙搭/本地）
root_out = os.path.join(HERE, "index.html")
open(root_out, "w", encoding="utf-8").write(html)
os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
shutil.copyfile(root_out, os.path.join(HERE, "dist", "index.html"))

print(f"✅ 打包完成: index.html + dist/index.html  ({os.path.getsize(root_out)//1024} KB, 内嵌数据+marked)")
