"""
统一 Case 数据持久化层 — SQLite 实现
=================================================================

职责：为 AI native 售后系统提供统一 case 存储、查询、筛选接口。
- 8 个公开接口：init_db, save_case, get_case, list_cases, count_cases, delete_case, export_cases_as_json, _get_conn
- SQLite WAL 模式 + busy_timeout 5000
- 软删除：is_active=0

依赖：仅使用标准库（sqlite3, json, os, datetime, typing）
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Optional

# ── 数据库路径 ──────────────────────────────────────────────
DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "cases.db")
)

# ── 表定义 ──────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cases (
    case_id         TEXT PRIMARY KEY,
    customer_intent TEXT NOT NULL DEFAULT 'general_inquiry',
    risk_tags       TEXT NOT NULL DEFAULT '[]',           -- JSON 数组
    slot_status     TEXT NOT NULL DEFAULT '{}',           -- JSON 对象
    knowledge_refs  TEXT NOT NULL DEFAULT '[]',           -- JSON 数组
    handoff_summary TEXT NOT NULL DEFAULT '',
    conversation    TEXT NOT NULL DEFAULT '[]',           -- JSON 数组
    feedback_events TEXT NOT NULL DEFAULT '[]',           -- JSON 数组
    state_history   TEXT NOT NULL DEFAULT '[]',           -- JSON 数组
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT '',
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(case_id)
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_customer_intent ON cases(customer_intent);",
    "CREATE INDEX IF NOT EXISTS idx_risk_tags ON cases(risk_tags);",
    "CREATE INDEX IF NOT EXISTS idx_created_at ON cases(created_at DESC);",
]


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接，自动创建目录和表。

    配置：
    - row_factory = sqlite3.Row（字段名访问）
    - WAL mode（并发读写）
    - busy_timeout = 5000ms（等待锁释放）
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    init_db(conn)
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    """初始化数据库：创建表 + 索引（幂等）。

    Args:
        conn: 可选，不传则内部创建连接。
    """
    if conn is None:
        conn = _get_conn()
        own_conn = True
    else:
        own_conn = False
    try:
        conn.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEXES_SQL:
            conn.execute(idx_sql)
        conn.commit()
    finally:
        if own_conn:
            conn.close()


# ── JSON 序列化/反序列化辅助 ──────────────────────────────

_JSON_FIELDS = {
    "risk_tags",
    "slot_status",
    "knowledge_refs",
    "conversation",
    "feedback_events",
    "state_history",
}


def _serialize_row(row: sqlite3.Row) -> dict:
    """将 sqlite3.Row 转为 dict，JSON 字段反序列化，is_active 转 bool。"""
    d = dict(row)
    for field in _JSON_FIELDS:
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    if "is_active" in d:
        d["is_active"] = bool(d["is_active"])
    return d


# ── CRUD 接口 ──────────────────────────────────────────────


def save_case(case_context: dict) -> str:
    """写入或更新一条 case 记录。

    幂等语义：ON CONFLICT(case_id) DO UPDATE。
    - JSON 字段自动序列化。
    - 首次写入设置 created_at，后续更新仅更新 updated_at。
    - 返回 case_id。

    Args:
        case_context: case_context dict，至少包含 case_id。

    Returns:
        case_id 字符串。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    case_id = case_context.get("case_id", "")

    # 构建 slot_status（从 required_slots 简化）
    required_slots = case_context.get("required_slots", {})
    slot_status = {}
    for k, v in required_slots.items():
        if isinstance(v, dict):
            slot_status[k] = {"status": v.get("status", "missing"), "value": v.get("value", "")}
        else:
            slot_status[k] = {"status": "missing", "value": str(v)}

    conn = _get_conn()
    try:
        # 检查是否已存在
        existing = conn.execute(
            "SELECT created_at FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()

        created_at = case_context.get("created_at", now) if existing is None else existing["created_at"]

        conn.execute(
            """INSERT INTO cases (
                case_id, customer_intent, risk_tags, slot_status,
                knowledge_refs, handoff_summary, conversation,
                feedback_events, state_history, created_at, updated_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(case_id) DO UPDATE SET
                customer_intent = excluded.customer_intent,
                risk_tags = excluded.risk_tags,
                slot_status = excluded.slot_status,
                knowledge_refs = excluded.knowledge_refs,
                handoff_summary = excluded.handoff_summary,
                conversation = excluded.conversation,
                feedback_events = excluded.feedback_events,
                state_history = excluded.state_history,
                updated_at = excluded.updated_at,
                is_active = 1
            """,
            (
                case_id,
                case_context.get("customer_intent", "general_inquiry"),
                json.dumps(case_context.get("risk_tags", []), ensure_ascii=False),
                json.dumps(slot_status, ensure_ascii=False),
                json.dumps(case_context.get("knowledge_refs", []), ensure_ascii=False),
                case_context.get("handoff_summary", ""),
                json.dumps(case_context.get("conversation", []), ensure_ascii=False),
                json.dumps(case_context.get("feedback_events", []), ensure_ascii=False),
                json.dumps(case_context.get("state_history", []), ensure_ascii=False),
                created_at,
                now,
            ),
        )
        conn.commit()
        return case_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_case(case_id: str) -> Optional[dict]:
    """根据 case_id 查询单条 case。

    Args:
        case_id: 要查询的 case_id。

    Returns:
        反序列化后的 dict，未找到返回 None。
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM cases WHERE case_id = ? AND is_active = 1",
            (case_id,),
        ).fetchone()
        if row is None:
            return None
        return _serialize_row(row)
    finally:
        conn.close()


def list_cases(
    limit: int = 50,
    offset: int = 0,
    intent_filter: Optional[str] = None,
    risk_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict]:
    """列出 case 记录，支持筛选和分页。

    动态构建 WHERE 子句：
    - intent_filter: 按 customer_intent 精确匹配。
    - risk_filter: 按 risk_tags LIKE 模糊匹配（如 '%compensation%'）。
    - date_from / date_to: 按 created_at 范围过滤（格式 'YYYY-MM-DD'）。

    Args:
        limit: 每页条数，默认 50。
        offset: 偏移量，默认 0。
        intent_filter: 客户意图精确匹配。
        risk_filter: 风险标签模糊匹配。
        date_from: 创建日期起始（含）。
        date_to: 创建日期截止（含）。

    Returns:
        dict 列表，按 updated_at DESC 排序。
    """
    conn = _get_conn()
    try:
        where_clauses = ["is_active = 1"]
        params: list = []

        if intent_filter:
            where_clauses.append("customer_intent = ?")
            params.append(intent_filter)

        if risk_filter:
            where_clauses.append("risk_tags LIKE ?")
            params.append(f"%{risk_filter}%")

        if date_from:
            where_clauses.append("created_at >= ?")
            params.append(f"{date_from} 00:00:00")

        if date_to:
            where_clauses.append("created_at <= ?")
            params.append(f"{date_to} 23:59:59")

        where_sql = " AND ".join(where_clauses)
        sql = f"SELECT * FROM cases WHERE {where_sql} ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        return [_serialize_row(r) for r in rows]
    finally:
        conn.close()


def count_cases(
    intent_filter: Optional[str] = None,
    risk_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> int:
    """返回符合条件的 case 总数（用于分页）。

    过滤条件与 list_cases 一致。

    Returns:
        整数计数值。
    """
    conn = _get_conn()
    try:
        where_clauses = ["is_active = 1"]
        params: list = []

        if intent_filter:
            where_clauses.append("customer_intent = ?")
            params.append(intent_filter)

        if risk_filter:
            where_clauses.append("risk_tags LIKE ?")
            params.append(f"%{risk_filter}%")

        if date_from:
            where_clauses.append("created_at >= ?")
            params.append(f"{date_from} 00:00:00")

        if date_to:
            where_clauses.append("created_at <= ?")
            params.append(f"{date_to} 23:59:59")

        where_sql = " AND ".join(where_clauses)
        row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM cases WHERE {where_sql}", params
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


def delete_case(case_id: str) -> bool:
    """软删除：将 is_active 设为 0。

    Args:
        case_id: 要删除的 case_id。

    Returns:
        True 表示成功删除，False 表示记录不存在。
    """
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "UPDATE cases SET is_active = 0, updated_at = ? WHERE case_id = ? AND is_active = 1",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), case_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def export_cases_as_json(path: str) -> int:
    """导出全部激活 case 为 JSON 数组文件。

    Args:
        path: 输出文件路径。

    Returns:
        导出的 case 条数。
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM cases WHERE is_active = 1 ORDER BY updated_at DESC"
        ).fetchall()
        cases = [_serialize_row(r) for r in rows]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cases, f, ensure_ascii=False, indent=2)
        return len(cases)
    finally:
        conn.close()
