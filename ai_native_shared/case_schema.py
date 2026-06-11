"""统一 case 上下文数据结构 — case_context 与 case_id.

本模块定义 AI native 售后服务系统的核心数据骨架：
- case_id：贯穿对客沟通、分类、RAG、摘要、质检和风险预警的唯一标识。
- case_context：结构化客户上下文，包含意图、槽位、风险、知识引用、转人工摘要和下一步动作。
- 辅助函数：槽位缺失检查、转人工判断。
"""

from datetime import datetime
from typing import Any, Literal

_counter = 0


def generate_case_id() -> str:
    """生成唯一 case_id，格式 CASE-YYYYMMDD-NNNN."""
    global _counter
    today = datetime.now().strftime("%Y%m%d")
    _counter += 1
    return f"CASE-{today}-{_counter:04d}"


def build_case_context(
    customer_message: str,
    conversation: list[dict[str, str]] | None = None,
    required_slots: dict[str, dict[str, str]] | None = None,
    risk_tags: list[str] | None = None,
    knowledge_refs: list[dict[str, str]] | None = None,
    next_action: Literal["continue_inquiry", "standard_answer", "human_handoff", "escalate"] | str = "continue_inquiry",
    handoff_summary: str = "",
    customer_intent: str = "general_inquiry",
    case_id: str | None = None,
    state_history: list[dict] | None = None,
) -> dict[str, Any]:
    """构建统一 case_context.

    Args:
        customer_message: 客户原始自然语言输入。
        conversation: 多轮对话列表 [{"role":"customer"|"agent","content":""}, ...].
        required_slots: 已收集/缺失字段 {"field_name":{"status":"provided"|"missing","value":""}}.
        risk_tags: 风险标签列表，如 ["regulatory_complaint","compensation_request"].
        knowledge_refs: 命中的知识片段 [{"source":"xxx","chunk_id":"KB-001","text":"xxx"}, ...].
        next_action: 下一步动作 — continue_inquiry / standard_answer / human_handoff / escalate.
        handoff_summary: 转人工时给人工客服的上下文摘要。
        customer_intent: 客户意图分类。
        case_id: 外部传入的 case_id（多轮对话沿用同一个），为 None 时自动生成。
        state_history: 状态变化记录列表，用于回放。

    Returns:
        完整 case_context dict。
    """
    case_id = case_id or generate_case_id()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if conversation is None:
        conversation = [{"role": "customer", "content": customer_message}]

    if required_slots is None:
        required_slots = {
            "order_id": {"status": "missing", "value": ""},
            "event_time": {"status": "missing", "value": ""},
            "customer_request": {"status": "provided", "value": customer_message},
            "evidence": {"status": "missing", "value": ""},
        }

    if risk_tags is None:
        risk_tags = []

    if knowledge_refs is None:
        knowledge_refs = []

    return {
        "case_id": case_id,
        "created_at": created_at,
        "source": "customer_agent",
        "customer_message": customer_message,
        "conversation": conversation,
        "customer_intent": customer_intent,
        "required_slots": required_slots,
        "risk_tags": risk_tags,
        "knowledge_refs": knowledge_refs,
        "next_action": next_action,
        "handoff_summary": handoff_summary,
        "state_history": state_history or [],
    }


def missing_slots(required_slots: dict[str, dict[str, str]]) -> list[str]:
    """返回状态为 'missing' 的槽位名称列表."""
    return [name for name, info in required_slots.items() if info.get("status") == "missing"]


def is_handoff_required(risk_tags: list[str], next_action: str) -> bool:
    """判断是否需要转人工."""
    if next_action in ("human_handoff", "escalate"):
        return True
    high_risk_tags = {
        "regulatory_or_public_risk",
        "regulatory_complaint",
        "compensation_or_refund",
        "compensation_request",
        "high_emotion",
        "policy_conflict",
        "evidence_insufficient",
    }
    if any(tag in high_risk_tags for tag in risk_tags):
        return True
    return False
