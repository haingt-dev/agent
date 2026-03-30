#!/usr/bin/env python3
"""Deterministic brain context injection for SessionStart hook.

Reads brain.db directly (no MCP needed) and outputs compact context.
Target: ~300-500 tokens max.
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"


def get_project() -> str | None:
    """Extract project from stdin JSON if available."""
    try:
        data = json.loads(sys.stdin.read())
        return data.get("project")
    except Exception:
        return None


def query_context(project: str | None) -> str:
    if not DB_PATH.exists():
        return ""

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
    except Exception:
        return ""

    sections = []

    # Recent decisions (last 7 days, max 3)
    try:
        rows = conn.execute(
            """SELECT content FROM memories
               WHERE type IN ('decision', 'discovery')
                 AND (project = ? OR project IS NULL)
                 AND created_at >= datetime('now', '-7 days')
               ORDER BY
                 CASE WHEN type = 'decision' THEN 0 ELSE 1 END,
                 created_at DESC
               LIMIT 3""",
            (project,),
        ).fetchall()
        if rows:
            items = [f"- {r['content'][:120]}" for r in rows]
            sections.append("Recent decisions:\n" + "\n".join(items))
    except Exception:
        pass

    # Active preferences (max 3)
    try:
        rows = conn.execute(
            """SELECT content FROM memories
               WHERE type = 'preference'
                 AND (project = ? OR project IS NULL)
               ORDER BY updated_at DESC LIMIT 3""",
            (project,),
        ).fetchall()
        if rows:
            items = [f"- {r['content'][:120]}" for r in rows]
            sections.append("Preferences:\n" + "\n".join(items))
    except Exception:
        pass

    # Last session summary (1 most recent)
    try:
        row = conn.execute(
            """SELECT summary FROM sessions
               WHERE summary IS NOT NULL AND ended_at IS NOT NULL
                 AND (project = ? OR project IS NULL)
               ORDER BY ended_at DESC LIMIT 1""",
            (project,),
        ).fetchone()
        if row and row["summary"]:
            summary = row["summary"][:200]
            sections.append(f"Last session: {summary}")
    except Exception:
        pass

    conn.close()

    if not sections:
        return ""

    return "\n".join(sections)


if __name__ == "__main__":
    # Project can come from env or be derived from cwd
    project = None
    cwd = Path.cwd()
    projects_dir = Path.home() / "Projects"
    try:
        project = cwd.relative_to(projects_dir).parts[0]
    except (ValueError, IndexError):
        pass

    context = query_context(project)
    if context:
        print(context)
