"""Hybrid search using Reciprocal Rank Fusion (FTS5 + sqlite-vec)."""

import math
import sqlite3
import struct

from .db import serialize_embedding
from .embeddings import embed_text

# Memories explicitly replaced via a `supersedes` relation are dead weight in
# results: the replacement carries the current fact, the target carries the
# stale one. Lineage stays in the relations table; retrieval skips the target.
SUPERSEDED_FILTER = (
    "m.id NOT IN (SELECT target_id FROM relations WHERE relation_type = 'supersedes')"
)


def hybrid_search(
    conn: sqlite3.Connection,
    query: str,
    memory_type: str | None = None,
    project: str | None = None,
    k: int = 5,
    rrf_k: int = 60,
    time_range: str | None = None,
) -> list[dict]:
    """
    Search memories using Reciprocal Rank Fusion combining FTS5 and vector search.

    RRF score = 1/(rrf_k + fts_rank) + 1/(rrf_k + vec_rank)
    Items appearing in both searches rank highest.

    time_range is a SQLite datetime modifier (e.g., '-7 days'). Applied as a
    SQL WHERE clause BEFORE top-k selection so older valid matches in the
    candidate pool are not filtered to empty post-retrieval.
    """
    query_embedding = embed_text(query)
    emb_bytes = serialize_embedding(query_embedding)

    # Build type/project/time filter clause
    filters = [SUPERSEDED_FILTER]
    params: dict = {}
    if memory_type:
        filters.append("m.type = :type")
        params["type"] = memory_type
    if project:
        filters.append("(m.project = :project OR m.project IS NULL)")
        params["project"] = project
    if time_range:
        filters.append("m.created_at >= datetime('now', :time_range)")
        params["time_range"] = time_range
    where_clause = " AND ".join(filters)

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
            (f.memory_id IS NOT NULL) AS fts_hit,
            (v.memory_id IS NOT NULL) AS vec_hit,
            COALESCE(1.0 / (:rrf_k + f.fts_pos), 0) +
            COALESCE(1.0 / (:rrf_k + v.vec_pos), 0) AS rrf_score
        FROM fts_results f
        FULL OUTER JOIN vec_results v ON f.memory_id = v.memory_id
    )
    SELECT m.*, s.fts_hit, s.vec_hit,
           s.rrf_score * (0.5 + 0.5 * COALESCE(m.importance, 0.5)) AS rrf_score
    FROM scored s
    JOIN memories m ON m.id = s.memory_id
    WHERE {where_clause}
    ORDER BY s.rrf_score * (0.5 + 0.5 * COALESCE(m.importance, 0.5)) DESC
    LIMIT :k
    """

    params.update({"query": query, "embedding": emb_bytes, "rrf_k": rrf_k, "k": k})

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        # Fallback: vector-only search if FTS fails (e.g., empty FTS table)
        rows = vector_search(conn, query_embedding, memory_type, project, k, time_range)
        return rows

    # NOTE: access_count update intentionally removed here. Moved to
    # tools/recall.py to apply only to the final top-n AFTER judge filtering.
    # With oversampling (k*3) introduced for the judge layer, incrementing
    # access_count for the whole candidate pool would inflate counters for
    # memories the judge drops, distorting importance signals.

    return [dict(row) for row in rows]


def _cosine_bytes(a_bytes: bytes, b_bytes: bytes) -> float:
    """Cosine similarity between two raw float32 embedding buffers."""
    n = len(a_bytes) // 4
    a = struct.unpack(f"{n}f", a_bytes)
    b = struct.unpack(f"{n}f", b_bytes)
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def dedup_pool(
    conn: sqlite3.Connection,
    pool: list[dict],
    threshold: float = 0.92,
) -> list[dict]:
    """Drop near-duplicate candidates from an oversampled pool.

    Audit 2026-06-12: ~17% of judged top-5 slots were the same fact saved
    2-3 times. Keeps the first occurrence (pool arrives RRF-ranked, so the
    strongest representative survives); duplicates are hidden from this
    result only, never deleted. O(n²) cosine over a pool capped at 12.
    """
    if len(pool) < 2:
        return pool
    embs: dict[str, bytes] = {}
    for c in pool:
        cid = c.get("id")
        if not cid:
            continue
        try:
            row = conn.execute(
                "SELECT embedding FROM memory_vectors WHERE memory_id = ?", (cid,)
            ).fetchone()
        except sqlite3.OperationalError:
            return pool  # vec table unavailable — skip dedup
        if row:
            embs[cid] = row[0]
    kept: list[dict] = []
    for c in pool:
        emb = embs.get(c.get("id", ""))
        is_dup = False
        if emb is not None:
            for k in kept:
                k_emb = embs.get(k.get("id", ""))
                if k_emb is not None and _cosine_bytes(emb, k_emb) >= threshold:
                    is_dup = True
                    break
        if not is_dup:
            kept.append(c)
    return kept


def vector_search(
    conn: sqlite3.Connection,
    query_embedding: list[float],
    memory_type: str | None = None,
    project: str | None = None,
    k: int = 5,
    time_range: str | None = None,
) -> list[dict]:
    """Pure vector search fallback."""
    emb_bytes = serialize_embedding(query_embedding)

    filters = [SUPERSEDED_FILTER]
    params: dict = {}
    if memory_type:
        filters.append("m.type = :type")
        params["type"] = memory_type
    if project:
        filters.append("(m.project = :project OR m.project IS NULL)")
        params["project"] = project
    if time_range:
        filters.append("m.created_at >= datetime('now', :time_range)")
        params["time_range"] = time_range
    where_clause = " AND ".join(filters)

    sql = f"""
    SELECT m.*, 0 AS fts_hit, 1 AS vec_hit, v.distance
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

    # NOTE: access_count update moved to tools/recall.py (see comment in hybrid_search)
    return [dict(row) for row in rows]
