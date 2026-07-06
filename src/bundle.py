#!/usr/bin/env python3
# 把 index.html + kb.json + marked.js 打包成单文件 dist/index.html。
# 妙搭静态托管会把子路径 fallback 到 index.html，拿不到独立 kb.json，
# 所以线上必须用内嵌数据的 standalone 版本。
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HERE,"index.html"), encoding="utf-8").read()
kb   = open(os.path.join(HERE,"kb.json"), encoding="utf-8").read()
marked = open(os.path.join(HERE,"marked.min.js"), encoding="utf-8").read()

# 1) 内嵌 kb.json 到占位符（转义 </script 防止提前闭合）
kb_safe = kb.replace("</", "<\\/")
html = html.replace("<!--KB_DATA-->", kb_safe)

# 2) 用本地 marked 替换 CDN 引用（内网可用、更快）
html = html.replace(
    '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>',
    f'<script>{marked}</script>'
)

os.makedirs(os.path.join(HERE,"dist"), exist_ok=True)
out = os.path.join(HERE,"dist","index.html")
open(out,"w",encoding="utf-8").write(html)
# 清掉 dist 里可能残留的独立 kb.json（standalone 不需要）
stray = os.path.join(HERE,"dist","kb.json")
if os.path.exists(stray): os.remove(stray)

print(f"✅ 打包完成: {out}  ({os.path.getsize(out)//1024} KB, 单文件内嵌数据+marked)")
