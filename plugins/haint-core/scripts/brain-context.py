#!/usr/bin/env python3
"""Deterministic brain context injection for SessionStart hook.

Reads brain.db directly (no MCP needed) and outputs compact context.
Target: ~300-500 tokens max.

argv[1] (optional): hook source — "startup" | "resume" | "compact".
On "compact" only the hot tier is emitted: the compact summary already
preserves recent decisions/session state, and long-lived sessions were
re-injecting near-identical full blocks on every compact cycle
(77 blocks in one session — audit 2026-06-12).
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"

CLIP_CHARS = 200

# Semantic dedup (same decision saved twice under different IDs filled 2 of 3
# section slots — audit 2026-06-12). Soft imports: missing package or vec
# extension degrades to ID-level dedup only.
_BRAIN_SRC = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / "src"
try:
    sys.path.insert(0, str(_BRAIN_SRC))
    from haingt_brain.search import dedup_pool as _dedup_pool
except Exception:
    _dedup_pool = None


def _staleness_suffix(date_str: str | None) -> str:
    """Return ' (Nd ago)' if the memory is 2+ days old, else empty string."""
    if not date_str:
        return ""
    try:
        # SQLite stores datetimes as naive UTC strings
        memory_dt = datetime.fromisoformat(date_str)
        age_days = (datetime.now() - memory_dt).days
        if age_days >= 2:
            return f" ({age_days}d ago)"
    except Exception:
        pass
    return ""


def _clip(text: str, limit: int = CLIP_CHARS) -> str:
    """Truncate at a word boundary so injected facts stay readable."""
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    if cut < limit // 2:
        cut = limit
    return text[:cut] + "…"


def _connect() -> sqlite3.Connection | None:
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
    except Exception:
        return None
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception:
        pass  # vec unavailable → semantic dedup silently degrades
    return conn


def _semantic_filter(
    conn: sqlite3.Connection, kept: list[dict], candidates: list[dict], limit: int
) -> list[dict]:
    """Drop candidates near-duplicating already-kept rows (or each other)."""
    if not candidates:
        return []
    if _dedup_pool is None:
        return candidates[:limit]
    try:
        survivors = _dedup_pool(conn, kept + candidates)
        kept_ids = {r["id"] for r in kept}
        return [r for r in survivors if r["id"] not in kept_ids][:limit]
    except Exception:
        return candidates[:limit]


def query_context(project: str | None, source: str = "startup") -> str:
    conn = _connect()
    if conn is None:
        return ""

    sections = []
    kept_rows: list[dict] = []
    emitted_ids: set[str] = set()

    # Hot-tier memories (importance >= 0.8, any age — timeless high-value)
    try:
        hot_rows = conn.execute(
            """SELECT id, content, type, importance,
                      COALESCE(updated_at, created_at) AS date FROM memories
               WHERE COALESCE(importance, 0.5) >= 0.8
                 AND type NOT IN ('tool', 'session')
                 AND (project = ? OR project IS NULL)
               ORDER BY importance DESC, updated_at DESC
               LIMIT 3""",
            (project,),
        ).fetchall()
        if hot_rows:
            rows = [dict(r) for r in hot_rows]
            kept_rows.extend(rows)
            emitted_ids.update(r["id"] for r in rows)
            items = [
                f"- [{r['type']}] {_clip(r['content'])}{_staleness_suffix(r['date'])}"
                for r in rows
            ]
            sections.append("High-value (timeless):\n" + "\n".join(items))
    except Exception:
        pass

    if source == "compact":
        conn.close()
        return "\n".join(sections) if sections else ""

    # Recent decisions (last 7 days) — over-fetch 6, dedup, emit 3
    try:
        rows = conn.execute(
            """SELECT id, content, COALESCE(updated_at, created_at) AS date FROM memories
               WHERE type IN ('decision', 'discovery')
                 AND (project = ? OR project IS NULL)
                 AND created_at >= datetime('now', '-7 days')
                 AND id NOT IN (SELECT target_id FROM relations WHERE relation_type = 'supersedes')
               ORDER BY
                 CASE WHEN type = 'decision' THEN 0 ELSE 1 END,
                 COALESCE(importance, 0.5) DESC,
                 created_at DESC
               LIMIT 6""",
            (project,),
        ).fetchall()
        candidates = [dict(r) for r in rows if r["id"] not in emitted_ids]
        picked = _semantic_filter(conn, kept_rows, candidates, 3)
        if picked:
            kept_rows.extend(picked)
            emitted_ids.update(r["id"] for r in picked)
            items = [f"- {_clip(r['content'])}{_staleness_suffix(r['date'])}" for r in picked]
            sections.append("Recent decisions:\n" + "\n".join(items))
    except Exception:
        pass

    # Active preferences — over-fetch 6, skip already emitted, dedup, emit 3
    try:
        rows = conn.execute(
            """SELECT id, content, COALESCE(updated_at, created_at) AS date FROM memories
               WHERE type = 'preference'
                 AND (project = ? OR project IS NULL)
                 AND id NOT IN (SELECT target_id FROM relations WHERE relation_type = 'supersedes')
               ORDER BY updated_at DESC LIMIT 6""",
            (project,),
        ).fetchall()
        candidates = [dict(r) for r in rows if r["id"] not in emitted_ids]
        picked = _semantic_filter(conn, kept_rows, candidates, 3)
        if picked:
            items = [f"- {_clip(r['content'])}{_staleness_suffix(r['date'])}" for r in picked]
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
    # Project derived from cwd; hook source passed as argv[1] by session-start.sh
    project = None
    cwd = Path.cwd()
    projects_dir = Path.home() / "Projects"
    try:
        project = cwd.relative_to(projects_dir).parts[0]
    except (ValueError, IndexError):
        pass

    source = sys.argv[1] if len(sys.argv) > 1 else "startup"
    context = query_context(project, source)
    if context:
        print(context)
