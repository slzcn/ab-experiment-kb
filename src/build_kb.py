#!/usr/bin/env python3
# 把 raw_docs.json 归类成面向"营销广告公司"的知识库 kb.json
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
docs = json.load(open(os.path.join(HERE, "raw_docs.json"), encoding="utf-8"))

# 分类体系：按营销广告团队的使用旅程组织。(顺序即优先级，先命中先归类)
# 每条：(分类key, 图标, 分类名, 一句话说明, [标题关键词/精确id规则])
CATS = [
    ("ad", "📢", "广告投放实验", "面向广告投放场景的实验：广告账户、素材资产、投放优化",
        ["广告", "投放管理", "推荐算法实验", "文案优化实验", "支付链路实验", "会员页实验", "UI 调整实验"]),
    ("cases", "🏆", "实战案例库", "真实增长案例：从业务问题到实验落地的完整打法",
        ["实验｜", "助力游戏", "佛系增长", "逆风翻盘", "揭秘", "关键环节", "带来增长", "带来什么"]),
    ("concept", "💡", "AB通识科普", "什么是AB实验、假设检验、统计学基础——决策者与新人必读",
        ["什么是A/B", "假设检验", "P值", "Power", "科学决策", "以数据为导向", "可能是错的",
         "了解A/B", "基本思想", "统计评估", "产品公开课", "8个错误"]),
    ("design", "📐", "实验设计与规划", "开实验前：如何设计、选类型、算流量、估样本量",
        ["如何设计实验", "开实验前准备", "选择实验类型", "规划实验流量", "预估实验流量",
         "流量层", "流量计算器", "流量建议", "增强分流", "分流模型", "分流 agent",
         "如何配置实验参数", "生效策略", "如何开启", "A/B实验怎么开", "流量平滑"]),
    ("create", "🧪", "创建与管理实验", "各类实验的创建与全生命周期管理",
        ["编程实验", "可视化实验", "多链接实验", "推送实验", "父子实验", "反转实验",
         "MAB", "个性化", "多变体", "模拟实验", "实验模版", "关闭实验组", "实验暂停",
         "实验编辑", "实验固化", "动态变量", "可视化编辑器", "实验版本", "创建常见"]),
    ("report", "📊", "实验报告与分析", "看懂报告、指标分析、高级分析与人群洞察",
        ["报告", "如何看懂", "指标分析", "高级分析", "热力图", "同期群", "差异分析",
         "累计趋势", "过滤模版", "敏感人群", "进组用户", "用户细查", "数据概览", "实验看板"]),
    ("metric", "🎯", "指标体系", "指标组、事件/留存/漏斗指标的建设与管理",
        ["指标组", "新建事件指标", "新建留存指标", "新建漏斗指标", "指标组模版",
         "指标详情", "必看指标", "指标看板", "指标监控", "灵活属性", "虚拟事件", "虚拟属性"]),
    ("data", "🗂️", "数据与埋点", "埋点、事件属性、预置字段、数据集成",
        ["埋点", "预置", "事件属性", "一般事件", "圈选事件", "被动和关系", "数据格式",
         "数据集成", "数据查重", "UBA", "数据集管理", "用户唯一标识", "上报地址", "用户属性",
         "禁用属性", "SQL 自定义", "跨端预置"]),
    ("sdk", "🔌", "SDK与技术集成", "各端SDK接入、调试、开放接口——研发同学看这里",
        ["SDK", "开放接口", "HTTP API", "集成工作台", "嵌入Feature代码", "Applog",
         "PrivacyInfo", "配置和插件", "服务端请求参数", "隐私配置"]),
    ("feature", "🚩", "Feature管理", "Feature Flag 功能开关的创建、调试、发布回滚",
        ["Feature"]),
    ("admin", "⚙️", "配置·权限·计费", "购买配置、权限、审批、系统设置、计费",
        ["权限", "购买与配置", "邀请用户", "审批", "系统设置", "通用设置", "计费", "任务管理",
         "报警任务", "用户分群", "白名单", "扫码录入", "资产迁移", "元数据", "集团", "应用列表",
         "用户管理", "角色管理", "个人资料", "集团信息", "命中实验查询", "命中诊断",
         "找到集团id", "打通", "地域", "云原生", "使用限制", "实验工具箱", "受众"]),
    ("misc", "📎", "上手·协议·其他", "新人上手、发布日志、服务协议等",
        []),  # 兜底
]

def classify(title):
    for key, icon, name, desc, kws in CATS:
        for kw in kws:
            if kw in title:
                return key
    return "misc"

# 归类
cat_meta = {c[0]: {"key": c[0], "icon": c[1], "name": c[2], "desc": c[3]} for c in CATS}
order = [c[0] for c in CATS]

for d in docs:
    d["cat"] = classify(d["title"])

# 统计
from collections import Counter
cnt = Counter(d["cat"] for d in docs)
print("=== 分类分布 ===")
for k in order:
    print(f"  {cat_meta[k]['icon']} {cat_meta[k]['name']}: {cnt.get(k,0)} 篇")

# 生成搜索用纯文本（去掉md标记/html/图片）
def plain(md):
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)          # 图片
    t = re.sub(r"<[^>]+>", "", t)                          # html标签
    t = re.sub(r"```[\s\S]*?```", "", t)                   # 代码块
    t = re.sub(r"[#>*`\|\-]{1,}", " ", t)                  # md符号
    t = re.sub(r"\s+", " ", t)
    return t.strip()

kb = {
    "meta": {
        "source": "火山引擎 DataTester A/B testing 文档库 (LibraryID=6287)",
        "source_url": "https://www.volcengine.com/docs/6287/",
        "total": len(docs),
        "built_for": "营销广告公司内部AB实验知识库",
    },
    "categories": [cat_meta[k] for k in order],
    "docs": [],
}
for d in sorted(docs, key=lambda x: (order.index(x["cat"]), -x["md_len"])):
    kb["docs"].append({
        "id": d["id"],
        "title": d["title"],
        "cat": d["cat"],
        "keywords": d["keywords"],
        "updated": (d.get("updated") or "")[:10],
        "url": d["url"],
        "md": d["md"],
        "text": plain(d["md"]),   # 检索用
    })

# 保留 add.py 加进来的内部自有知识（只存在于已有 kb.json 中）
out = os.path.join(HERE, "kb.json")
if os.path.exists(out):
    prev = json.load(open(out, encoding="utf-8"))
    internal = [d for d in prev.get("docs", []) if d.get("internal")]
    if internal:
        kb["docs"].extend(internal)
        print(f"保留内部自有知识 {len(internal)} 篇")

kb["meta"]["total"] = len(kb["docs"])
json.dump(kb, open(out, "w", encoding="utf-8"), ensure_ascii=False)
print(f"\n写入 {out}  ({os.path.getsize(out)//1024} KB)")
