"""反馈事件持久化存储层 — SQLite 实现

为 AI native 售后系统提供统一的反馈事件存储、查询、聚合接口。
覆盖 5 类标准化事件：knowledge_miss / handoff_reason / human_rewrite / quality_low_score / inquiry_failure

依赖：仅使用标准库（sqlite3, json, os, datetime, typing）
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional

# ── 数据库路径（复用 case_store 的 data/cases.db）──
DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "cases.db")
)

# ── 表定义 ──
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS feedback_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         TEXT NOT NULL DEFAULT '',
    event_type      TEXT NOT NULL,
    source_module   TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    root_cause      TEXT NOT NULL DEFAULT '',
    suggested_action TEXT NOT NULL DEFAULT '',
    priority        TEXT NOT NULL DEFAULT 'P1',
    created_at      TEXT NOT NULL DEFAULT '',
    is_resolved     INTEGER NOT NULL DEFAULT 0
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_fb_event_type ON feedback_events(event_type);",
    "CREATE INDEX IF NOT EXISTS idx_fb_case_id   ON feedback_events(case_id);",
    "CREATE INDEX IF NOT EXISTS idx_fb_priority  ON feedback_events(priority);",
    "CREATE INDEX IF NOT EXISTS idx_fb_resolved  ON feedback_events(is_resolved);",
    "CREATE INDEX IF NOT EXISTS idx_fb_created   ON feedback_events(created_at DESC);",
]


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接，自动创建目录和表。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    # 首次使用时自动建表
    conn.execute(CREATE_TABLE_SQL)
    for idx_sql in CREATE_INDEXES_SQL:
        try:
            conn.execute(idx_sql)
        except Exception:
            pass
    conn.commit()
    return conn


def init_db() -> None:
    """初始化 feedback_events 表（幂等）。"""
    conn = _get_conn()
    try:
        conn.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEXES_SQL:
            conn.execute(idx_sql)
        conn.commit()
    finally:
        conn.close()


# 模块导入时自动初始化
init_db()


# ── 公开接口 ──

def save_event(
    case_id: str = "",
    event_type: str = "",
    source_module: str = "",
    description: str = "",
    root_cause: str = "",
    suggested_action: str = "",
    priority: str = "P1",
) -> int:
    """写入一条反馈事件记录。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_conn()
    try:
        cursor = conn.execute(
            """INSERT INTO feedback_events
               (case_id, event_type, source_module, description, root_cause,
                suggested_action, priority, created_at, is_resolved)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (case_id, event_type, source_module, description,
             root_cause, suggested_action, priority, now),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _serialize_row(row: sqlite3.Row) -> dict:
    """将 sqlite3.Row 转为普通 dict。"""
    return dict(row)


def get_events(
    case_id: Optional[str] = None,
    event_type: Optional[str] = None,
    priority: Optional[str] = None,
    is_resolved: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """查询反馈事件，支持多条件筛选。"""
    conn = _get_conn()
    try:
        where_clauses: list[str] = []
        params: list = []

        if case_id is not None:
            where_clauses.append("case_id = ?")
            params.append(case_id)
        if event_type is not None:
            where_clauses.append("event_type = ?")
            params.append(event_type)
        if priority is not None:
            where_clauses.append("priority = ?")
            params.append(priority)
        if is_resolved is not None:
            where_clauses.append("is_resolved = ?")
            params.append(is_resolved)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        sql = f"SELECT * FROM feedback_events {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        return [_serialize_row(r) for r in rows]
    finally:
        conn.close()


def count_by_type() -> dict[str, int]:
    """按 event_type 分组统计事件数量。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT event_type, COUNT(*) as cnt FROM feedback_events GROUP BY event_type"
        ).fetchall()
        return {r["event_type"]: r["cnt"] for r in rows}
    finally:
        conn.close()


def count_by_priority() -> dict[str, int]:
    """按 priority 分组统计事件数量。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT priority, COUNT(*) as cnt FROM feedback_events GROUP BY priority"
        ).fetchall()
        return {r["priority"]: r["cnt"] for r in rows}
    finally:
        conn.close()


def get_unresolved(limit: int = 100) -> list[dict]:
    """查询所有未解决事件，P0 优先显示。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM feedback_events
               WHERE is_resolved = 0
               ORDER BY
                   CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1
                                 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END ASC,
                   created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [_serialize_row(r) for r in rows]
    finally:
        conn.close()


def resolve_event(event_id: int) -> bool:
    """将指定 id 的事件标记为已解决。"""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "UPDATE feedback_events SET is_resolved = 1 WHERE id = ?",
            (event_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_event(event_id: int) -> bool:
    """删除指定 id 的事件。"""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM feedback_events WHERE id = ?",
            (event_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
