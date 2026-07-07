#!/usr/bin/env python3
# 把 dev.html + kb.json + marked.js 打包成单文件 standalone。
# 输出两份，用途不同：
#   - index.html      （仓库根，GitHub Pages）——★不内嵌全量正文★，首屏只 fetch
#     同目录的 kb_index.json（轻量列表），正文点开时按需拉 kb_docs.json。
#     内嵌全量会让文件涨到 ~2MB 且线上根本用不到（首屏走 fetch），纯浪费带宽。
#   - dist/index.html （妙搭发布 / 本地双击）——必须内嵌全量：静态托管会把子路径
#     fallback 到 index.html，拿不到独立 kb.json，只能靠内嵌数据离线自足。
import os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HERE,"dev.html"), encoding="utf-8").read()
kb   = open(os.path.join(HERE,"kb.json"), encoding="utf-8").read()
marked = open(os.path.join(HERE,"marked.min.js"), encoding="utf-8").read()

# 用本地 marked 替换 CDN 引用（内网可用、更快、离线可打开）——两份都要
html = html.replace(
    '<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>',
    f'<script>{marked}</script>'
)

# 1) 仓库根 index.html（GitHub Pages）：占位符替换成空串，不内嵌全量数据。
#    boot() 会 fetch kb_index.json，内嵌兜底那层用不到。
root_html = html.replace("<!--KB_DATA-->", "")
root_out = os.path.join(HERE, "index.html")
open(root_out, "w", encoding="utf-8").write(root_html)

# 2) dist/index.html（妙搭/本地双击）：内嵌全量正文，离线自足。
kb_safe = kb.replace("</", "<\\/")   # 转义 </script 防止提前闭合
dist_html = html.replace("<!--KB_DATA-->", kb_safe)
os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
open(os.path.join(HERE, "dist", "index.html"), "w", encoding="utf-8").write(dist_html)

print(f"✅ 打包完成: index.html ({os.path.getsize(root_out)//1024} KB, 瘦身/fetch) "
      f"+ dist/index.html ({os.path.getsize(os.path.join(HERE,'dist','index.html'))//1024} KB, 内嵌全量/妙搭)")
