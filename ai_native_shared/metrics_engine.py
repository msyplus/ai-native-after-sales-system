"""
生产指标计算引擎 — 基于 case_store 持久化数据实时聚合
=================================================================

7 项核心指标：
1. 自动解决率 (auto_resolve_rate)
2. 转人工率 (handoff_rate)
3. 知识命中率 (knowledge_hit_rate)
4. 字段完整率 (field_completion_rate)
5. 转人工原因分布 (handoff_reasons)
6. 风险标签分布 (risk_tag_distribution)
7. 每日 case 趋势 (daily_case_trends)

重要说明：
- case_store 的 save_case 只写入了有限字段到 SQLite（未保留 next_action 即列）。
- next_action 实际存储在 state_history 最后一条记录中。
- 本引擎自动从 state_history 回退提取 next_action。
- JSON 字段在 case_store._serialize_row 中已自动反序列化，本引擎也兼容原始 JSON 字符串。

依赖：仅使用标准库（json）
"""

import json


def _ensure_deserialized(val):
    """确保 JSON 字段已反序列化。

    case_store._serialize_row 已自动反序列化 JSON 字段，
    但本函数作为防御性处理，兼容原始字符串和已解析对象。
    """
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


def _get_next_action(case: dict) -> str:
    """获取 case 的 next_action。

    优先从顶层字段获取（如果未来 save_case 加了该列），
    否则从 state_history 最后一条回退提取。
    """
    action = case.get("next_action")
    if action and isinstance(action, str):
        return action

    state_history = _ensure_deserialized(case.get("state_history", []))
    if isinstance(state_history, list) and state_history:
        last_state = state_history[-1]
        if isinstance(last_state, dict):
            return last_state.get("next_action", "")
    return ""


def compute_metrics(cases: list[dict]) -> dict:
    """从一批 case 数据中计算生产指标。

    Args:
        cases: case_store.list_cases() 返回的 dict 列表。

    Returns:
        包含所有计算指标的 dict。数据不足（cases < 3）时返回简略结果。
    """
    total = len(cases)

    # ── 数据不足保护 ──
    if total < 3:
        return {
            "insufficient_data": True,
            "total_cases": total,
            "auto_resolve_rate": 0.0,
            "handoff_rate": 0.0,
            "knowledge_hit_rate": 0.0,
            "field_completion_rate": 0.0,
            "handoff_reasons": {},
            "risk_tag_distribution": {},
            "daily_case_trends": {},
            "handoff_count": 0,
            "auto_resolve_count": 0,
            "knowledge_hit_count": 0,
            "knowledge_miss_count": 0,
        }

    # ── 1. 自动解决率 & 2. 转人工率 ──
    auto_resolve_count = sum(
        1 for c in cases if _get_next_action(c) == "standard_answer"
    )
    handoff_count = sum(
        1 for c in cases if _get_next_action(c) == "human_handoff"
    )

    auto_resolve_rate = (auto_resolve_count / total) * 100
    handoff_rate = (handoff_count / total) * 100

    # ── 3. 知识命中率 ──
    knowledge_hit_count = 0
    for c in cases:
        refs = _ensure_deserialized(c.get("knowledge_refs", []))
        if isinstance(refs, list) and len(refs) > 0:
            knowledge_hit_count += 1
        elif isinstance(refs, str) and refs.strip() and refs != "[]":
            knowledge_hit_count += 1
    knowledge_miss_count = total - knowledge_hit_count
    knowledge_hit_rate = (knowledge_hit_count / total) * 100

    # ── 4. 字段完整率 ──
    completion_ratios = []
    for c in cases:
        slot_status = _ensure_deserialized(c.get("slot_status", {}))
        if isinstance(slot_status, dict) and len(slot_status) > 0:
            provided = sum(
                1 for v in slot_status.values()
                if isinstance(v, dict) and v.get("status") == "provided"
            )
            completion_ratios.append(provided / len(slot_status))

    field_completion_rate = (
        (sum(completion_ratios) / len(completion_ratios) * 100)
        if completion_ratios
        else 0.0
    )

    # ── 5. 转人工原因分布 ──
    handoff_reasons = {}
    for c in cases:
        events = _ensure_deserialized(c.get("feedback_events", []))
        if not isinstance(events, list):
            continue
        for evt in events:
            if not isinstance(evt, dict):
                continue
            if evt.get("event_type") == "handoff_reason":
                desc = evt.get("description", "未指定原因")
                handoff_reasons[desc] = handoff_reasons.get(desc, 0) + 1

    # ── 6. 风险标签分布 ──
    risk_tag_distribution = {}
    for c in cases:
        tags = _ensure_deserialized(c.get("risk_tags", []))
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if isinstance(tag, str) and tag:
                risk_tag_distribution[tag] = risk_tag_distribution.get(tag, 0) + 1

    # ── 7. 每日 case 趋势 ──
    daily_case_trends = {}
    for c in cases:
        created = c.get("created_at", "")
        day = created[:10] if created else "unknown"
        daily_case_trends[day] = daily_case_trends.get(day, 0) + 1

    # 按日期排序
    daily_case_trends = dict(sorted(daily_case_trends.items()))

    return {
        "auto_resolve_rate": round(auto_resolve_rate, 2),
        "handoff_rate": round(handoff_rate, 2),
        "knowledge_hit_rate": round(knowledge_hit_rate, 2),
        "field_completion_rate": round(field_completion_rate, 2),
        "handoff_reasons": handoff_reasons,
        "risk_tag_distribution": risk_tag_distribution,
        "daily_case_trends": daily_case_trends,
        "total_cases": total,
        "handoff_count": handoff_count,
        "auto_resolve_count": auto_resolve_count,
        "knowledge_hit_count": knowledge_hit_count,
        "knowledge_miss_count": knowledge_miss_count,
    }
