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

### 方式一：网页直接写（推荐，零文件操作）

打开线上或本地的知识库页面，点左下「✍ 写一篇新文章」→ 填标题/选分类/写 Markdown
→ 点「✓ 提交并发布」。文章直接写入 Supabase，约十几秒后 GitHub Action 重生成静态文件、
全网同步。全程不下载、不碰文件。

> 需要上传文档转码 / 批量管理，见下方「管理后台」。

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

## 管理后台（增删改 + 批量上传文档转码）

一个独立的管理后台 `admin.html`，需授权访问，
顶部三个 tab：

- **📤 批量上传**：拖入 PPT / Word / PDF / Excel 等文档，**纯网页操作、零本地依赖**。
  **每个文件可单独选分类**（默认继承顶部的默认分类，可逐个调整）。浏览器把原始文件直传
  Supabase Storage 并建处理任务；**服务器（GitHub Action）**自动抽取正文**并连同文档里的
  图片**转成带图 Markdown 文章入库。前端实时显示每个文件的排队/转码/完成进度，
  可关闭本页，几分钟后自动同步到线上。
- **📄 文章管理**：列出全部文章，可搜索、在线编辑（标题/分类/关键词/正文）、删除。
- **🗂 分类配置**：增删改分类（key / 图标 / 名称 / 排序）。

三个 tab 全部纯 web、直连 Supabase，**不需要在本地跑任何脚本**。打开线上
`https://slzcn.github.io/ab-experiment-kb/admin.html` 即可用。

### 上传处理链路（纯 web）

```
浏览器 admin.html
  ① 原始文件 → Supabase Storage 桶(doc-uploads)
  ② 插一条 upload_jobs 记录(status=queued)
        ▼
GitHub Action = 服务器 (.github/workflows/process-uploads.yml，每 5 分钟 / 可手动触发)
  ③ 拉 queued 任务 → 从 Storage 下载 → doc_to_md 转码抽图
  ④ 写 ab_articles + 提交图片到仓库 → 回填 upload_jobs 状态
        ▼
触发 refresh-cache Action 重生成静态文件，全网同步
浏览器轮询 upload_jobs 看进度
```

**一次性初始化**：在 Supabase 控制台 SQL Editor 跑一次 `supabase_uploads.sql`
（建 Storage 桶 + upload_jobs 表 + RLS）。之后永远不用碰本地。

> 图片存到 `assets/` 并由 Action 推到仓库，md 用 `raw.githubusercontent` 引用
> （与手工发布的文章图片模型一致）。主站左下角「⚙ 管理后台」可进入。

## 公开站如何同步后台改动（数据库触发，即时全自动）

任何改动——前端「写文章」、后台的增/删/改/上下线、批量上传——都即时写入数据库；
数据库的**触发器**会在写入后立刻通知 GitHub 重建公开站，约 1 分钟同步，**全程零手动**。

链路：`ab_articles/ab_categories` 增删改 → 数据库触发器（pg_net 发 repository_dispatch）
→ `refresh-cache` Action 跑 `gen_cache.py` 重生成静态文件（已排除下线文章）→ 提交上线。
每 10 分钟另有一次定时兜底，万一某次即时触发漏了也能补上。

**一次性初始化**（跑一次 SQL，之后永久生效）：
1. 建 GitHub token：https://github.com/settings/personal-access-tokens/new
   → 选仓库 `slzcn/ab-experiment-kb` → Contents: Read and write → 生成复制
2. 在 Supabase 控制台 SQL Editor 打开 `supabase_autosync.sql`，把第 1 段的
   `<YOUR_GITHUB_TOKEN>` 换成刚建的 token，整个文件运行一次。

> token 存进 Supabase Vault（加密），不明文落在触发器里；触发器用 statement 级 +
> Action 端 `cancel-in-progress`，短时间多次改动会自动合并成最新一次重建，不会堆积。

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
| `admin.html` | ★ 管理后台：授权访问，批量上传文档 / 文章增删改 / 分类配置（纯 web）|
| `supabase_uploads.sql` | ★ 一次性初始化：建 Storage 桶 + upload_jobs 表 + RLS |
| `process_uploads.py` | ★ 服务器处理器：拉待处理任务 → 转码入库（在 GitHub Action 里跑）|
| `.github/workflows/process-uploads.yml` | ★ 上传处理 workflow（每 5 分钟 / 可手动触发）|
| `doc_to_md.py` | 文档→Markdown 转码器（抽文字+图，图存 assets/），被处理器调用也可单跑 |
| `kb_common.py` | 公共工具：纯文本提取 / slug / git / Supabase REST + Storage 客户端 |
| `publish.py` | 一键发布：articles → kb.json → 打包 → --push 推线上 |
| `bundle.py` | 打包 dev.html+数据 → index.html / dist/index.html |
| `crawl.py` / `sync_volc.py` | 全量爬取 / 增量同步火山文档 |
| `build_kb.py` / `add.py` | 重建分类 / 命令行新增知识 |
| `marked.min.js` | Markdown 渲染库（打包内联，离线可用） |

## 数据接口（火山文档站，供维护参考）
- 目录树：`GET https://www.volcengine.com/api/doc/getDocList?LibraryID=6287`
- 单篇正文：`GET https://www.volcengine.com/api/doc/getDocDetail?DocumentID=<id>&LibraryID=6287`
- 原文页面：`https://www.volcengine.com/docs/6287/<id>`
