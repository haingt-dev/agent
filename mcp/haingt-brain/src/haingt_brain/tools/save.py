"""brain_save: Store a memory with embedding and optional relationships."""

import json
import sqlite3
import uuid

from ..db import serialize_embedding
from ..embeddings import embed_text


def brain_save(
    conn: sqlite3.Connection,
    content: str,
    memory_type: str,
    tags: list[str] | None = None,
    project: str | None = None,
    metadata: dict | None = None,
    relations: list[dict] | None = None,
) -> dict:
    """
    Save a memory with automatic embedding for semantic search.

    Args:
        content: The text content to remember.
        memory_type: One of: decision, discovery, pattern, entity, preference, session, tool
        tags: Optional list of tags for filtering.
        project: Project scope (None = global, accessible from any project).
        metadata: Arbitrary JSON metadata (tool schemas, entity details, etc.)
        relations: Optional list of {target_id, relation_type, weight?} to link this memory.

    Returns:
        dict with id, status, and the created memory.
    """
    memory_id = uuid.uuid4().hex[:12]
    tags_json = json.dumps(tags or [])
    meta_json = json.dumps(metadata or {})

    # Embed the content
    embedding = embed_text(content)
    emb_bytes = serialize_embedding(embedding)

    # Insert memory
    conn.execute(
        """INSERT INTO memories (id, content, type, tags, project, metadata)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (memory_id, content, memory_type, tags_json, project, meta_json),
    )

    # Insert vector
    conn.execute(
        "INSERT INTO memory_vectors (memory_id, embedding) VALUES (?, ?)",
        (memory_id, emb_bytes),
    )

    # Insert FTS
    conn.execute(
        "INSERT INTO memory_fts (memory_id, content, tags, project) VALUES (?, ?, ?, ?)",
        (memory_id, content, tags_json, project or ""),
    )

    # Insert relations
    if relations:
        for rel in relations:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO relations (source_id, target_id, relation_type, weight)
                       VALUES (?, ?, ?, ?)""",
                    (
                        memory_id,
                        rel["target_id"],
                        rel["relation_type"],
                        rel.get("weight", 1.0),
                    ),
                )
            except (sqlite3.IntegrityError, KeyError):
                pass  # Skip invalid relations

    conn.commit()

    return {
        "id": memory_id,
        "status": "saved",
        "type": memory_type,
        "tags": tags or [],
        "project": project,
    }
