"""brain_save: Store a memory with embedding and optional relationships."""

import json
import os
import sqlite3
import uuid

from ..db import serialize_embedding
from ..embeddings import embed_text

NEAR_DUP_DEFAULT = 0.92   # cosine ≥ this, same type → the fact is already stored
SUPERSEDE_BAND = (0.80, 0.97)  # divergent same-subject sibling band for auto-detect


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


def _near_dup_threshold() -> float:
    try:
        return float(os.environ.get("BRAIN_NEAR_DUP_THRESHOLD", str(NEAR_DUP_DEFAULT)))
    except ValueError:
        return NEAR_DUP_DEFAULT


def _project_compatible(a: str | None, b: str | None) -> bool:
    """Same project, or one side global (None) — mirrors recall scoping."""
    return a is None or b is None or a == b


def _find_near_dup(conn, emb_bytes, memory_type, project, threshold):
    """Highest-cosine same-type near-duplicate ≥ threshold, or None. Soft-fail to None."""
    from ..search import _cosine_bytes
    try:
        neighbors = conn.execute(
            "SELECT memory_id FROM memory_vectors WHERE embedding MATCH ? AND k = 6",
            (emb_bytes,),
        ).fetchall()
    except Exception:
        return None
    best = None
    for nb in neighbors:
        oid = nb["memory_id"]
        row = conn.execute("SELECT type, project FROM memories WHERE id = ?", (oid,)).fetchone()
        if not row or row["type"] != memory_type or not _project_compatible(project, row["project"]):
            continue
        emb = conn.execute("SELECT embedding FROM memory_vectors WHERE memory_id = ?", (oid,)).fetchone()
        if not emb:
            continue
        sim = _cosine_bytes(emb_bytes, emb["embedding"])
        if sim >= threshold and (best is None or sim > best[1]):
            best = (oid, sim)
    return best


def _detect_write_time_supersede(conn, emb_bytes, content, memory_type, project):
    """Find a divergent same-subject sibling and classify whether `content` revises it.

    Only invoked when BRAIN_AUTO_SUPERSEDE is enabled (LLM call + latency). Returns
    (target_id, relation_type, confidence) or None. The anti-series guard lives inside
    classify_pair, so phase-logs short-circuit to 'unrelated' here too.
    """
    from ..search import _cosine_bytes
    from ..contradiction import classify_pair

    try:
        neighbors = conn.execute(
            "SELECT memory_id FROM memory_vectors WHERE embedding MATCH ? AND k = 6",
            (emb_bytes,),
        ).fetchall()
    except Exception:
        return None
    lo, hi = SUPERSEDE_BAND
    best = None
    for nb in neighbors:
        oid = nb["memory_id"]
        row = conn.execute(
            "SELECT content, type, project FROM memories WHERE id = ?", (oid,)
        ).fetchone()
        if not row or row["type"] != memory_type or not _project_compatible(project, row["project"]):
            continue
        emb = conn.execute("SELECT embedding FROM memory_vectors WHERE memory_id = ?", (oid,)).fetchone()
        if not emb:
            continue
        sim = _cosine_bytes(emb_bytes, emb["embedding"])
        if lo <= sim <= hi and (best is None or sim > best[1]):
            best = (oid, sim, row["content"])
    if not best:
        return None
    try:
        min_conf = float(os.environ.get("BRAIN_SUPERSEDE_MIN_CONF", "0.85"))
    except ValueError:
        min_conf = 0.85
    verdict = classify_pair(content, best[2])  # NEW vs OLD
    if verdict["verdict"] in ("supersedes", "contradicts") and verdict["confidence"] >= min_conf:
        return best[0], verdict["verdict"], verdict["confidence"]
    return None


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
    # Normalize Vietnamese Telex leaks before indexing (clean brain architecture)
    try:
        from ..vn_normalize import normalize_vn

        content = normalize_vn(content)
    except Exception:
        pass  # fallback: store original

    # Compute initial importance from type + source
    from ..importance import compute_initial_importance

    source = (metadata or {}).get("source")
    importance = compute_initial_importance(memory_type, source)

    memory_id = uuid.uuid4().hex[:12]
    tags_json = json.dumps(tags or [])
    meta_json = json.dumps(metadata or {})

    # Validate relations shape BEFORE any INSERT — a malformed entry raising
    # mid-write used to leave a dangling transaction that ghost-committed the
    # half-saved memory on the next unrelated commit (audit 2026-06-12).
    valid_relations = [
        rel for rel in (relations or [])
        if isinstance(rel, dict) and rel.get("target_id") and rel.get("relation_type")
    ]

    # Embed the content (outside the write transaction — may raise on API error)
    embedding = embed_text(content)
    emb_bytes = serialize_embedding(embedding)

    # Near-dup guard (D4): stop duplicate-spam at the source. If a same-type memory
    # already carries this fact (cosine ≥ threshold), skip the insert instead of
    # creating yet another near-identical row (the "saved 7×" pattern).
    if _flag("BRAIN_NEAR_DUP_GUARD", "true"):
        try:
            dup = _find_near_dup(conn, emb_bytes, memory_type, project, _near_dup_threshold())
        except Exception:
            dup = None
        if dup:
            return {
                "id": dup[0],
                "status": "skipped_near_duplicate",
                "matched": dup[0],
                "sim": round(dup[1], 3),
                "type": memory_type,
            }

    # Write-time belief-revision detection. OFF by default (BRAIN_AUTO_SUPERSEDE):
    # an LLM call per in-band save is opt-in and only flipped on after the re-audit
    # proves classifier precision. When off, no detection runs (no latency/cost).
    auto_edge = None
    if _flag("BRAIN_AUTO_SUPERSEDE", "false"):
        try:
            auto_edge = _detect_write_time_supersede(conn, emb_bytes, content, memory_type, project)
        except Exception:
            auto_edge = None

    try:
        # Insert memory
        conn.execute(
            """INSERT INTO memories (id, content, type, tags, project, metadata, importance)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (memory_id, content, memory_type, tags_json, project, meta_json, importance),
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
        for rel in valid_relations:
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
                # Supersedes demotion: halve importance of superseded memory
                if rel.get("relation_type") == "supersedes":
                    conn.execute(
                        "UPDATE memories SET importance = COALESCE(importance, 0.5) * 0.5 WHERE id = ?",
                        (rel["target_id"],),
                    )
            except sqlite3.IntegrityError:
                pass  # Skip relations pointing at missing targets

        # Auto belief-revision edge (only when BRAIN_AUTO_SUPERSEDE flipped on).
        # NEW memory is the source; the divergent sibling is the target. supersedes
        # hides the target + demotes it; contradicts surfaces both (read-time flag).
        if auto_edge:
            tgt, rtype, _conf = auto_edge
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO relations (source_id, target_id, relation_type, weight) "
                    "VALUES (?, ?, ?, 1.0)", (memory_id, tgt, rtype))
                if rtype == "supersedes":
                    conn.execute(
                        "UPDATE memories SET importance = COALESCE(importance, 0.5) * 0.5 WHERE id = ?",
                        (tgt,))
            except sqlite3.IntegrityError:
                pass

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    result = {
        "id": memory_id,
        "status": "saved",
        "type": memory_type,
        "tags": tags or [],
        "project": project,
    }
    if auto_edge:
        result["auto_revision"] = {"target": auto_edge[0], "relation": auto_edge[1],
                                   "confidence": round(auto_edge[2], 2)}
    return result
