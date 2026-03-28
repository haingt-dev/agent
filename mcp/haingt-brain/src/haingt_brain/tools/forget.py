"""brain_forget: Delete a memory and all its relationships."""

import sqlite3


def brain_forget(conn: sqlite3.Connection, memory_id: str) -> dict:
    """
    Delete a memory by ID. Also removes its embedding, FTS entry, and all relationships.

    Args:
        memory_id: The ID of the memory to delete.

    Returns:
        dict with status and deleted ID.
    """
    # Check existence
    row = conn.execute("SELECT id, type, content FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if not row:
        return {"status": "not_found", "id": memory_id}

    # Delete from all tables (relations cascade via FK, but be explicit for vec/fts)
    conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (memory_id,))
    conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
    conn.execute("DELETE FROM relations WHERE source_id = ? OR target_id = ?", (memory_id, memory_id))
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()

    return {
        "status": "deleted",
        "id": memory_id,
        "type": row["type"],
        "content_preview": row["content"][:100],
    }
