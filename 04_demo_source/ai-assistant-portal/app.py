"""
AI native 售后服务系统控制台 — 生产型统一入口
=================================================================

主需求是可应用于真实生产环境的售后服务功能闭环，面试展示只是次级需求。
系统由 1 个对客沟通输入端、5 个业务能力模块和 1 个统一控制台组成。
"""

import os as _os
import sys

# ---------- path setup ----------
# 本地: D:/job3.0/
# 线上 Streamlit Cloud: /mount/src/ai-native-after-sales-system/
_SHARED = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

import streamlit as st
from datetime import datetime
import json

# ---------- 导入共享模块，带调试保护 ----------
try:
    from ai_native_shared.case_store import list_cases, count_cases, get_case, export_cases_as_json
    from ai_native_shared.metrics_engine import compute_metrics
    from ai_native_shared.feedback_store import get_events, count_by_type, count_by_priority, get_unresolved, resolve_event
    from ai_native_shared.insight_engine import generate_insights
except ImportError as _e:
    st.error(f"导入 ai_native_shared 失败: {_e}")
    st.info(f"当前 sys.path: {sys.path}")
    st.info(f"__file__: {__file__}")
    st.info(f"SHARED_PATH: {_SHARED}")
    st.stop()

st.set_page_config(
    page_title="AI native 售后服务系统控制台",
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SYSTEMS = [
    {
        "name": "对客沟通机器人",
        "short": "对客输入",
        "version": "v1.0",
        "value": "承接客户自然语言问题，多轮追问必要字段，生成统一 case，识别风险并转人工。",
        "evidence": "系统信息输入端 — 补足对客 Agent 设计能力。不作为已有生产经验，展示的是对客沟通链路、风险边界和产品验证能力。",
        "features": ["自然语言输入", "多轮追问", "知识引用", "高风险转人工", "case 上下文"],
        "scenario": "客户用自然语言描述售后问题后，系统先识别意图和风险，追问必要字段，再决定标准回答或转人工。",
        "analysis": "把客户原始表达转成意图、槽位、风险标签、知识依据和下一步动作。",
        "output": "case_id、customer_intent、required_slots、risk_tags、knowledge_refs、handoff_summary、next_action。",
        "tooling": "规则引擎负责意图识别和风险标签，知识库检索提供 SOP 依据，高风险场景标记人工确认边界。",
        "url": "https://customer-agent-demo.streamlit.app",
    },
    {
        "name": "VOC 智能分类与优先级评估",
        "short": "分类",
        "version": "v3.2",
        "value": "将客诉文本转化为类别、情绪、优先级和处理建议，帮助一线快速分流。",
        "evidence": "对应携程 AI 智能化投诉系统与投诉业务分类经验。",
        "features": ["规则/AI 双引擎", "优先级评估", "批量异常检测", "可视化看板"],
        "scenario": "一线接到大量客诉后，需要快速判断问题类型、紧急程度和处理方向。",
        "analysis": "把非结构化文本拆成分类标签、情绪、优先级和建议动作。",
        "output": "分类结果、优先级、处理建议、异常聚集提示。",
        "tooling": "规则引擎负责稳定分类兜底，AI 模型负责语义理解和复杂表达判断，人工负责低置信度复核。",
        "url": "https://complaint-classifier-demo.streamlit.app",
    },
    {
        "name": "批量异常识别与服务风险预警",
        "short": "预警",
        "version": "v3.2",
        "value": "识别 VOC 聚集、敏感风险和时间异常，把潜在舆情从事后复盘前移到事中预警。",
        "evidence": "对应携程智慧预警平台与拼多多批量异常客诉处理经验。",
        "features": ["统计聚类", "敏感词识别", "时间异常检测", "风险报告"],
        "scenario": "运营需要从大量用户声音中发现正在聚集的问题，而不是逐条人工阅读。",
        "analysis": "把 VOC 拆成事件类型、聚集程度、时间异常、升级风险和影响范围。",
        "output": "异常主题、风险等级、趋势判断、响应建议和 Markdown 报告。",
        "tooling": "统计聚类发现聚集，敏感词规则识别确定性风险，AI 引擎补充语义聚类和根因总结。",
        "url": "https://voc-risk-detector-demo.streamlit.app",
    },
    {
        "name": "客服对话质量评估",
        "short": "质检",
        "version": "v3.2",
        "value": "围绕识别需求、有效共情、达成一致、承诺回复四个维度评估服务质量。",
        "evidence": "对应携程 AI 质检平台的业务侧评估标准设计。",
        "features": ["四维评分", "规则/AI 评估", "雷达图", "问题定位"],
        "scenario": "质检团队需要把主观的服务好不好拆成可复核、可训练的评价标准。",
        "analysis": "把对话质量拆成需求识别、共情、方案一致和承诺回复四个维度。",
        "output": "维度评分、问题定位、改进话术和 badcase 清单。",
        "tooling": "规则标准保证评分口径稳定，AI 负责理解对话语义，人工质检负责争议样本复核。",
        "url": "https://cs-quality-evaluator-demo.streamlit.app",
    },
    {
        "name": "服务事件智能摘要",
        "short": "摘要",
        "version": "v2.0",
        "value": "把对话、日志和备注压缩为结构化摘要，降低工单录入和复盘分析成本。",
        "evidence": "对应携程 AI 自动总结项目，复现 Prompt 约束和格式化输出思路。",
        "features": ["多源输入", "实体提取", "结构化摘要", "人工评分反馈"],
        "scenario": "客服处理后需要把分散对话和操作记录整理成后续角色可读的信息。",
        "analysis": "把长文本拆成事件类型、关键事实、用户诉求、处理动作和待跟进事项。",
        "output": "结构化摘要、风险等级、关键词保留率和人工评分反馈。",
        "tooling": "Prompt 约束输出结构，规则提取关键字段，人工评分反馈用于判断摘要是否可用。",
        "url": "https://summary-system-demo.streamlit.app",
    },
    {
        "name": "客服 SOP 知识库问答",
        "short": "RAG",
        "version": "v1.0",
        "value": "把服务 SOP、质检标准和风险规则转为可检索知识库，输出带引用依据的处理建议。",
        "evidence": "用于补齐 RAG / 知识库应用证据，展示从规则文档到问答原型的产品转译能力。",
        "features": ["文档切分", "TF-IDF 检索", "引用依据", "结构化回答"],
        "scenario": "一线或主管需要快速找到 SOP、风险规则和质检标准中的依据。",
        "analysis": "把知识文档拆成可检索片段，并将问题匹配到相关规则和历史口径。",
        "output": "引用依据、判断逻辑、建议动作和人工确认边界。",
        "tooling": "检索负责找依据，生成负责组织回答，人工负责确认规则适用性和高风险边界。",
        "url": "https://service-rag-msydemo.streamlit.app",
    },
    {
        "name": "AI native 售后服务系统控制台",
        "short": "控制台",
        "version": "v1.0",
        "value": "统一展示对客输入、分类、预警、质检、摘要和知识服务，作为系统总入口。",
        "evidence": "把分散 demo 串成一个售后服务系统合集，强调信息流、判断流、人机分工和反馈闭环。",
        "features": ["统一入口", "模块导航", "链路说明", "价值指标", "闭环展示"],
        "scenario": "服务负责人或面试官从控制台进入各模块，理解系统如何从客户输入走到人工接管和反馈优化。",
        "analysis": "把单点能力组织成可解释、可验证的 AI native 售后服务工作流。",
        "output": "模块入口、工作流、核心指标、1.0/2.0 演进说明。",
        "tooling": "控制台不替代业务模块，负责组织入口、表达系统边界和串联验证路径。",
        "url": "https://ai-native-system-msydemo.streamlit.app",
    },
]

WORKFLOW = [
    ("1", "对客输入", "承接客户自然语言问题，识别意图，多轮追问必要字段"),
    ("2", "统一 case", "生成 case_id 和结构化上下文，贯穿后续所有模块"),
    ("3", "知识引用", "RAG 检索 SOP/规则/政策依据，证据不足时不强答"),
    ("4", "风险判断", "识别监管、赔付、舆情等高风险，触发人工接管"),
    ("5", "摘要/质检", "生成服务摘要，按 case_id 做四维质检评分"),
    ("6", "回流优化", "记录 badcase、知识未命中、转人工原因，驱动迭代"),
]


def inject_css():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2.2rem; padding-bottom: 2.5rem; }
        .hero {
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            padding: 28px 30px;
            background: #f8fafc;
        }
        .hero h1 {
            margin: 0 0 10px 0;
            font-size: 34px;
            letter-spacing: 0;
            color: #102a43;
        }
        .hero p {
            margin: 0;
            color: #52606d;
            font-size: 16px;
            line-height: 1.7;
        }
        .section-title {
            font-size: 22px;
            font-weight: 700;
            color: #102a43;
            margin: 18px 0 10px 0;
        }
        .workflow-step {
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            padding: 14px;
            min-height: 124px;
            background: white;
        }
        .workflow-index {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            background: #0f766e;
            color: white;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .system-card {
            border: 1px solid #d9e2ec;
            border-radius: 8px;
            padding: 20px;
            background: white;
            min-height: 290px;
        }
        .system-card h3 {
            margin-top: 0;
            color: #102a43;
            font-size: 20px;
        }
        .muted { color: #627d98; font-size: 14px; line-height: 1.65; }
        .tag {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 6px;
            background: #e6fffa;
            color: #0f766e;
            font-size: 13px;
            margin: 0 6px 6px 0;
            border: 1px solid #b2f5ea;
        }
        .demo-button {
            display: block;
            text-align: center;
            padding: 10px 12px;
            border-radius: 8px;
            background: #0f766e;
            color: white !important;
            text-decoration: none;
            font-weight: 700;
            margin-top: 16px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero():
    st.markdown(
        """
        <div class="hero">
            <h1>AI native 售后服务系统控制台</h1>
            <p>
            主需求是可应用于真实生产环境的售后服务功能闭环，面试展示只是次级需求。
            系统由 1 个对客沟通输入端、5 个业务能力模块和 1 个统一控制台组成。
            生产链路：对客输入 → 统一 case → 知识引用 → 风险判断 → 摘要/质检 → 回流优化。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics():
    st.markdown('<div class="section-title">1.0 生产指标面板</div>', unsafe_allow_html=True)
    cols = st.columns(6)
    cols[0].metric("自动解决率", "≈ 45%", "目标 ≥ 50%")
    cols[1].metric("转人工率", "≈ 30%", "目标 ≤ 25%")
    cols[2].metric("字段完整率", "≈ 60%", "目标 ≥ 80%")
    cols[3].metric("知识命中率", "≈ 75%", "目标 ≥ 85%")
    cols[4].metric("人工接管时长", "≈ 8 min", "目标 ≤ 5 min")
    cols[5].metric("客户重复描述率", "≈ 15%", "目标 ≤ 10%")


def render_workflow():
    st.markdown('<div class="section-title">1.0 生产工作流链路</div>', unsafe_allow_html=True)
    cols = st.columns(6)
    for col, (index, title, desc) in zip(cols, WORKFLOW):
        with col:
            st.markdown(
                f"""
                <div class="workflow-step">
                    <div class="workflow-index">{index}</div>
                    <div><strong>{title}</strong></div>
                    <div class="muted">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_system_card(system):
    tags = "".join(f'<span class="tag">{feature}</span>' for feature in system["features"])
    st.markdown(
        f"""
        <div class="system-card">
            <h3>{system["short"]} · {system["name"]}</h3>
            <div class="muted"><strong>{system["version"]}</strong> | 本地 Streamlit | 默认规则引擎无需 API Key</div>
            <p>{system["value"]}</p>
            <div class="muted"><strong>使用场景：</strong>{system["scenario"]}</div>
            <div class="muted"><strong>分析需求：</strong>{system["analysis"]}</div>
            <div class="muted"><strong>功能输出：</strong>{system["output"]}</div>
            <div class="muted"><strong>AI/工具调配：</strong>{system["tooling"]}</div>
            <div class="muted">{system["evidence"]}</div>
            <div style="margin-top:14px;">{tags}</div>
            <a class="demo-button" href="{system["url"]}" target="_blank">打开模块</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_systems():
    st.markdown('<div class="section-title">1.0 系统模块</div>', unsafe_allow_html=True)
    for row_start in range(0, len(SYSTEMS), 2):
        cols = st.columns(2)
        for offset, col in enumerate(cols):
            index = row_start + offset
            if index < len(SYSTEMS):
                with col:
                    render_system_card(SYSTEMS[index])


def render_notes():
    st.markdown('<div class="section-title">1.0 与 2.0 版本路线</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown(
                """
                **1.0：生产可落地版本**

                - ✅ 对客沟通机器人（系统信息输入端）
                - ✅ 统一 case_id 和结构化上下文
                - ✅ RAG 知识引用和证据不足不强答
                - ✅ 高风险转人工 + 转人工包
                - ✅ 服务摘要 + 结构质检
                - ✅ 基础监控指标
                - ✅ badcase 回流记录
                """
            )
    with col2:
        with st.container(border=True):
            st.markdown(
                """
                **2.0：自主优化版本（规划）**

                - 🔲 自主问题发现（聚合重复咨询和知识未命中）
                - 🔲 自动归因（知识缺口/规则冲突/流程卡点/话术问题）
                - 🔲 优化建议生成（知识补充/SOP修订/Prompt调整）
                - 🔲 反馈闭环看板（发现→归因→动作→验证）
                - 🔲 追问策略自优化 + 知识健康自检
                - 🔲 灰度验证和回滚机制
                """
            )

    st.markdown('<div class="section-title">产品思维拆解方式</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            """
            | 产品拆解层 | 展示重点 |
            |---|---|
            | 业务场景 | 谁在什么业务节点遇到什么问题 |
            | 功能需求 | 需要系统判断、提取、监控或沉淀什么 |
            | AI/工具调配 | 哪些交给规则，哪些交给 AI，哪些保留人工复核 |
            | 输出设计 | 给一线、主管或运营什么结果，是否可导出、可复盘 |
            | 验证指标 | 用准确性、误伤/漏报、处理时长、人工修改原因或保留比例验证 |
            """
        )

    st.markdown('<div class="section-title">使用说明</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            """
            - 默认规则/统计引擎无需 API Key，可直接展示完整流程。
            - 样例数据为模拟/脱敏数据，不包含真实用户隐私。
            - 本系统以真实生产可落地为目标，面试展示只是次级需求。
            - 不接真实客服系统、CRM 或用户数据，不包装成已有生产上线经验。
            """
        )


def render_case_list_page():
    """Case 列表页 — 筛选、搜索、查看详情、导出。"""
    st.subheader("📋 Case 列表")

    # ── 筛选栏 ──
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        intent_filter = st.selectbox(
            "意图筛选",
            ["全部", "refund_compensation_complaint", "logistics_inquiry",
             "regulatory_complaint", "general_inquiry"],
            key="cs_intent",
        )
    with col2:
        risk_filter = st.text_input("🏷️ 风险标签筛选", placeholder="如 compensation", key="cs_risk")
    with col3:
        date_from = st.date_input("开始日期", value=None, key="cs_df")
    with col4:
        date_to = st.date_input("结束日期", value=None, key="cs_dt")

    # ── 构建筛选参数 ──
    params = {}
    if intent_filter and intent_filter != "全部":
        params["intent_filter"] = intent_filter
    if risk_filter:
        params["risk_filter"] = risk_filter
    if date_from:
        params["date_from"] = date_from.strftime("%Y-%m-%d")
    if date_to:
        params["date_to"] = date_to.strftime("%Y-%m-%d")

    # ── 分页 ──
    PAGE_SIZE = 20
    total = count_cases(**params)
    max_page = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.number_input("页码", min_value=1, max_value=max_page, value=1, key="cs_page")
    offset = (page - 1) * PAGE_SIZE

    cases = list_cases(limit=PAGE_SIZE, offset=offset, **params)

    if not cases:
        st.info("暂无 case 记录。请先在「对客沟通机器人」中处理客户问题。")
        # ── 导出按钮（仅在有数据时显示） ──
        return

    # ── 统计条 ──
    st.caption(f"共 {total} 条记录，当前显示 {len(cases)} 条")

    # ── 表格展示 ──
    for c in cases:
        with st.container(border=True):
            cols = st.columns([2, 3, 2, 2, 3])
            with cols[0]:
                expand_label = c["case_id"]
                st.markdown(f"**{expand_label}**")
            cols[1].markdown(
                c.get("customer_message", c.get("conversation", [{}])[0].get("content", ""))[:80] + "..."
                if c.get("customer_message") or c.get("conversation") else "—"
            )
            cols[2].markdown(f"`{c.get('customer_intent', '—')}`")

            # 风险标签
            risk_tags = c.get("risk_tags", [])
            if risk_tags:
                risk_str = ", ".join(risk_tags[:2])
                if len(risk_tags) > 2:
                    risk_str += "…"
                cols[3].markdown(f"⚠️ {risk_str}")
            else:
                cols[3].markdown("—")

            cols[4].markdown(f"🕐 {c.get('created_at', '—')}")

            # 展开详情
            with st.expander("查看完整 Case 上下文"):
                st.json(c)

    # ── 导出按钮 ──
    if st.button("📥 导出当前筛选结果为 JSON"):
        json_str = json.dumps(cases, ensure_ascii=False, indent=2)
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "下载 JSON",
            json_str,
            file_name=f"cases_export_{now_str}.json",
            mime="application/json",
        )


def render_metrics_page():
    """生产指标面板 — 基于持久化 case 数据实时计算"""
    st.subheader("📊 生产指标")
    st.caption("基于 case_store 中持久化的 case 数据实时计算")

    # 读取全部 case
    cases = list_cases(limit=1000)

    if not cases or len(cases) < 3:
        st.info("等待更多数据积累。至少需要 3 条 case 才能展示有意义的指标。")
        st.caption(f"当前共 {len(cases)} 条 case")
        return

    metrics = compute_metrics(cases)

    # 顶部 KPI 卡片（4 列）
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("自动解决率", f"{metrics['auto_resolve_rate']:.1f}%",
                help="next_action=standard_answer 的 case 占比")
    col2.metric("转人工率", f"{metrics['handoff_rate']:.1f}%",
                help="next_action=human_handoff 的 case 占比")
    col3.metric("知识命中率", f"{metrics['knowledge_hit_rate']:.1f}%",
                help="knowledge_refs 非空的 case 占比")
    col4.metric("字段完整率", f"{metrics['field_completion_rate']:.1f}%",
                help="所有 case 的槽位收集完整度均值")

    st.caption(f"基于 {metrics['total_cases']} 条 case 计算")

    # 转人工原因分布
    if metrics.get("handoff_reasons"):
        st.subheader("🔄 转人工原因分布")
        st.bar_chart(metrics["handoff_reasons"])

    # 风险标签分布
    if metrics.get("risk_tag_distribution"):
        st.subheader("⚠️ 风险标签分布")
        st.bar_chart(metrics["risk_tag_distribution"])

    # 每日 case 趋势
    if metrics.get("daily_case_trends"):
        st.subheader("📈 每日 Case 趋势")
        st.line_chart(metrics["daily_case_trends"])

    # 底部指标说明
    with st.expander("📋 指标定义与口径"):
        st.markdown("""
        | 指标 | 定义 | 数据来源 |
        |------|------|----------|
        | 自动解决率 | next_action=standard_answer 的 case / 总 case | case_store.next_action |
        | 转人工率 | next_action=human_handoff 的 case / 总 case | case_store.next_action |
        | 知识命中率 | knowledge_refs 非空的 case / 总 case | case_store.knowledge_refs |
        | 字段完整率 | 所有 case 的 provided_slots / total_slots 均值 | case_store.slot_status |
        | 转人工原因 | handoff_reason 类 feedback_event 的分组计数 | case_store.feedback_events |
        | 风险标签 | risk_tags 中每个标签的出现次数 | case_store.risk_tags |
        | 每日趋势 | 按 created_at 日期聚合的 case 数量 | case_store.created_at |
        """)


def render_feedback_events_page():
    """反馈事件页面 — 展示、筛选、标记解决。"""
    st.subheader("📝 反馈事件")

    # ── 顶部 KPI 栏 ──
    type_counts = count_by_type()
    priority_counts = count_by_priority()
    unresolved = get_unresolved(limit=1)
    total = sum(type_counts.values()) if type_counts else 0
    unresolved_count = len(unresolved) if unresolved else 0

    if total == 0:
        st.info("暂无反馈事件。请先在「对客沟通机器人」中处理客户问题产生反馈。")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("事件总数", total)
    col2.metric("未解决数", unresolved_count)
    with col3:
        if type_counts:
            top_type = max(type_counts, key=type_counts.get)
            st.metric("最多类型", f"{top_type} ({type_counts[top_type]})")

    st.markdown("---")

    # ── 筛选栏 ──
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        event_type_filter = st.selectbox(
            "事件类型",
            ["全部", "knowledge_miss", "handoff_reason", "human_rewrite",
             "quality_low_score", "inquiry_failure"],
            key="fb_type",
        )
    with col2:
        priority_filter = st.selectbox(
            "优先级",
            ["全部", "P0", "P1", "P2", "P3"],
            key="fb_pri",
        )
    with col3:
        case_id_filter = st.text_input("Case ID", placeholder="输入 case_id 筛选", key="fb_case")
    with col4:
        resolved_filter = st.selectbox(
            "解决状态",
            ["全部", "未解决", "已解决"],
            key="fb_res",
        )

    # ── 构建查询参数 ──
    params = {}
    if event_type_filter and event_type_filter != "全部":
        params["event_type"] = event_type_filter
    if priority_filter and priority_filter != "全部":
        params["priority"] = priority_filter
    if case_id_filter and case_id_filter.strip():
        params["case_id"] = case_id_filter.strip()
    if resolved_filter == "未解决":
        params["is_resolved"] = 0
    elif resolved_filter == "已解决":
        params["is_resolved"] = 1

    # ── 分页 ──
    PAGE_SIZE = 20
    filter_params = {k: v for k, v in params.items()
                     if k in ("event_type", "priority", "is_resolved", "case_id")}
    all_events = get_events(limit=1000, **filter_params)
    total = len(all_events)
    max_page = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.number_input("页码", min_value=1, max_value=max_page, value=1,
                           key="fb_page")
    offset = (page - 1) * PAGE_SIZE

    events = get_events(limit=PAGE_SIZE, offset=offset, **filter_params)

    if not events:
        st.caption("没有匹配的事件。")
        return

    st.caption(f"共 {total} 条记录，当前显示 {len(events)} 条（按创建时间倒序）")

    # ── 事件列表 ──
    for ev in events:
        priority_label = {"P0": "🔴 P0", "P1": "🟠 P1", "P2": "🟡 P2", "P3": "🟢 P3"}
        resolved_label = "✅ 已解决" if ev["is_resolved"] else "⏳ 未解决"

        with st.container(border=True):
            cols = st.columns([1, 3, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{priority_label.get(ev['priority'], ev['priority'])}**")
            with cols[1]:
                st.markdown(f"**{ev['event_type']}** — {ev['description'][:120]}")
                st.caption(f"来源: {ev['source_module']} | Case: `{ev['case_id']}` | {ev['created_at']}")
            with cols[2]:
                st.markdown(f"根因: {ev.get('root_cause', '—')}")
            with cols[3]:
                st.markdown(resolved_label)
            with cols[4]:
                if not ev["is_resolved"]:
                    if st.button("✅ 标记解决", key=f"resolve_{ev['id']}"):
                        resolve_event(ev["id"])
                        st.rerun()

            with st.expander("查看详情"):
                if ev.get("suggested_action"):
                    st.markdown(f"**建议动作**: {ev['suggested_action']}")
                st.json(dict(ev))


def render_insights_page():
    """2.0 优化任务页面 — 展示自动聚合的优化洞察。"""
    st.subheader("🔍 2.0 优化任务 — 自主问题发现")
    st.caption("基于 feedback_store 和 case_store 数据自动聚合，发现优化机会。")

    # 1. 读取数据
    feedback_events = get_events(limit=5000)

    if not feedback_events:
        st.info("暂无反馈事件数据。请在「对客沟通机器人」中处理客户问题，积累足够数据后自动生成洞察。")
        return

    # 2. 读取 cases（用于关联）
    cases = list_cases(limit=1000)

    # 3. 生成 insights
    insights = generate_insights(feedback_events, cases)

    # 4. 展示
    if not insights:
        st.info("当前数据未发现显著模式。至少需要同一类型事件出现 2 次以上才会生成优化任务。")
        return

    # 5. 顶部分类统计
    type_counts = {}
    for ins in insights:
        t = ins["issue_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    type_labels = {
        "knowledge_gap": "📚 知识缺口",
        "rule_conflict": "⚠️ 规则冲突",
        "process_block": "🔒 流程卡点",
        "prompt_issue": "💬 追问策略",
        "quality_issue": "⭐ 质检低分",
    }

    cols = st.columns(5)
    for col, (t, label) in zip(cols, type_labels.items()):
        with col:
            count = type_counts.get(t, 0)
            st.metric(label, count)

    st.markdown("---")

    # 6. 列表展示（按热点分数排序）
    priority_weight = {"P0": 3, "P1": 2, "P2": 1}

    def hotscore(ins):
        return ins["source_events_count"] * priority_weight.get(ins["priority"], 1)

    sorted_insights = sorted(insights, key=hotscore, reverse=True)

    for ins in sorted_insights:
        with st.container(border=True):
            priority_label = {"P0": "🔴 P0", "P1": "🟠 P1", "P2": "🟡 P2"}
            issue_icon = type_labels.get(ins["issue_type"], "📌")

            cols = st.columns([2, 1, 1, 1, 1, 2])
            with cols[0]:
                st.markdown(f"**{issue_icon} {ins['title']}**")
                st.caption(f"类型: {ins['issue_type']} | ID: {ins['id']}")
            with cols[1]:
                st.markdown(f"📄 {ins['description'][:100]}…" if len(ins['description']) > 100 else f"📄 {ins['description']}")
            with cols[2]:
                st.markdown(f"**{ins['source_events_count']}** 个事件")
            with cols[3]:
                st.markdown(priority_label.get(ins["priority"], ins["priority"]))
            with cols[4]:
                score = hotscore(ins)
                st.markdown(f"🔥 热点分: {score}")
            with cols[5]:
                st.markdown(f"💡 {ins['suggested_action'][:60]}…")

            # 折叠展开
            with st.expander("查看建议动作和关联 Case"):
                st.markdown(f"**💡 建议动作**: {ins['suggested_action']}")
                if ins.get("related_case_ids"):
                    st.markdown(f"**🔗 关联 Case**: {', '.join(ins['related_case_ids'][:10])}")
                    if len(ins["related_case_ids"]) > 10:
                        st.caption(f"...以及另外 {len(ins['related_case_ids']) - 10} 个 case")
                st.json(ins)


def main():
    inject_css()
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 控制台", "📋 Case 列表", "📊 生产指标", "📝 反馈事件", "🔍 2.0 优化任务"])
    with tab1:
        render_hero()
        st.write("")
        render_metrics()
        render_workflow()
        render_systems()
        render_notes()
    with tab2:
        render_case_list_page()
    with tab3:
        render_metrics_page()
    with tab4:
        render_feedback_events_page()
    with tab5:
        render_insights_page()
    st.caption("本地 Streamlit 应用需先运行 start-local-demos.bat 启动各模块。")


if __name__ == "__main__":
    main()
