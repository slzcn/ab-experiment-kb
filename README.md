# A/B 实验知识库 · 营销增长中心

面向营销广告公司内部的 **A/B 实验知识库**。内容整理自火山引擎 DataTester 官方文档库
（共 **203 篇**有正文的文章），按营销团队使用旅程重新归类为 **12 个主题**，支持
**全文检索、分类导航、关键词高亮**，且**每篇都可溯源到官方原文**，并支持持续新增知识。

## 在线访问

GitHub Pages 部署（根目录 `index.html` 为单文件 standalone 版，数据已内嵌，打开即用）。

## 12 个主题

📢 广告投放实验　🏆 实战案例库　💡 AB通识科普　📐 实验设计与规划　🧪 创建与管理实验
📊 实验报告与分析　🎯 指标体系　🗂️ 数据与埋点　🔌 SDK与技术集成　🚩 Feature管理
⚙️ 配置·权限·计费　📎 上手·协议·其他

## 目录

| 路径 | 说明 |
|---|---|
| `index.html` | **在线版**：单文件 standalone（内嵌数据 + marked.js），GitHub Pages 直接托管 |
| `src/index.template.html` | 前端模板（读同目录 kb.json，本地开发用） |
| `src/kb.json` | 知识库数据（分类 + 203 篇正文 + 检索文本 + 溯源链接） |
| `src/crawl.py` | 全量爬取火山文档 |
| `src/sync_volc.py` | 增量同步火山官方更新 |
| `src/build_kb.py` | 重建分类生成 kb.json（自动保留内部知识） |
| `src/add.py` | 新增公司内部自有知识 |
| `src/bundle.py` | 打包成单文件 standalone（部署用） |

维护与新增知识的详细用法见 `src/README.md`。

## 数据来源

火山引擎 DataTester A/B testing 文档库，原文链接形如
`https://www.volcengine.com/docs/6287/<文档ID>`，知识库内每篇均可一键跳转溯源。
