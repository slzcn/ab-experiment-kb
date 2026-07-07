#!/usr/bin/env python3
# 从 Supabase 拉全部文章+分类，生成静态文件（前端纯静态读取）。
# 拆分优化（首屏最小化）：
#   kb_index.json  轻量列表：标题/分类/关键词/日期/来源 + 140字摘要 + 字数（无全文）
#                  → 首屏只下这个，几十KB，秒出列表
#   kb_search.json id → 全文检索文本（body_text）→ 后台异步加载，加载完启用正文全文搜索
#   kb_docs.json   id → md 正文 → 打开某篇文章时按需取
#   kb_cache.json  完整数据（含 md+text）→ 妙搭内嵌/离线回退
# 发新文章后由 GitHub Action 重新生成。
import json, os
from kb_common import Supabase

HERE = os.path.dirname(os.path.abspath(__file__))
SB = Supabase()

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
print(f"   {len(arts)} 篇 + {len(categories)} 分类。首屏只需下 kb_index.json。")
