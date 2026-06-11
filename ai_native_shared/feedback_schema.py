"""统一反馈事件数据结构 — feedback_event.

本模块定义质量反馈闭环的统一记录格式。
feedback_event 贯穿质检、摘要、对客沟通和 RAG 模块，
用于记录人工修改原因、知识未命中、转人工原因和 badcase。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

EventType = Literal[
    "knowledge_miss",
    "human_modification",
    "handoff_reason",
    "badcase",
    "false_positive",
    "false_negative",
    "low_quality_score",
    "repeat_inquiry",
]

RootCause = Literal[
    "knowledge_gap",
    "rule_conflict",
    "process_block",
    "product_issue",
    "script_issue",
    "policy_unclear",
    "false_positive",
    "false_negative",
    "human_error",
]

Priority = Literal["P0", "P1", "P2", "P3"]


def build_feedback_event(
    case_id: str,
    event_type: EventType | str,
    source_module: str,
    description: str,
    root_cause: RootCause | str = "knowledge_gap",
    suggested_action: str = "",
    priority: Priority | str = "P1",
) -> dict:
    """构建统一 feedback_event.

    Args:
        case_id: 关联的 case_id。
        event_type: 事件类型 — knowledge_miss / human_modification / handoff_reason /
                    badcase / false_positive / false_negative / low_quality_score / repeat_inquiry.
        source_module: 来源模块，如 customer_agent / rag / summary / quality_evaluator /
                       voc_detector / classifier.
        description: 事件描述，说明发现了什么问题。
        root_cause: 根因分类 — knowledge_gap / rule_conflict / process_block /
                    product_issue / script_issue / policy_unclear / false_positive /
                    false_negative / human_error.
        suggested_action: 建议优化动作。
        priority: 优先级 — P0 / P1 / P2 / P3.

    Returns:
        结构化 feedback_event dict。
    """
    return {
        "case_id": case_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "source_module": source_module,
        "description": description,
        "root_cause": root_cause,
        "suggested_action": suggested_action,
        "priority": priority,
    }
