"""brain_recall: Hybrid semantic + keyword search over memories.

Pipeline:
  1. Hybrid search returns oversampled candidate pool (k*3, capped 10-20)
  2. LLM judge layer reranks by INTENT (if JUDGE_ENABLED and pool >= JUDGE_MIN_CANDIDATES)
  3. Take top-n
  4. Bump access_count ONLY on final top-n (not the oversampled pool)
  5. Format output with judge_status field

Note on access_count placement: previously incremented inside hybrid_search for
all fetched candidates. With oversampling, that would inflate access_count for
memories the judge drops, distorting importance signals. Moved here post-judge.
"""

import json
import sqlite3

from ..judge import (
    STATUS_DISABLED,
    STATUS_BUDGET,
    STATUS_MIN_CANDIDATES,
    STATUS_OK,
    bump_telemetry,
    get_budget_status,
    judge_relevance,
    update_budget,
)
from ..search import cluster_conflicts, dedup_pool, hybrid_search


def _oversample_k(k: int) -> int:
    """Adaptive oversampling cap: max(k*2, 8), ceiling 12.

    Reduced from k*3/cap-20 after measuring real judge latency: 15-candidate
    pools took 3-5s from VN host (~1000 input tokens). Ceiling 12 keeps judge
    prompt ≤800 tokens → typical 2-3s, fits within 6s timeout.

    Floor 8 ensures small-k queries (k=1,2,3) still get meaningful judge pool.
    """
    return min(max(k * 2, 8), 12)


def _bump_access_counts(conn: sqlite3.Connection, ids: list[str]) -> None:
    """Increment access_count + last_accessed for final top-n only."""
    for memory_id in ids:
        try:
            conn.execute(
                """UPDATE memories
                   SET access_count = access_count + 1,
                       last_accessed = datetime('now')
                   WHERE id = ?""",
                (memory_id,),
            )
        except Exception:
            pass
    try:
        conn.commit()
    except Exception:
        pass


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

    When JUDGE_ENABLED=true and the candidate pool is large enough, results
    are LLM-reranked for contextual relevance (+400-800ms latency, soft-fail
    to RRF order on any error).

    Args:
        query: Natural language search query.
        memory_type: Filter by type (decision, discovery, pattern, entity, preference, session, tool).
        project: Filter by project scope. None returns all (global + project-scoped).
        k: Number of results to return.
        time_range: Optional SQL datetime filter (e.g., '-7 days', '-30 days').

    Returns:
        List of matching memories sorted by relevance. Each entry includes
        a 'judge_status' field on the first entry (top-level signal) when
        judge ran or fell back.
    """
    # Normalize Vietnamese Telex leaks in query (clean brain architecture)
    try:
        from ..vn_normalize import normalize_vn

        query = normalize_vn(query)
    except Exception:
        pass

    # Stage 1: Oversample candidate pool from hybrid search
    pool_k = _oversample_k(k)
    pool = hybrid_search(conn, query, memory_type, project, pool_k, time_range=time_range)

    # Stage 1.5: Drop near-duplicate saves so they don't eat top-n slots
    try:
        pool = dedup_pool(conn, pool)
    except Exception:
        pass

    # Stage 2: Budget gate — skip judge if daily limit exceeded
    judge_status = STATUS_DISABLED
    telemetry = {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "latency_ms": 0, "cache_hit": False}
    _, _, budget_ok = get_budget_status(conn)

    if not budget_ok:
        results = pool[:k]
        judge_status = STATUS_BUDGET
    else:
        # Stage 3: LLM judge rerank (no-op if JUDGE_ENABLED=false or pool too small)
        results, judge_status, telemetry = judge_relevance(query, pool, k)

    # Stage 3.5: Noise gate for unvetted results. When the judge didn't run
    # (disabled/budget/timeout/parse error), pure vector neighbors on a novel
    # topic look confident but measured 10/10 irrelevant on adversarial
    # queries. Without a single FTS term match in the pool, return nothing —
    # an empty recall is strictly better than injected noise.
    # Exemptions (audit phase 2, 2026-06-12): fts_hit=None means the FTS leg
    # errored/was skipped — 'unknown', not 'no match' — never gate on it; and
    # min_candidates pools are legitimately small (type-filtered recalls),
    # not adversarial-noise shaped.
    if judge_status not in (STATUS_OK, STATUS_MIN_CANDIDATES) and results:
        hit_vals = [r.get("fts_hit") for r in results if "fts_hit" in r]
        if hit_vals and all(v is not None for v in hit_vals) and not any(hit_vals):
            results = []

    # Stage 4: Bump access_count on FINAL top-n only (not the oversampled pool)
    final_ids = [r["id"] for r in results if r.get("id")]
    _bump_access_counts(conn, final_ids)

    # Stage 5: Update telemetry + budget
    bump_telemetry(conn, telemetry, judge_status)
    if telemetry.get("cost_usd", 0) > 0:
        update_budget(conn, telemetry["cost_usd"])

    # Stage 5.5: Conflict-surface — tag same-subject divergent siblings in the
    # final set with currency ("_current" vs "_superseded_candidate (Nd ago)"),
    # so the reader is told WHICH is current instead of silently receiving two
    # contradictory rows and having to ask. Annotation only — nothing is hidden
    # or reordered. Soft-fail to no flags.
    try:
        conflict_flags = cluster_conflicts(conn, results)
    except Exception:
        conflict_flags = {}

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
            "importance": round(r.get("importance", 0.5), 3),
        }
        if r.get("metadata") and r["metadata"] != "{}":
            entry["metadata"] = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"]
        if r.get("rrf_score"):
            entry["relevance"] = round(r["rrf_score"], 4)
        # Dual-source hits (FTS + vector) measured 100% precision in eval —
        # surface the tier so consumers can trust them above the flat RRF band.
        if r.get("fts_hit") is not None:
            entry["dual_hit"] = bool(r.get("fts_hit")) and bool(r.get("vec_hit"))
        flag = conflict_flags.get(r["id"])
        if flag:
            if flag["role"] == "current":
                entry["_current"] = True
            else:
                entry["_superseded_candidate"] = flag.get("age", "older")
                entry["_conflict_with"] = flag.get("vs")
        formatted.append(entry)

    # Attach judge_status as a top-level field on the first entry (signal carrier)
    # Done this way to avoid changing the brain_recall return shape from list to dict.
    if formatted:
        formatted[0]["_judge_status"] = judge_status

    return formatted
