#!/usr/bin/env python3
# 从 Supabase 拉全部文章+分类，生成静态缓存 kb_cache.json（前端首屏秒开用）。
# 发新文章后重新生成一次即可。前端仍会后台比对数据库，缓存过期会自动刷新。
import json, os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
cfg  = json.load(open(os.path.join(HERE, "sb_config.json"), encoding="utf-8"))
URL, KEY = cfg["url"].rstrip("/"), cfg["key"]

def sb_get(pathq):
    req = urllib.request.Request(f"{URL}/rest/v1/{pathq}",
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

cats = sb_get("ab_categories?select=key,icon,name,descr,ord&order=ord")
arts = sb_get("ab_articles?select=doc_id,title,cat,keywords,md,body_text,updated,source_url,is_internal&order=doc_id")

kb = {
    "meta": {"total": len(arts), "source": "Supabase 缓存"},
    "categories": [{"key":c["key"],"icon":c["icon"],"name":c["name"],"desc":c.get("descr","")} for c in cats],
    "docs": [{"id":a["doc_id"],"title":a["title"],"cat":a["cat"],"keywords":a.get("keywords","") or "",
              "md":a.get("md","") or "","text":a.get("body_text","") or "",
              "updated":a.get("updated","") or "","url":a.get("source_url","") or "",
              "internal":bool(a.get("is_internal"))} for a in arts],
}
out = os.path.join(HERE, "kb_cache.json")
json.dump(kb, open(out,"w",encoding="utf-8"), ensure_ascii=False)
print(f"✅ 缓存已生成: kb_cache.json  ({os.path.getsize(out)//1024} KB, {len(arts)} 篇 + {len(cats)} 分类)")
