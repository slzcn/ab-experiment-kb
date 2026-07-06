#!/usr/bin/env python3
# 爬取火山引擎 DataTester A/B testing 文档库 (LibraryID=6287) 全部文档正文
import json, os, time, urllib.request, urllib.error

LIB = 6287
BASE = "https://www.volcengine.com"
HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_list():
    d = get(f"{BASE}/api/doc/getDocList?LibraryID={LIB}")
    return d["Result"]

def fetch_detail(doc_id):
    for attempt in range(4):
        try:
            d = get(f"{BASE}/api/doc/getDocDetail?DocumentID={doc_id}&LibraryID={LIB}")
            return d["Result"]
        except Exception as e:
            if attempt == 3:
                print(f"  !! {doc_id} 失败: {e}")
                return None
            time.sleep(1.5 * (attempt + 1))

def main():
    lst = fetch_list()
    # 建立 id->节点(含层级信息)
    index = {n["DocumentID"]: n for n in lst}
    print(f"目录节点 {len(lst)} 个，开始拉正文...")

    docs = []
    for i, n in enumerate(lst, 1):
        did = n["DocumentID"]
        detail = fetch_detail(did)
        if not detail:
            continue
        md = (detail.get("MDContent") or "").strip()
        docs.append({
            "id": did,
            "code": detail.get("DocumentCode"),
            "title": detail.get("Title"),
            "parent_id": detail.get("ParentID"),
            "type": n.get("Type"),          # 1=目录组 0=文章(经验值)
            "index": n.get("Index"),
            "keywords": detail.get("Keywords") or "",
            "updated": detail.get("UpdatedTime"),
            "md": md,
            "md_len": len(md),
            "url": f"{BASE}/docs/{LIB}/{did}",
        })
        if i % 20 == 0:
            print(f"  {i}/{len(lst)}  最近: {detail.get('Title')} ({len(md)}字)")
        time.sleep(0.25)

    out = os.path.join(HERE, "raw_docs.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=1)
    empty = sum(1 for d in docs if d["md_len"] == 0)
    print(f"\n完成: {len(docs)} 篇，其中空正文 {empty} 篇。写入 {out}")

if __name__ == "__main__":
    main()
