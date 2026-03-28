"""brain_graph: Knowledge graph traversal from an entity."""

import json
import sqlite3
from collections import deque


def brain_graph(
    conn: sqlite3.Connection,
    entity: str,
    depth: int = 2,
) -> dict:
    """
    Traverse the knowledge graph starting from a memory ID or search term.

    Uses BFS to find related memories through typed relationships.

    Args:
        entity: Memory ID to start from, or a search term to find the starting node.
        depth: How many hops to traverse (default 2).

    Returns:
        dict with the root memory and all related memories found via graph traversal.
    """
    # If entity looks like a memory ID (hex string), use it directly
    root_row = conn.execute(
        "SELECT * FROM memories WHERE id = ?", (entity,)
    ).fetchone()

    # If not found by ID, search by content
    if not root_row:
        root_row = conn.execute(
            """SELECT m.* FROM memories m
               JOIN memory_fts f ON m.id = f.memory_id
               WHERE memory_fts MATCH ?
               ORDER BY f.rank LIMIT 1""",
            (entity,),
        ).fetchone()

    if not root_row:
        return {"status": "not_found", "query": entity}

    root_id = root_row["id"]

    # BFS traversal
    visited = {root_id}
    queue = deque([(root_id, 0)])
    nodes = [_format_memory(root_row)]
    edges = []

    while queue:
        current_id, current_depth = queue.popleft()
        if current_depth >= depth:
            continue

        # Find outgoing relations
        outgoing = conn.execute(
            """SELECT r.*, m.content, m.type, m.tags
               FROM relations r
               JOIN memories m ON m.id = r.target_id
               WHERE r.source_id = ?""",
            (current_id,),
        ).fetchall()

        # Find incoming relations
        incoming = conn.execute(
            """SELECT r.*, m.content, m.type, m.tags
               FROM relations r
               JOIN memories m ON m.id = r.source_id
               WHERE r.target_id = ?""",
            (current_id,),
        ).fetchall()

        for rel in outgoing:
            target_id = rel["target_id"]
            edges.append({
                "from": current_id,
                "to": target_id,
                "type": rel["relation_type"],
                "weight": rel["weight"],
            })
            if target_id not in visited:
                visited.add(target_id)
                node = conn.execute("SELECT * FROM memories WHERE id = ?", (target_id,)).fetchone()
                if node:
                    nodes.append(_format_memory(node))
                    queue.append((target_id, current_depth + 1))

        for rel in incoming:
            source_id = rel["source_id"]
            edges.append({
                "from": source_id,
                "to": current_id,
                "type": rel["relation_type"],
                "weight": rel["weight"],
            })
            if source_id not in visited:
                visited.add(source_id)
                node = conn.execute("SELECT * FROM memories WHERE id = ?", (source_id,)).fetchone()
                if node:
                    nodes.append(_format_memory(node))
                    queue.append((source_id, current_depth + 1))

    return {
        "root": root_id,
        "nodes": nodes,
        "edges": edges,
        "depth_searched": depth,
    }


def _format_memory(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "content": row["content"],
        "type": row["type"],
        "tags": json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"],
        "project": row["project"],
    }
