#!/usr/bin/env python3
# 从 Supabase 拉全部文章+分类，生成静态文件（前端纯静态读取）。
# 拆分优化（首屏最小化）：
#   kb_index.json  轻量列表：标题/分类/关键词/日期/来源 + 140字摘要 + 字数（无全文）
#                  → 首屏只下这个，几十KB，秒出列表
#   kb_search.json id → 全文检索文本（body_text）→ 后台异步加载，加载完启用正文全文搜索
#   kb_docs.json   id → md 正文 → 打开某篇文章时按需取
#   kb_cache.json  完整数据（含 md+text）→ 妙搭内嵌/离线回退
#   a/<id>.html    每篇一个真实静态页 → 直达/分享/SEO（搜索引擎可单独收录）
# 发新文章后由 GitHub Action 重新生成。
import json, os, re, html as _html, shutil
from kb_common import Supabase

HERE = os.path.dirname(os.path.abspath(__file__))
SB = Supabase()
SITE = "https://slzcn.github.io/ab-experiment-kb"   # 站点基地址（用于 canonical/图片绝对路径）

cats = SB.get("ab_categories?select=key,icon,name,descr,ord&order=ord")
# 带 published 列查询；若该列尚未 ALTER 出来（PostgREST 400），退回不带该列的查询，
# 保证 Action 在“加字段 SQL 还没跑”的过渡期也不会挂。
try:
    arts = SB.get("ab_articles?select=doc_id,title,cat,keywords,md,body_text,updated,source_url,is_internal,published&order=doc_id")
except Exception:
    arts = SB.get("ab_articles?select=doc_id,title,cat,keywords,md,body_text,updated,source_url,is_internal&order=doc_id")

# 只把「上线」文章写进公开静态文件——下线的库里保留、但公开站不显示。
# published 为 None（老数据未设/该列不存在）按上线处理。
arts = [a for a in arts if a.get("published", True) is not False]

categories = [{"key":c["key"],"icon":c["icon"],"name":c["name"],"desc":c.get("descr","")} for c in cats]

# 完整 docs（含 md）——保留给 bundle 内嵌 & 离线回退
full_docs = [{"id":a["doc_id"],"title":a["title"],"cat":a["cat"],"keywords":a.get("keywords","") or "",
              "md":a.get("md","") or "","text":a.get("body_text","") or "",
              "updated":a.get("updated","") or "","url":a.get("source_url","") or "",
              "internal":bool(a.get("is_internal"))} for a in arts]

# 轻量列表：去掉全文 text，改放 140 字摘要 + 字数（列表卡片只需这些）
index_docs = [{
    "id":d["id"], "title":d["title"], "cat":d["cat"], "keywords":d["keywords"],
    "updated":d["updated"], "url":d["url"], "internal":d["internal"],
    "excerpt":(d["text"][:140]), "len":len(d["text"]),
} for d in full_docs]
# 全文检索索引：id -> 全文（后台异步加载，用于正文全文搜索）
search_idx = {str(d["id"]): d["text"] for d in full_docs}
# 正文映射 id -> md（点开文章时按需取）
docs_md = {str(d["id"]): d["md"] for d in full_docs}

def dump(name, obj):
    p = os.path.join(HERE, name)
    json.dump(obj, open(p,"w",encoding="utf-8"), ensure_ascii=False)
    return os.path.getsize(p)//1024

s1 = dump("kb_index.json", {"meta":{"total":len(arts),"source":"Supabase"},"categories":categories,"docs":index_docs})
s4 = dump("kb_search.json", search_idx)
s2 = dump("kb_docs.json", docs_md)
s3 = dump("kb_cache.json", {"meta":{"total":len(arts),"source":"Supabase"},"categories":categories,"docs":full_docs})
print(f"✅ 已生成: kb_index.json({s1}KB, 轻量列表+摘要) + kb_search.json({s4}KB, 全文索引) "
      f"+ kb_docs.json({s2}KB, 正文) + kb_cache.json({s3}KB, 完整)")


# ============ 每篇生成一个真实静态页 a/<id>.html（SEO / 直达 / 分享）============
def md_to_html(md):
    """极简 Markdown→HTML：覆盖本项目文章用到的语法（标题/加粗/列表/图片/链接/代码/引用/表格）。
    文章来自我们自己的管道、格式干净，不追求完备，只求正确渲染常见结构。"""
    lines = (md or "").replace("\r\n", "\n").split("\n")
    out, i, n = [], 0, len(lines)
    def inline(t):
        t = _html.escape(t)
        t = re.sub(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", r'<img src="\1" loading="lazy">', t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        return t
    while i < n:
        ln = lines[i]
        # 代码块
        if ln.startswith("```"):
            i += 1; buf = []
            while i < n and not lines[i].startswith("```"): buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre><code>" + _html.escape("\n".join(buf)) + "</code></pre>"); continue
        # 标题
        m = re.match(r"(#{1,4})\s+(.*)", ln)
        if m:
            lv = len(m.group(1)); out.append(f"<h{lv}>{inline(m.group(2))}</h{lv}>"); i += 1; continue
        # 表格（连续以 | 开头的行）
        if ln.strip().startswith("|") and i+1 < n and re.match(r"\s*\|?[\s:\-|]+\|?\s*$", lines[i+1]):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2; rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            trs = "".join("<tr>"+"".join(f"<td>{inline(c)}</td>" for c in r)+"</tr>" for r in rows)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"); continue
        # 无序列表
        if re.match(r"\s*[-*]\s+", ln):
            items = []
            while i < n and re.match(r"\s*[-*]\s+", lines[i]):
                items.append("<li>"+inline(re.sub(r"\s*[-*]\s+", "", lines[i], count=1))+"</li>"); i += 1
            out.append("<ul>"+"".join(items)+"</ul>"); continue
        # 有序列表
        if re.match(r"\s*\d+\.\s+", ln):
            items = []
            while i < n and re.match(r"\s*\d+\.\s+", lines[i]):
                items.append("<li>"+inline(re.sub(r"\s*\d+\.\s+", "", lines[i], count=1))+"</li>"); i += 1
            out.append("<ol>"+"".join(items)+"</ol>"); continue
        # 分隔线
        if re.match(r"\s*(-{3,}|\*{3,})\s*$", ln):
            out.append("<hr>"); i += 1; continue
        # 引用
        if ln.startswith(">"):
            out.append("<blockquote>"+inline(ln.lstrip("> ").rstrip())+"</blockquote>"); i += 1; continue
        # 空行
        if not ln.strip(): i += 1; continue
        # 普通段落（合并连续非空行）
        buf = [ln]; i += 1
        while i < n and lines[i].strip() and not re.match(r"(#{1,4}\s|```|\s*[-*]\s|\s*\d+\.\s|>|\|)", lines[i]):
            buf.append(lines[i]); i += 1
        out.append("<p>"+inline(" ".join(buf))+"</p>")
    return "\n".join(out)

ART_TPL = """<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · A/B 实验知识库</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{site}/a/{id}.html">
<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">
<meta property="og:type" content="article"><meta property="og:url" content="{site}/a/{id}.html">
<style>
:root{{--bg:#faf7f2;--bg2:#fff;--line:#e8e0d4;--ink:#2c2a26;--sub:#6b6459;--dim:#9a9184;--brand:#e0632e;--brand2:#c9541f;--panel:#f4efe7}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--ink);font:16px/1.9 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:720px;margin:0 auto;padding:26px 20px 60px}}
.back{{display:inline-block;color:var(--dim);text-decoration:none;font-size:13px;margin-bottom:22px}}
.back:hover{{color:var(--brand)}}
.ct{{display:inline-block;font-size:11.5px;font-weight:600;color:var(--brand2);background:rgba(224,99,46,.1);padding:4px 12px;border-radius:20px}}
h1{{font-size:30px;font-weight:800;line-height:1.32;letter-spacing:-.01em;margin:14px 0 14px}}
.meta{{font-size:12.5px;color:var(--dim);padding-bottom:22px;border-bottom:1px solid var(--line);margin-bottom:26px}}
.md{{color:#3a3733}}
.md h1,.md h2,.md h3,.md h4{{color:var(--ink);font-weight:750;line-height:1.4;margin:1.9em 0 .7em}}
.md h1{{font-size:23px}} .md h2{{font-size:20px;padding-left:11px;border-left:4px solid var(--brand)}} .md h3{{font-size:17px}}
.md p{{margin:1em 0}} .md strong{{color:var(--ink)}}
.md a{{color:var(--brand2);border-bottom:1px solid rgba(201,84,31,.4)}}
.md ul,.md ol{{margin:.8em 0;padding-left:1.5em}} .md li{{margin:.45em 0}}
.md img{{max-width:100%;height:auto;border-radius:12px;border:1px solid var(--line);display:block;margin:20px auto;max-height:70vh;width:auto}}
.md blockquote{{border-left:3px solid var(--brand);background:var(--panel);padding:12px 18px;margin:1.2em 0;border-radius:0 10px 10px 0;color:var(--sub)}}
.md code{{background:var(--panel);padding:2px 6px;border-radius:5px;font-size:.9em;color:var(--brand2)}}
.md pre{{background:#2c2a26;border-radius:10px;padding:15px 17px;overflow-x:auto;margin:1em 0}}
.md pre code{{background:none;padding:0;color:#f0ebe2;font-size:13px;line-height:1.6}}
.md table{{border-collapse:collapse;width:100%;margin:1.1em 0;font-size:14px;display:block;overflow-x:auto}}
.md th,.md td{{border:1px solid var(--line);padding:8px 12px;text-align:left}} .md th{{background:var(--panel)}}
.foot{{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);color:var(--dim);font-size:12.5px;text-align:center}}
.foot a{{color:var(--brand2);text-decoration:none}}
</style></head><body>
<div class="wrap">
<a class="back" href="{site}/">← 返回知识库</a>
<div><span class="ct">{cat_icon} {cat_name}</span></div>
<h1>{title}</h1>
<div class="meta">📄 {wordcount} 字 · 🕐 {updated}</div>
<article class="md">{body}</article>
<div class="foot">{src} · <a href="{site}/">← 返回 A/B 实验知识库</a></div>
</div></body></html>"""

cat_map = {c["key"]: c for c in categories}
ART_DIR = os.path.join(HERE, "a")
# 每次全量重建：先清空 a/ 再生成，避免下线/删除的文章残留静态页
if os.path.isdir(ART_DIR): shutil.rmtree(ART_DIR)
os.makedirs(ART_DIR, exist_ok=True)
for d in full_docs:
    c = cat_map.get(d["cat"], {"icon": "📎", "name": "其他"})
    desc = (d["text"][:110].replace("\n", " ").strip()).replace('"', "'")
    is_internal = d["internal"] or not re.match(r"^https?:", d["url"] or "")
    src = "本文为营销增长中心内部沉淀" if is_internal else "内容整理自火山引擎 DataTester A/B testing 文档库"
    page = ART_TPL.format(
        site=SITE, id=d["id"], title=_html.escape(d["title"]), desc=_html.escape(desc),
        cat_icon=c.get("icon", "📎"), cat_name=_html.escape(c.get("name", "其他")),
        wordcount=f'{len(d["text"]):,}', updated=d["updated"] or "—",
        body=md_to_html(d["md"]), src=src)
    open(os.path.join(ART_DIR, f'{d["id"]}.html'), "w", encoding="utf-8").write(page)

print(f"   {len(arts)} 篇 + {len(categories)} 分类。首屏只需下 kb_index.json。")
print(f"✅ 已生成 {len(full_docs)} 个文章静态页 → a/<id>.html（SEO/直达/分享）")
