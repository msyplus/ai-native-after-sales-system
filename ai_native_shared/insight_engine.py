"""2.0 自主问题发现引擎 — 从反馈事件中自动聚合优化洞察。

职责：
- 从 feedback_events 和 cases 中聚类出高频问题
- 归因到 5 类 issue_type
- 生成可执行的优化建议
- 纯函数计算，无副作用

依赖：仅使用 Python 3.12 标准库
"""

from datetime import datetime
from typing import Optional

# ── 模块级 ID 计数器 ──
_insight_counter = 0

# ── 5 类 issue_type ──
ISSUE_TYPES = [
    "knowledge_gap",
    "rule_conflict",
    "process_block",
    "prompt_issue",
    "quality_issue",
]

# ── 优先级权重（用于热点分数计算） ──
PRIORITY_WEIGHTS = {"P0": 3, "P1": 2, "P2": 1, "P3": 0}

# ── 关键词映射表（用于聚类过程中判断 issue_type） ──
# 针对 handoff_reason → process_block 的转人工赔付关键词
PROCESS_BLOCK_KEYWORDS = ["赔付", "退款", "情绪", "审批", "限额"]

# ── suggested_action 模板 ──
ACTION_TEMPLATES = {
    "knowledge_gap": (
        "目标：补充知识库「{keyword}」相关条目。\n"
        "动作：梳理事件涉及的 {count} 个 case，归纳标准话术或 FAQ，"
        "更新 knowledge_base.py 或外部知识库。"
    ),
    "rule_conflict": (
        "目标：修订「{keyword}」相关 SOP 的规则优先级。\n"
        "动作：梳理 {count} 个 case 中的规则冲突场景，"
        "明确规则优先级顺序或合并互斥规则。"
    ),
    "process_block": (
        "目标：优化「{keyword}」相关流程。\n"
        "动作：分析 {count} 个 case 中的重复卡点原因，"
        "考虑增加前置校验、优化追问策略或简化流程。"
    ),
    "prompt_issue": (
        "目标：调整「{keyword}」相关场景的追问策略。\n"
        "动作：回顾 {count} 个 case 中追问失败的模式，"
        "优化追问话术、降低单轮追问信息密度，"
        "或增加用户可选字段列表。"
    ),
    "quality_issue": (
        "目标：改进「{keyword}」场景的话术或质检标准。\n"
        "动作：分析 {count} 个 case 中低分原因，"
        "参考评分维度和业务目标调整话术模板或质检评分规则。"
    ),
}

# ── 规则冲突关键词 ──
RULE_CONFLICT_KEYWORDS = [
    "多个规则", "规则冲突", "同时命中", "规则矛盾",
    "rule conflict", "multiple rules",
]


def _gen_insight_id() -> str:
    """生成唯一 insight_id，格式 INSIGHT-YYYYMMDD-NNNN。"""
    global _insight_counter
    _insight_counter += 1
    today = datetime.now().strftime("%Y%m%d")
    return f"INSIGHT-{today}-{_insight_counter:04d}"


def _normalize_description(desc: str) -> str:
    """标准化 description：去除首尾空格。"""
    return desc.strip() if desc else ""


def _cluster_by_keyword(
    events: list[dict],
    event_type_filter: str,
    keyword_extract_len: int = 30,
) -> dict[str, list[dict]]:
    """按事件 description 聚类。

    Args:
        events: 全部反馈事件。
        event_type_filter: 要筛选的事件类型。
        keyword_extract_len: 从 description 提取关键词的字符长度。

    Returns:
        {关键词前缀: [事件列表]}
    """
    clusters: dict[str, list[dict]] = {}
    for ev in events:
        if ev.get("event_type") != event_type_filter:
            continue
        desc = _normalize_description(ev.get("description", ""))
        if not desc:
            continue
        # 取前 keyword_extract_len 个字符作为 bucket 键
        bucket = desc[:keyword_extract_len]
        clusters.setdefault(bucket, []).append(ev)
    return clusters


def _assign_priority(events: list[dict]) -> str:
    """取一组事件中最高的 priority。"""
    rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    best = "P3"
    best_rank = 99
    for ev in events:
        pri = ev.get("priority", "P2")
        r = rank.get(pri, 99)
        if r < best_rank:
            best_rank = r
            best = pri
    return best


def _default_id(case_id: str | None) -> str:
    return case_id or ""


def _extract_keyword_from_bucket(bucket: str) -> str:
    """从 bucket key 中提取展示用的关键词。"""
    # 简单地取前 20 个字符
    return bucket[:20].strip()


def _classify_handoff_to_issue_type(description: str) -> str:
    """根据 handoff_reason 的 description 判断是 rule_conflict 还是 process_block。"""
    desc_lower = description.lower()
    for kw in RULE_CONFLICT_KEYWORDS:
        if kw in desc_lower or kw in description:
            return "rule_conflict"
    return "process_block"


def generate_insights(
    feedback_events: list[dict],
    cases: list[dict],
) -> list[dict]:
    """从反馈事件和 case 数据中聚合出优化洞察（insights）。

    Args:
        feedback_events: feedback_store.get_events() 返回的完整事件列表。
        cases: case_store.list_cases() 返回的 case 列表。

    Returns:
        list[dict]，每条 dict 包含以下字段：
            - id: str, 唯一标识，格式 "INSIGHT-YYYYMMDD-NNNN"
            - issue_type: str, 5 种类型之一
            - title: str, 概括性标题
            - description: str, 详细描述，包含聚类关键词和统计信息
            - source_events_count: int, 参与聚合的事件数
            - priority: str, "P0" | "P1" | "P2"
            - hot_score: float, count × weight (P0=3, P1=2, P2=1)
            - suggested_action: str, 可执行建议
            - related_case_ids: list[str], 关联的 case_id 列表
            - created_at: str, 生成时间 "YYYY-MM-DD HH:mm"
    """
    if not feedback_events:
        return []

    # 收集所有 case_id 用于关联（去重）
    all_case_ids: set[str] = set()
    for ev in feedback_events:
        cid = ev.get("case_id")
        if cid:
            all_case_ids.add(str(cid))

    insights: list[dict] = []

    # ── 1. knowledge_miss → knowledge_gap ──
    km_clusters = _cluster_by_keyword(feedback_events, "knowledge_miss")
    for bucket, ev_list in km_clusters.items():
        count = len(ev_list)
        if count < 2:
            continue
        priority = _assign_priority(ev_list)
        keyword = _extract_keyword_from_bucket(bucket)
        related_ids = list({_default_id(e.get("case_id")) for e in ev_list if e.get("case_id")})
        insights.append({
            "id": _gen_insight_id(),
            "issue_type": "knowledge_gap",
            "title": f"知识缺口：{keyword}",
            "description": f"检测到 {count} 次知识未命中事件，均涉及「{keyword}」相关查询。",
            "source_events_count": count,
            "priority": priority,
            "hot_score": count * PRIORITY_WEIGHTS.get(priority, 1),
            "suggested_action": ACTION_TEMPLATES["knowledge_gap"].format(
                keyword=keyword, count=count
            ),
            "related_case_ids": related_ids,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    # ── 2. inquiry_failure → prompt_issue ──
    if_clusters = _cluster_by_keyword(feedback_events, "inquiry_failure")
    for bucket, ev_list in if_clusters.items():
        count = len(ev_list)
        if count < 2:
            continue
        priority = _assign_priority(ev_list)
        keyword = _extract_keyword_from_bucket(bucket)
        related_ids = list({_default_id(e.get("case_id")) for e in ev_list if e.get("case_id")})
        insights.append({
            "id": _gen_insight_id(),
            "issue_type": "prompt_issue",
            "title": f"追问策略问题：{keyword}",
            "description": f"检测到 {count} 次追问失败事件，均涉及「{keyword}」相关场景。",
            "source_events_count": count,
            "priority": priority,
            "hot_score": count * PRIORITY_WEIGHTS.get(priority, 1),
            "suggested_action": ACTION_TEMPLATES["prompt_issue"].format(
                keyword=keyword, count=count
            ),
            "related_case_ids": related_ids,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    # ── 3. handoff_reason → process_block 或 rule_conflict ──
    hr_clusters = _cluster_by_keyword(feedback_events, "handoff_reason")
    for bucket, ev_list in hr_clusters.items():
        count = len(ev_list)
        if count < 2:
            continue
        # 根据描述判断是 rule_conflict 还是 process_block
        issue_type = _classify_handoff_to_issue_type(bucket)
        priority = _assign_priority(ev_list)
        keyword = _extract_keyword_from_bucket(bucket)
        related_ids = list({_default_id(e.get("case_id")) for e in ev_list if e.get("case_id")})
        insights.append({
            "id": _gen_insight_id(),
            "issue_type": issue_type,
            "title": f"{'流程卡点' if issue_type == 'process_block' else '规则冲突'}：{keyword}",
            "description": f"检测到 {count} 次转人工事件，均涉及「{keyword}」相关场景。",
            "source_events_count": count,
            "priority": priority,
            "hot_score": count * PRIORITY_WEIGHTS.get(priority, 1),
            "suggested_action": ACTION_TEMPLATES[issue_type].format(
                keyword=keyword, count=count
            ),
            "related_case_ids": related_ids,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    # ── 4. quality_low_score → quality_issue ──
    ql_clusters = _cluster_by_keyword(feedback_events, "quality_low_score")
    for bucket, ev_list in ql_clusters.items():
        count = len(ev_list)
        if count < 2:
            continue
        priority = _assign_priority(ev_list)
        keyword = _extract_keyword_from_bucket(bucket)
        related_ids = list({_default_id(e.get("case_id")) for e in ev_list if e.get("case_id")})
        insights.append({
            "id": _gen_insight_id(),
            "issue_type": "quality_issue",
            "title": f"质检低分热点：{keyword}",
            "description": f"检测到 {count} 次质检低分事件，均涉及「{keyword}」相关场景。",
            "source_events_count": count,
            "priority": priority,
            "hot_score": count * PRIORITY_WEIGHTS.get(priority, 1),
            "suggested_action": ACTION_TEMPLATES["quality_issue"].format(
                keyword=keyword, count=count
            ),
            "related_case_ids": related_ids,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    return insights
