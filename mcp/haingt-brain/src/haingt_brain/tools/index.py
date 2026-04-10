"""brain_index: Topic breakdown and memory health snapshot."""

import sqlite3


# Noise tags to exclude from all queries
NOISE_TAGS = {
    "auto-captured",
    "web-search",
    "web-fetch",
    "pre-compact",
    "auto-snapshot",
    "structured",
    "auto-extracted",
    "synthesized",
    "entity",
    "skill",
}


def brain_index(conn: sqlite3.Connection, days: int = 60) -> dict:
    """
    Get a topic breakdown of what's in brain memory.

    Returns overview of tag-based topics, memory types, stale entries, and recent activity.

    Args:
        days: Number of days to include in topic breakdown (default 60).

    Returns:
        dict with:
        - total_memories: total count across all time
        - topics: {tag_name: {"total": N, "by_type": {...}}, ...} sorted by total desc
        - stale: [{"tag": str, "count": int}, ...] entries 30+ days old with 0 access
        - recent_tags: [str, ...] distinct tags from last 7 days, up to 8
    """
    try:
        # Format noise tags for SQL IN clause
        noise_placeholders = ", ".join(["?" for _ in NOISE_TAGS])
        noise_tags_list = list(NOISE_TAGS)

        # Total count
        total_row = conn.execute("SELECT COUNT(*) as cnt FROM memories").fetchone()
        total_memories = total_row["cnt"] if total_row else 0

        # Topic breakdown (tags over last N days, grouped by type)
        topic_rows = conn.execute(
            f"""
            SELECT value as tag, memories.type as type, COUNT(*) as n
            FROM memories, json_each(memories.tags)
            WHERE memories.created_at > datetime('now', '-{days} days')
            AND value NOT IN ({noise_placeholders})
            GROUP BY value, memories.type
            ORDER BY n DESC
            """,
            noise_tags_list,
        ).fetchall()

        # Post-process: group by tag, aggregate by_type
        topics = {}
        for row in topic_rows:
            tag = row["tag"]
            mtype = row["type"]
            count = row["n"]

            if tag not in topics:
                topics[tag] = {"total": 0, "by_type": {}}

            topics[tag]["total"] += count
            topics[tag]["by_type"][mtype] = count

        # Sort by total desc
        topics = dict(sorted(topics.items(), key=lambda x: x[1]["total"], reverse=True))

        # Stale entries (30+ days old, never accessed)
        stale_rows = conn.execute(
            f"""
            SELECT value as tag, COUNT(*) as n
            FROM memories m, json_each(m.tags)
            WHERE m.access_count = 0
            AND m.created_at < datetime('now', '-30 days')
            AND value NOT IN ({noise_placeholders})
            GROUP BY value
            ORDER BY n DESC
            LIMIT 10
            """,
            noise_tags_list,
        ).fetchall()

        stale = [{"tag": row["tag"], "count": row["n"]} for row in stale_rows]

        # Recent tags (last 7 days, distinct, up to 8)
        recent_rows = conn.execute(
            f"""
            SELECT DISTINCT value
            FROM memories m, json_each(m.tags)
            WHERE m.created_at > datetime('now', '-7 days')
            AND value NOT IN ({noise_placeholders})
            ORDER BY m.created_at DESC
            LIMIT 8
            """,
            noise_tags_list,
        ).fetchall()

        recent_tags = [row["value"] for row in recent_rows]

        return {
            "total_memories": total_memories,
            "topics": topics,
            "stale": stale,
            "recent_tags": recent_tags,
        }

    except Exception as e:
        # Return partial results on error
        return {
            "total_memories": 0,
            "topics": {},
            "stale": [],
            "recent_tags": [],
            "error": str(e),
        }
