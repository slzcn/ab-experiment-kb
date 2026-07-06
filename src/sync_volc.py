#!/usr/bin/env python3
# 从火山引擎 DataTester 文档库增量同步：发现新文档、更新已变更的文档。
# 会保留用 add.py 加进来的内部自有知识（internal=True）。
# 用法: python3 sync_volc.py   然后 python3 build_kb.py 重建分类
import json, os, time, urllib.request

LIB = 6287
BASE = "https://www.volcengine.com"
HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def detail(did):
    for k in range(4):
        try: return get(f"{BASE}/api/doc/getDocDetail?DocumentID={did}&LibraryID={LIB}")["Result"]
        except Exception:
            if k==3: return None
            time.sleep(1.5*(k+1))

def main():
    raw_path = os.path.join(HERE, "raw_docs.json")
    old = json.load(open(raw_path, encoding="utf-8")) if os.path.exists(raw_path) else []
    old_map = {d["id"]: d for d in old}

    lst = get(f"{BASE}/api/doc/getDocList?LibraryID={LIB}")["Result"]
    print(f"火山目录节点 {len(lst)} 个，检查更新...")

    new_cnt = upd_cnt = 0
    result = []
    for i, n in enumerate(lst, 1):
        did = n["DocumentID"]
        d = detail(did)
        if not d or not (d.get("MDContent") or "").strip():
            # 目录容器/空文，保留旧的（若有）
            if did in old_map: result.append(old_map[did])
            continue
        md = d["MDContent"].strip()
        upd = d.get("UpdatedTime")
        rec = {"id":did,"code":d.get("DocumentCode"),"title":d.get("Title"),
               "parent_id":d.get("ParentID"),"type":n.get("Type"),"index":n.get("Index"),
               "keywords":d.get("Keywords") or "","updated":upd,"md":md,"md_len":len(md),
               "url":f"{BASE}/docs/{LIB}/{did}"}
        if did not in old_map: new_cnt += 1
        elif old_map[did].get("updated") != upd or old_map[did].get("md_len") != len(md): upd_cnt += 1
        result.append(rec)
        time.sleep(0.25)

    json.dump(result, open(raw_path,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"完成：新增 {new_cnt} 篇，更新 {upd_cnt} 篇，火山侧共 {len(result)} 篇。")
    print("下一步：python3 build_kb.py  （会自动合并内部知识并重建分类）")

if __name__ == "__main__":
    main()
