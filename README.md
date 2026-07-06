# A/B 实验知识库 · 营销增长中心

面向营销广告公司内部的 A/B 实验知识库。内容整理自火山引擎 DataTester 官方文档库
（共 203 篇有正文的文章），按营销团队使用旅程归类为 12 个主题，支持全文检索、分类导航、
关键词高亮，每篇可溯源到官方原文，乳白亮色主题，并支持在本地持续新增文章、一步发布上线。

## 这个目录就是权威仓库

`~/ab-experiment-kb` 既是本地工作区，也直接连着 GitHub（`slzcn/ab-experiment-kb`）。
文章、数据、脚本、线上产物全在这里，改完一条命令即可更新线上——不再有第二份拷贝。

在线地址（GitHub Pages，公网免登录）：https://slzcn.github.io/ab-experiment-kb/
飞书妙搭（企业内可见）：https://fenmikeji.aiforce.cloud/app/app_179k37gs08n

## 新增一篇文章 → 一步更新线上

### 方式一：网页点一下直接提交（推荐，零文件操作）

在你自己的电脑上启动本地发布服务，然后在网页里写完点「提交并发布」就直接入库、直接上线：
```bash
cd ~/ab-experiment-kb
python3 serve.py --push        # 提交即推送线上（去掉 --push 则只入本地）
# 也可再加 --miaoda 同步飞书妙搭
```
按提示打开 `http://localhost:8799` → 点左下「✍ 写一篇新文章」→ 填标题/选分类/写正文
→ 点「✓ 提交并发布」。文章自动写入 `articles/`、合并打包、（--push 时）推送 GitHub Pages，
新文章立刻出现在页面上，全程不下载、不碰文件。

> 这个写入口只在本机 localhost 监听、不对外。线上公开版没有它，编辑器会自动回退成「导出 .md」，
> 所以公网访客无法直接改你的库——安全。

### 方式二：命令行（适合批量 / 已有 md）

在 `articles/` 放带 frontmatter 的 `.md`，或用网页的「导出」按钮拿到 md 文件放进去：
```markdown
---
title: 双十一大促实验复盘
cat: cases            # 分类key，见 python3 add.py --list-cats
keywords: 复盘 大促    # 选填
date: 2026-07-06      # 选填
---

# 正文用 Markdown 随便写
```
然后一条命令发布：
```bash
python3 publish.py --push            # 合并 → 打包 → 推 GitHub Pages（约1分钟后线上更新）
python3 publish.py --push --miaoda   # 想同时更新飞书妙搭就多加 --miaoda
```
不加参数（`python3 publish.py`）则只在本地生成 `dist/index.html`，双击即可离线预览。

> `publish.py` 幂等：同名文件重发只更新、不重复。文章标 `internal`，火山官方同步不会覆盖它。

## 同步火山官方最新文档
```bash
python3 sync_volc.py     # 拉火山最新
python3 build_kb.py      # 重建分类（本地文章自动保留）
python3 publish.py --push
```

## 文件说明

| 文件 | 作用 |
|---|---|
| `index.html` | **线上版**：单文件 standalone（内嵌数据+marked），GitHub Pages 托管 |
| `dist/index.html` | 同上，供妙搭发布 / 本地双击 |
| `dev.html` | 前端源码模板（读同目录 kb.json，仅本地开发调试用） |
| `articles/` | **放新文章的目录**（每篇一个带 frontmatter 的 .md） |
| `kb.json` | 知识库数据 |
| `serve.py` | ★ 本地发布服务：网页点「提交并发布」直接入库（--push 直推线上） |
| `publish.py` | 一键发布：articles → kb.json → 打包 → --push 推线上 |
| `bundle.py` | 打包 dev.html+数据 → index.html / dist/index.html |
| `crawl.py` / `sync_volc.py` | 全量爬取 / 增量同步火山文档 |
| `build_kb.py` / `add.py` | 重建分类 / 命令行新增知识 |
| `marked.min.js` | Markdown 渲染库（打包内联，离线可用） |

## 数据接口（火山文档站，供维护参考）
- 目录树：`GET https://www.volcengine.com/api/doc/getDocList?LibraryID=6287`
- 单篇正文：`GET https://www.volcengine.com/api/doc/getDocDetail?DocumentID=<id>&LibraryID=6287`
- 原文页面：`https://www.volcengine.com/docs/6287/<id>`
