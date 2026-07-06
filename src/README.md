# A/B 实验知识库（营销增长中心）

面向营销广告公司内部的 A/B 实验知识库。内容来自火山引擎 DataTester 官方文档库
（LibraryID=6287，共 203 篇有正文的文章），按营销团队使用旅程重新归类为 12 个主题，
支持全文检索、分类导航、关键词高亮、**每篇可溯源到官方原文**，并支持持续新增知识。

## 文件说明

| 文件 | 作用 |
|---|---|
| `index.html` | 知识库前端（纯静态，fetch 加载 kb.json） |
| `kb.json` | 知识库数据（分类 + 203 篇正文 + 检索文本 + 溯源链接） |
| `crawl.py` | 首次全量爬取火山文档 → raw_docs.json |
| `sync_volc.py` | **增量同步**火山官方更新（发现新文档、更新变更） |
| `build_kb.py` | 由 raw_docs.json 重建分类 → kb.json（自动保留内部知识） |
| `add.py` | **新增内部自有知识**（公司自己的复盘/规范，非火山来源） |
| `raw_docs.json` | 爬取的原始数据（中间产物） |

## 三种「新增知识」的方式

### 1. 加公司内部自有知识（最常用）
```bash
python3 add.py --list-cats                     # 先看有哪些分类
python3 add.py --title "【内部】大促实验复盘规范" \
               --cat cases \
               --file 复盘.md \
               --keywords "复盘 大促"
```
内部知识用 9 开头的 id，标 `internal:true`，重建时自动保留，不会被官方同步覆盖。

### 2. 同步火山官方最新文档
```bash
python3 sync_volc.py     # 拉取火山最新，发现新增/变更
python3 build_kb.py      # 重建 kb.json（内部知识自动保留）
```

### 3. 直接编辑 kb.json
`kb.json` 的 `docs` 是数组，每条含 `id/title/cat/keywords/updated/url/md/text`，
手动追加一条即可（`text` 是检索用纯文本，`url` 是溯源链接）。

## 重新部署
改完数据后重新部署 dist 目录到妙搭即可生效：
```bash
~/feishu-claude-bot/scripts/deploy-to-miaoda.sh <dist目录> "A/B实验知识库" --scope tenant
```

## 数据接口（火山文档站，供维护参考）
- 目录树：`GET https://www.volcengine.com/api/doc/getDocList?LibraryID=6287`
- 单篇正文：`GET https://www.volcengine.com/api/doc/getDocDetail?DocumentID=<id>&LibraryID=6287`
- 原文页面：`https://www.volcengine.com/docs/6287/<id>`
