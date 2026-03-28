"""brain_update: Update a memory's content/tags/metadata while preserving ID and history."""

import json
import sqlite3

from ..db import serialize_embedding
from ..embeddings import embed_text


def brain_update(
    conn: sqlite3.Connection,
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """
    Update an existing memory. Preserves ID, access_count, created_at, and relations.

    Only provided fields are updated. Omitted fields stay unchanged.
    If content changes, the embedding and FTS entry are re-generated.
    """
    # Verify memory exists
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    if not row:
        return {"error": f"Memory {memory_id} not found"}

    updates = []
    params: list = []

    if content is not None:
        updates.append("content = ?")
        params.append(content)

        # Re-embed
        embedding = embed_text(content)
        emb_bytes = serialize_embedding(embedding)
        conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (memory_id,))
        conn.execute(
            "INSERT INTO memory_vectors (memory_id, embedding) VALUES (?, ?)",
            (memory_id, emb_bytes),
        )

        # Re-index FTS
        conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
        new_tags = json.dumps(tags) if tags is not None else row["tags"]
        conn.execute(
            "INSERT INTO memory_fts (memory_id, content, tags, project) VALUES (?, ?, ?, ?)",
            (memory_id, content, new_tags, row["project"] or ""),
        )

    if tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(tags))
        # If content didn't change but tags did, update FTS tags
        if content is None:
            conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            conn.execute(
                "INSERT INTO memory_fts (memory_id, content, tags, project) VALUES (?, ?, ?, ?)",
                (memory_id, row["content"], json.dumps(tags), row["project"] or ""),
            )

    if metadata is not None:
        updates.append("metadata = ?")
        params.append(json.dumps(metadata))

    if not updates:
        return {"error": "No fields to update"}

    updates.append("updated_at = datetime('now')")
    params.append(memory_id)

    conn.execute(
        f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()

    # Return updated memory
    updated = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return {
        "id": memory_id,
        "status": "updated",
        "type": updated["type"],
        "content": updated["content"][:100] + "..." if len(updated["content"]) > 100 else updated["content"],
        "access_count": updated["access_count"],
        "created_at": updated["created_at"],
    }
