"""AI native 售后服务系统 — 共享数据结构模块.

本模块为对客沟通机器人、分类、RAG、摘要、质检、VOC 预警和门户提供统一的
case_id、case_context、feedback_events 和知识库数据结构。
"""

__version__ = "1.0.0"

from .case_schema import (
    generate_case_id,
    build_case_context,
    missing_slots,
    is_handoff_required,
)

from .knowledge_base import (
    KNOWLEDGE_CHUNKS,
    retrieve_knowledge,
    has_sufficient_evidence,
)

from .feedback_schema import (
    build_feedback_event,
)

from .sample_cases import SAMPLE_CASES

from .case_store import (
    save_case,
    get_case,
    list_cases,
    count_cases,
    delete_case,
    export_cases_as_json,
    init_db,
)

from .feedback_store import (
    save_event,
    get_events,
    count_by_type,
    count_by_priority,
    get_unresolved,
    resolve_event,
    delete_event,
    init_db as init_feedback_db,
)

__all__ = [
    "generate_case_id",
    "build_case_context",
    "missing_slots",
    "is_handoff_required",
    "KNOWLEDGE_CHUNKS",
    "retrieve_knowledge",
    "has_sufficient_evidence",
    "build_feedback_event",
    "SAMPLE_CASES",
    "save_case",
    "get_case",
    "list_cases",
    "count_cases",
    "delete_case",
    "export_cases_as_json",
    "init_db",
    "save_event",
    "get_events",
    "count_by_type",
    "count_by_priority",
    "get_unresolved",
    "resolve_event",
    "delete_event",
    "init_feedback_db",
]
