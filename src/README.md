# A/B 实验知识库（营销增长中心）

面向营销广告公司内部的 A/B 实验知识库。内容来自火山引擎 DataTester 官方文档库
（LibraryID=6287，共 203 篇有正文的文章），按营销团队使用旅程重新归类为 12 个主题，
支持全文检索、分类导航、关键词高亮、**每篇可溯源到官方原文**，乳白亮色主题，并支持持续新增文章。

## 文件说明

| 文件 | 作用 |
|---|---|
| `index.html` | 知识库前端（本地开发版，fetch 加载 kb.json；含「✍ 写文章」编辑器） |
| `kb.json` | 知识库数据（分类 + 正文 + 检索文本 + 溯源链接） |
| `articles/` | **放新文章的目录**（每篇一个 .md，带 frontmatter） |
| `publish.py` | **一键发布**：扫描 articles/ → 合并进 kb.json → 打包出可双击打开的 dist/index.html |
| `bundle.py` | 打包成单文件 standalone（内嵌数据 + marked.js） |
| `crawl.py` | 首次全量爬取火山文档 → raw_docs.json |
| `sync_volc.py` | 增量同步火山官方更新（发现新文档、更新变更） |
| `build_kb.py` | 由 raw_docs.json 重建分类 → kb.json（自动保留内部文章） |
| `add.py` | 命令行新增内部知识（另一种入口） |

## 新增文章（推荐流程）

### 方式 A：网页里写（零技术门槛）
1. 打开知识库，点左下角 **「✍ 写一篇新文章」**
2. 填标题、选分类、写 Markdown（右侧实时预览）
3. 点 **「导出 .md 文件」**，把下载的文件放进 `articles/` 目录
4. 运行 `python3 publish.py`

### 方式 B：直接写 md 文件
在 `articles/` 下新建 `任意名字.md`，开头写 frontmatter：
```markdown
---
title: 双十一大促实验复盘
cat: cases            # 分类key，见 python3 add.py --list-cats
keywords: 复盘 大促    # 选填
date: 2026-07-06      # 选填
---

# 正文用 Markdown 随便写
```
然后 `python3 publish.py`，双击生成的 `dist/index.html` 即可本地查看（离线可用）。

> `publish.py` 是幂等的：同名文件重发只会更新、不会重复。articles 里的文章标 `internal`，
> 不会被火山官方同步覆盖。

## 同步火山官方最新文档
```bash
python3 sync_volc.py     # 拉取火山最新
python3 build_kb.py      # 重建 kb.json（本地文章自动保留）
python3 publish.py       # 或直接 publish.py，会顺带打包
```

## 部署到线上

### GitHub Pages（公网免登录）
把 `dist/index.html` 覆盖到仓库根目录后 push：
```bash
cp dist/index.html <仓库>/index.html && cd <仓库> && git add -A && git commit -m "更新知识库" && git push
```

### 飞书妙搭（企业内可见）
```bash
~/feishu-claude-bot/scripts/deploy-to-miaoda.sh dist "A/B实验知识库" --scope tenant
```

## 数据接口（火山文档站，供维护参考）
- 目录树：`GET https://www.volcengine.com/api/doc/getDocList?LibraryID=6287`
- 单篇正文：`GET https://www.volcengine.com/api/doc/getDocDetail?DocumentID=<id>&LibraryID=6287`
- 原文页面：`https://www.volcengine.com/docs/6287/<id>`
