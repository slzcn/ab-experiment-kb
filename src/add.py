#!/usr/bin/env python3
# 往知识库新增一条【内部自有知识】（非火山来源，比如公司自己的实验复盘/规范）
# 用法:
#   python3 add.py --title "标题" --cat design --file 正文.md
#   python3 add.py --title "标题" --cat cases --text "正文内容..."
#   python3 add.py --list-cats           # 查看可用分类key
import json, os, re, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.path.join(HERE, "kb.json")

def plain(md):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"```[\s\S]*?```", "", t)
    t = re.sub(r"[#>*`\|\-]{1,}", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def main():
    kb = json.load(open(KB, encoding="utf-8"))
    cat_keys = [c["key"] for c in kb["categories"]]

    ap = argparse.ArgumentParser()
    ap.add_argument("--title")
    ap.add_argument("--cat", help="分类key，见 --list-cats")
    ap.add_argument("--file", help="markdown 正文文件路径")
    ap.add_argument("--text", help="直接给正文文本")
    ap.add_argument("--url", default="", help="可选：内部文档来源链接（溯源用）")
    ap.add_argument("--keywords", default="", help="可选：额外检索关键词")
    ap.add_argument("--list-cats", action="store_true")
    a = ap.parse_args()

    if a.list_cats:
        for c in kb["categories"]:
            print(f'  {c["key"]:<10} {c["icon"]} {c["name"]}  —— {c["desc"]}')
        return

    assert a.title, "必须给 --title"
    assert a.cat in cat_keys, f"--cat 必须是: {cat_keys}"
    md = open(a.file, encoding="utf-8").read() if a.file else (a.text or "")
    assert md.strip(), "正文不能为空（--file 或 --text）"

    # 生成新id：自有知识用 9 开头的大号，避免和火山id撞
    exist = {d["id"] for d in kb["docs"]}
    nid = 900000001
    while nid in exist: nid += 1

    doc = {
        "id": nid,
        "title": a.title,
        "cat": a.cat,
        "keywords": (a.keywords + " 内部知识").strip(),
        "updated": datetime.date.today().isoformat(),
        "url": a.url or f"#internal-{nid}",   # 无外链则给锚点
        "md": md,
        "text": plain(md),
        "internal": True,   # 标记为内部自有
    }
    kb["docs"].append(doc)
    kb["meta"]["total"] = len(kb["docs"])
    json.dump(kb, open(KB, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"✅ 已新增: [{nid}] 《{a.title}》→ 分类 {a.cat}")
    print(f"   全库现有 {len(kb['docs'])} 篇。重新部署即可生效。")

if __name__ == "__main__":
    main()
