#!/usr/bin/env python3
# 一键发布：扫描 articles/*.md → 合并进 kb.json → 打包成可本地双击打开的 dist/index.html
#
# 写新文章：在 articles/ 下新建一个 .md 文件，开头写 frontmatter：
#   ---
#   title: 双十一大促实验复盘
#   cat: cases            # 分类key，见下方列表或 python3 add.py --list-cats
#   keywords: 复盘 大促    # 选填，额外检索词
#   date: 2026-07-06      # 选填，不写则用文件修改日期
#   ---
#   （下面正文用 markdown 随便写）
#
# 然后运行：python3 publish.py
# 完成后双击 dist/index.html 即可在浏览器本地打开，新文章已并入、可检索。

import json, os, re, subprocess, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "articles")
KB  = os.path.join(HERE, "kb.json")

def plain(md):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"```[\s\S]*?```", "", t)
    t = re.sub(r"[#>*`\|\-]{1,}", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def parse_front(text):
    """解析开头的 ---\nkey: val\n--- frontmatter，返回 (meta, body)"""
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    return meta, m.group(2)

def stable_id(fname):
    """按文件名生成稳定 id（9 开头），同一文件重发不会重复添加"""
    h = 0
    for c in fname:
        h = (h * 131 + ord(c)) % 90000000
    return 910000000 + h

def main():
    kb = json.load(open(KB, encoding="utf-8"))
    cat_keys = {c["key"] for c in kb["categories"]}

    # 先移除上一轮由 articles 生成的条目（articleFile 标记），再重新加入，实现幂等更新
    kb["docs"] = [d for d in kb["docs"] if not d.get("articleFile")]

    files = sorted(f for f in os.listdir(ART) if f.endswith(".md")) if os.path.isdir(ART) else []
    added = 0
    for fn in files:
        path = os.path.join(ART, fn)
        raw = open(path, encoding="utf-8").read()
        meta, body = parse_front(raw)
        title = meta.get("title") or os.path.splitext(fn)[0]
        cat = meta.get("cat", "misc")
        if cat not in cat_keys:
            print(f"⚠️  {fn}: cat='{cat}' 不是有效分类，已归到 misc。可用: {sorted(cat_keys)}")
            cat = "misc"
        if not body.strip():
            print(f"⚠️  {fn}: 正文为空，跳过"); continue
        date = meta.get("date")
        if not date:
            ts = os.path.getmtime(path)
            date = datetime.date.fromtimestamp(ts).isoformat()
        kb["docs"].append({
            "id": stable_id(fn),
            "title": title,
            "cat": cat,
            "keywords": (meta.get("keywords", "") + " 内部文章").strip(),
            "updated": date,
            "url": meta.get("url", f"#article-{fn}"),
            "md": body.strip(),
            "text": plain(body),
            "internal": True,
            "articleFile": fn,
        })
        added += 1
        print(f"  + {fn}  →《{title}》[{cat}]")

    kb["meta"]["total"] = len(kb["docs"])
    json.dump(kb, open(KB, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n合并本地文章 {added} 篇，全库现有 {len(kb['docs'])} 篇。")

    # 直接打包成可本地打开的单文件
    r = subprocess.run([sys.executable, os.path.join(HERE, "bundle.py")])
    if r.returncode == 0:
        dist = os.path.join(HERE, "dist", "index.html")
        print(f"\n✅ 已生成成品：{dist}")
        print("   → 双击这个文件即可在浏览器本地打开知识库（离线可用）")
        print("   → 要发布到线上，把它覆盖到 GitHub 仓库根目录再 push（详见 src/README.md）")

if __name__ == "__main__":
    main()
