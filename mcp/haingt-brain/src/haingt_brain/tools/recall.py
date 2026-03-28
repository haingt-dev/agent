"""brain_recall: Hybrid semantic + keyword search over memories."""

import json
import sqlite3

from ..search import hybrid_search


def brain_recall(
    conn: sqlite3.Connection,
    query: str,
    memory_type: str | None = None,
    project: str | None = None,
    k: int = 5,
    time_range: str | None = None,
) -> list[dict]:
    """
    Search memories using hybrid search (FTS5 keyword + vector semantic).

    Args:
        query: Natural language search query.
        memory_type: Filter by type (decision, discovery, pattern, entity, preference, session, tool).
        project: Filter by project scope. None returns all (global + project-scoped).
        k: Number of results to return.
        time_range: Optional SQL datetime filter (e.g., '-7 days', '-30 days').

    Returns:
        List of matching memories sorted by relevance.
    """
    results = hybrid_search(conn, query, memory_type, project, k)

    # Apply time filter if specified
    if time_range and results:
        filtered = []
        for r in results:
            row = conn.execute(
                "SELECT id FROM memories WHERE id = ? AND created_at >= datetime('now', ?)",
                (r["id"], time_range),
            ).fetchone()
            if row:
                filtered.append(r)
        results = filtered

    # Format for output
    formatted = []
    for r in results:
        entry = {
            "id": r["id"],
            "content": r["content"],
            "type": r["type"],
            "tags": json.loads(r["tags"]) if isinstance(r["tags"], str) else r["tags"],
            "project": r["project"],
            "created_at": r["created_at"],
            "access_count": r["access_count"],
        }
        if r.get("metadata") and r["metadata"] != "{}":
            entry["metadata"] = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"]
        if r.get("rrf_score"):
            entry["relevance"] = round(r["rrf_score"], 4)
        formatted.append(entry)

    return formatted
