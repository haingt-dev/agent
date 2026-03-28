"""brain_session: Session lifecycle management."""

import json
import sqlite3
import uuid
from datetime import datetime


def brain_session_start(conn: sqlite3.Connection, project: str | None = None) -> dict:
    """
    Start a new session and return relevant context.

    Auto-runs consolidation if >7 days since last run.
    Returns last 3 session summaries, active entities, pending decisions, and preferences.
    """
    session_id = uuid.uuid4().hex[:12]

    conn.execute(
        "INSERT INTO sessions (id, project) VALUES (?, ?)",
        (session_id, project),
    )
    conn.commit()

    # Auto-consolidation check (non-blocking — runs only if overdue)
    consolidation_report = None
    try:
        from ..consolidate import should_consolidate, consolidate_all
        if should_consolidate(conn, interval_days=7):
            consolidation_report = consolidate_all(conn)
    except Exception:
        pass  # Don't let consolidation failure block session start

    # Tool index drift check
    tool_drift = None
    try:
        from .toolbox import validate_tool_index
        tool_drift = validate_tool_index(conn)
    except Exception:
        pass  # Don't block session start

    # Gather context
    context = {"session_id": session_id, "project": project}
    if consolidation_report and any(v for k, v in consolidation_report.items() if k != "details"):
        context["auto_consolidation"] = {
            k: v for k, v in consolidation_report.items() if k != "details"
        }
    if tool_drift:
        context["tool_index_drift"] = tool_drift

    # Last 3 session summaries for this project
    rows = conn.execute(
        """SELECT id, summary, ended_at FROM sessions
           WHERE project = ? AND summary IS NOT NULL AND ended_at IS NOT NULL
           ORDER BY ended_at DESC LIMIT 3""",
        (project,),
    ).fetchall()
    if rows:
        context["recent_sessions"] = [
            {"id": r["id"], "summary": r["summary"], "ended_at": r["ended_at"]}
            for r in rows
        ]

    # Active preferences (always relevant)
    prefs = conn.execute(
        """SELECT id, content, tags FROM memories
           WHERE type = 'preference' AND (project = ? OR project IS NULL)
           ORDER BY updated_at DESC LIMIT 5""",
        (project,),
    ).fetchall()
    if prefs:
        context["preferences"] = [
            {"id": r["id"], "content": r["content"]} for r in prefs
        ]

    # Recent decisions (last 7 days)
    decisions = conn.execute(
        """SELECT id, content, tags, created_at FROM memories
           WHERE type = 'decision'
             AND (project = ? OR project IS NULL)
             AND created_at >= datetime('now', '-7 days')
           ORDER BY created_at DESC LIMIT 5""",
        (project,),
    ).fetchall()
    if decisions:
        context["recent_decisions"] = [
            {"id": r["id"], "content": r["content"], "created_at": r["created_at"]}
            for r in decisions
        ]

    # Active entities (most accessed)
    entities = conn.execute(
        """SELECT id, content, tags FROM memories
           WHERE type = 'entity'
             AND (project = ? OR project IS NULL)
           ORDER BY access_count DESC, updated_at DESC LIMIT 5""",
        (project,),
    ).fetchall()
    if entities:
        context["active_entities"] = [
            {"id": r["id"], "content": r["content"]} for r in entities
        ]

    return context


def brain_session_save(
    conn: sqlite3.Connection,
    session_id: str,
    summary: str,
    decisions: list[str] | None = None,
    discoveries: list[str] | None = None,
    entities: list[str] | None = None,
) -> dict:
    """
    Save session learnings and mark session as ended.

    Optionally auto-creates memory entries for decisions, discoveries, and entities.
    """
    from .save import brain_save

    memory_ids = []

    # Save individual items as memories
    for content in (decisions or []):
        r = brain_save(conn, content, "decision")
        memory_ids.append(r["id"])

    for content in (discoveries or []):
        r = brain_save(conn, content, "discovery")
        memory_ids.append(r["id"])

    for content in (entities or []):
        r = brain_save(conn, content, "entity")
        memory_ids.append(r["id"])

    # Update session record
    conn.execute(
        """UPDATE sessions SET ended_at = datetime('now'), summary = ?, memory_ids = ?
           WHERE id = ?""",
        (summary, json.dumps(memory_ids), session_id),
    )
    conn.commit()

    return {
        "status": "saved",
        "session_id": session_id,
        "summary_length": len(summary),
        "memories_created": len(memory_ids),
        "memory_ids": memory_ids,
    }


def brain_session_status(conn: sqlite3.Connection) -> dict:
    """Return memory stats: count by type, total, recent activity."""
    type_counts = conn.execute(
        "SELECT type, COUNT(*) as count FROM memories GROUP BY type ORDER BY count DESC"
    ).fetchall()

    total = sum(r["count"] for r in type_counts)

    recent_7d = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()[0]

    sessions_total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    sessions_with_summary = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE summary IS NOT NULL"
    ).fetchone()[0]

    return {
        "total_memories": total,
        "by_type": {r["type"]: r["count"] for r in type_counts},
        "created_last_7_days": recent_7d,
        "total_sessions": sessions_total,
        "sessions_with_summary": sessions_with_summary,
    }
