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


def sanitize_fts_query(query: str) -> str:
    """Make an arbitrary string safe for FTS5 MATCH.

    Raw MATCH treats '.', '-', '+', '(' as syntax — 'judge.py timeout' and
    'chimera-protocol naming' raise OperationalError, silently degrading
    hybrid search to vector-only (audit 2026-06-12). Quote each whitespace
    token as a phrase: preserves implicit-AND semantics, neutralizes syntax.
    """
    tokens = []
    for raw in query.split():
        t = raw.replace('"', '""')
        # Skip tokens with no indexable characters (pure punctuation)
        if not any(c.isalnum() for c in t):
            continue
        tokens.append(f'"{t}"')
    return " ".join(tokens[:16])


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
    elif memory_type == "tool":
        # Tools have scope: with no project context, only globally-available tools apply
        # (project-scoped skills/MCP servers aren't loaded outside their project). For
        # non-tool recall, an absent project still means "all memories".
        filters.append("m.project IS NULL")
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

    fts_query = sanitize_fts_query(query)
    params.update({"query": fts_query, "embedding": emb_bytes, "rrf_k": rrf_k, "k": k})

    try:
        if not fts_query:
            raise sqlite3.OperationalError("empty FTS query after sanitization")
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        # Fallback: vector-only search if FTS fails (e.g., empty FTS table).
        # fts_hit comes back NULL there — 'unknown', not 'no keyword match' —
        # so downstream noise gates must not treat this path as gate-worthy.
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


def _age_label(newer_created: str, older_created: str) -> str:
    """Human "Nd ago" between two created_at strings (newer minus older)."""
    from datetime import datetime

    try:
        dn = datetime.fromisoformat(newer_created)
        do = datetime.fromisoformat(older_created)
    except (ValueError, TypeError):
        return "older"
    days = (dn - do).days
    if days >= 1:
        return f"{days}d ago"
    hours = int((dn - do).total_seconds() // 3600)
    if hours >= 1:
        return f"{hours}h ago"
    return "earlier"


def cluster_conflicts(
    conn: sqlite3.Connection,
    results: list[dict],
    sim_lo: float = 0.80,
    sim_hi: float = 0.985,
) -> dict[str, dict]:
    """Find same-subject DIVERGENT pairs among the final results and tag currency.

    A conflict pair = same `type`, same-or-null project, cosine in [sim_lo, sim_hi]
    (high enough = same subject; below the ~0.99 near-identical-dup band that
    dedup_pool already collapses), OR an explicit `contradicts`/`supersedes` edge
    between two members. Clusters are grouped; the newest member by created_at is
    flagged "current", the rest "superseded_candidate (Nd ago)". This converts the
    silent "two divergent rows, no signal" case into an explicit currency cue so
    the reader stops having to ask which is current.

    Returns {memory_id: {"role": "current"|"superseded_candidate", "age": str,
                         "vs": peer_id, "via": "similarity"|"edge"}}.
    Annotation only — never reorders or hides. Soft-fails to {} on any error.
    """
    if len(results) < 2:
        return {}
    by_id = {r.get("id"): r for r in results if r.get("id")}
    ids = list(by_id)
    if len(ids) < 2:
        return {}

    # Fetch embeddings for the (small, ≤k) result set — mirrors dedup_pool.
    embs: dict[str, bytes] = {}
    for cid in ids:
        try:
            row = conn.execute(
                "SELECT embedding FROM memory_vectors WHERE memory_id = ?", (cid,)
            ).fetchone()
        except sqlite3.OperationalError:
            return {}
        if row:
            embs[cid] = row[0]

    # Anti-series guard: formulaic phase-logs ("aseprite Tier 1/2a/2b LANDED") are
    # distinct-true siblings, not supersession — skip them for GEOMETRIC pairs. An
    # explicit contradicts/supersedes edge (below) is a deliberate judgment and is
    # always surfaced regardless.
    def _series(a_content, b_content) -> bool:
        try:
            from .contradiction import is_series_pair
            return is_series_pair(a_content or "", b_content or "")
        except Exception:
            return False

    # Geometric conflict pairs
    pairs: list[tuple[str, str, str]] = []  # (a, b, via)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            ra, rb = by_id[a], by_id[b]
            if ra.get("type") != rb.get("type"):
                continue
            pa, pb = ra.get("project"), rb.get("project")
            if pa is not None and pb is not None and pa != pb:
                continue
            ea, eb = embs.get(a), embs.get(b)
            if ea is None or eb is None:
                continue
            sim = _cosine_bytes(ea, eb)
            if sim_lo <= sim <= sim_hi and not _series(ra.get("content"), rb.get("content")):
                pairs.append((a, b, "similarity"))

    # Explicit edges among the result set (first consumer of `contradicts`)
    try:
        placeholders = ",".join("?" * len(ids))
        edge_rows = conn.execute(
            f"""SELECT source_id, target_id FROM relations
                WHERE relation_type IN ('contradicts', 'supersedes')
                  AND source_id IN ({placeholders}) AND target_id IN ({placeholders})""",
            (*ids, *ids),
        ).fetchall()
        for er in edge_rows:
            pairs.append((er["source_id"], er["target_id"], "edge"))
    except sqlite3.OperationalError:
        pass

    if not pairs:
        return {}

    # Union-find clustering
    parent = {cid: cid for cid in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    via_of: dict[str, str] = {}
    for a, b, via in pairs:
        parent[find(a)] = find(b)
        via_of[a] = via_of.get(a, via)
        via_of[b] = via_of.get(b, via)

    clusters: dict[str, list[str]] = {}
    for cid in ids:
        if cid in via_of:
            clusters.setdefault(find(cid), []).append(cid)

    flags: dict[str, dict] = {}
    for members in clusters.values():
        if len(members) < 2:
            continue
        newest = max(members, key=lambda m: by_id[m].get("created_at") or "")
        newest_created = by_id[newest].get("created_at") or ""
        for m in members:
            if m == newest:
                flags[m] = {"role": "current", "via": via_of.get(m, "similarity")}
            else:
                flags[m] = {
                    "role": "superseded_candidate",
                    "age": _age_label(newest_created, by_id[m].get("created_at") or ""),
                    "vs": newest,
                    "via": via_of.get(m, "similarity"),
                }
    return flags


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
    elif memory_type == "tool":
        # Tools have scope: with no project context, only globally-available tools apply
        # (project-scoped skills/MCP servers aren't loaded outside their project). For
        # non-tool recall, an absent project still means "all memories".
        filters.append("m.project IS NULL")
    if time_range:
        filters.append("m.created_at >= datetime('now', :time_range)")
        params["time_range"] = time_range
    where_clause = " AND ".join(filters)

    sql = f"""
    SELECT m.*, NULL AS fts_hit, 1 AS vec_hit, v.distance
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
