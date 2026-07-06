# A/B 实验知识库 · 营销增长中心

面向营销广告公司内部的 **A/B 实验知识库**。内容整理自火山引擎 DataTester 官方文档库
（共 **203 篇**有正文的文章），按营销团队使用旅程重新归类为 **12 个主题**，支持
**全文检索、分类导航、关键词高亮**，每篇**可溯源到官方原文**，乳白亮色主题，
并支持**在本地持续新增文章**。

## 在线访问

GitHub Pages 部署，根目录 `index.html` 为单文件 standalone 版（数据已内嵌），打开即用、免登录。

## 12 个主题

📢 广告投放实验　🏆 实战案例库　💡 AB通识科普　📐 实验设计与规划　🧪 创建与管理实验
📊 实验报告与分析　🎯 指标体系　🗂️ 数据与埋点　🔌 SDK与技术集成　🚩 Feature管理
⚙️ 配置·权限·计费　📎 上手·协议·其他

## 新增文章（本地发布，两种方式）

**方式 A — 网页里写（零门槛）**：打开知识库点左下角「✍ 写一篇新文章」，填标题、选分类、
写 Markdown（右侧实时预览），点「导出 .md 文件」，把文件放进 `articles/`，再跑 `python3 src/publish.py`。

**方式 B — 直接写 md**：在 `articles/` 建一个带 frontmatter 的 `.md`，跑 `python3 src/publish.py`。

发布后双击生成的 `dist/index.html` 即可**本地离线打开**；要上线就把它覆盖到根 `index.html` 再 push。
详见 `src/README.md`。

## 目录

| 路径 | 说明 |
|---|---|
| `index.html` | **在线版**：单文件 standalone（内嵌数据 + marked.js），GitHub Pages 直接托管 |
| `articles/` | 放新文章的目录（每篇一个带 frontmatter 的 .md） |
| `src/publish.py` | 一键发布：articles → kb.json → dist/index.html |
| `src/index.template.html` | 前端模板（读同目录 kb.json，本地开发用） |
| `src/kb.json` | 知识库数据 |
| `src/crawl.py` / `src/sync_volc.py` | 全量爬取 / 增量同步火山文档 |
| `src/build_kb.py` / `src/bundle.py` / `src/add.py` | 归类 / 打包 / 命令行新增 |

## 数据来源

火山引擎 DataTester A/B testing 文档库，原文链接形如
`https://www.volcengine.com/docs/6287/<文档ID>`，知识库内每篇均可一键跳转溯源。
内部自有文章标注「✍ 内部自有文章」，与官方内容区分。
