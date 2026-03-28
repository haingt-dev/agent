"""Hybrid search using Reciprocal Rank Fusion (FTS5 + sqlite-vec)."""

import sqlite3

from .db import serialize_embedding
from .embeddings import embed_text


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    memory_type: str | None = None,
    project: str | None = None,
    k: int = 5,
    rrf_k: int = 60,
) -> list[dict]:
    """
    Search memories using Reciprocal Rank Fusion combining FTS5 and vector search.

    RRF score = 1/(rrf_k + fts_rank) + 1/(rrf_k + vec_rank)
    Items appearing in both searches rank highest.
    """
    query_embedding = embed_text(query)
    emb_bytes = serialize_embedding(query_embedding)

    # Build type/project filter clause
    filters = []
    params: dict = {}
    if memory_type:
        filters.append("m.type = :type")
        params["type"] = memory_type
    if project:
        filters.append("(m.project = :project OR m.project IS NULL)")
        params["project"] = project
    where_clause = " AND ".join(filters) if filters else "1=1"

    sql = f"""
    WITH fts_results AS (
        SELECT memory_id, rank AS fts_rank,
               ROW_NUMBER() OVER (ORDER BY rank) AS fts_pos
        FROM memory_fts
        WHERE memory_fts MATCH :query
        ORDER BY rank
        LIMIT 20
    ),
    vec_results AS (
        SELECT memory_id, distance AS vec_dist,
               ROW_NUMBER() OVER (ORDER BY distance) AS vec_pos
        FROM memory_vectors
        WHERE embedding MATCH :embedding
          AND k = 20
    ),
    scored AS (
        SELECT
            COALESCE(f.memory_id, v.memory_id) AS memory_id,
            COALESCE(1.0 / (:rrf_k + f.fts_pos), 0) +
            COALESCE(1.0 / (:rrf_k + v.vec_pos), 0) AS rrf_score
        FROM fts_results f
        FULL OUTER JOIN vec_results v ON f.memory_id = v.memory_id
    )
    SELECT m.*, s.rrf_score
    FROM scored s
    JOIN memories m ON m.id = s.memory_id
    WHERE {where_clause}
    ORDER BY s.rrf_score DESC
    LIMIT :k
    """

    params.update({"query": query, "embedding": emb_bytes, "rrf_k": rrf_k, "k": k})

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        # Fallback: vector-only search if FTS fails (e.g., empty FTS table)
        rows = vector_search(conn, query_embedding, memory_type, project, k)
        return rows

    # Update access counts
    for row in rows:
        conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ?",
            (row["id"],),
        )
    conn.commit()

    return [dict(row) for row in rows]


def vector_search(
    conn: sqlite3.Connection,
    query_embedding: list[float],
    memory_type: str | None = None,
    project: str | None = None,
    k: int = 5,
) -> list[dict]:
    """Pure vector search fallback."""
    emb_bytes = serialize_embedding(query_embedding)

    filters = []
    params: dict = {}
    if memory_type:
        filters.append("m.type = :type")
        params["type"] = memory_type
    if project:
        filters.append("(m.project = :project OR m.project IS NULL)")
        params["project"] = project
    where_clause = " AND ".join(filters) if filters else "1=1"

    sql = f"""
    SELECT m.*, v.distance
    FROM memory_vectors v
    JOIN memories m ON m.id = v.memory_id
    WHERE v.embedding MATCH :embedding
      AND v.k = :k_vec
      AND {where_clause}
    ORDER BY v.distance
    LIMIT :k
    """

    params.update({"embedding": emb_bytes, "k_vec": k * 4, "k": k})
    rows = conn.execute(sql, params).fetchall()

    for row in rows:
        conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ?",
            (row["id"],),
        )
    conn.commit()

    return [dict(row) for row in rows]
