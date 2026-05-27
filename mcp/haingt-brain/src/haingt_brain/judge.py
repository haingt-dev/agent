"""LLM judge layer for brain_recall — rerank hybrid_search candidates by INTENT.

Why: RRF + importance multiplier scores by similarity, not contextual relevance.
"First Drop of Ink" paper (arxiv 2605.10828) shows 10% hard distractors →
~55% reasoning degradation. Hard distractors = semantically similar but
contextually wrong (cross-project leaks, stale info, wrong era). RRF cannot
distinguish "looks relevant" from "actually relevant" — judge can.

Recursion guard: this module MUST NOT call brain_recall, brain_save, or any
MCP tool. Pure OpenAI client only. Adding such a call would create a loop
where judge invokes itself.

Design contract:
- Single batched chat completion call (not n calls)
- Soft-fail on any error → return RRF top-n unchanged
- LRU cache: full-set hash (judge calibrates against the candidate set)
- Hard timeout 1500ms — never block recall longer than this
"""

import hashlib
import json
import os
import sys
from collections import OrderedDict
from datetime import date

from .embeddings import _get_client, _load_env

# Ensure .env vars (JUDGE_ENABLED, JUDGE_MODEL, etc.) are loaded into os.environ
# at module import time. Brain MCP server triggers .env load via _get_client()
# when embedding, but hook context (prompt-context.py) uses urllib for embeddings
# and never calls _get_client — so without this, hook-side judge would never see
# JUDGE_ENABLED=true from the .env file.
_load_env()

# Soft-fail status codes for transparency in recall output
STATUS_OK = "ok"
STATUS_DISABLED = "fallback:disabled"
STATUS_MIN_CANDIDATES = "fallback:min_candidates"
STATUS_BUDGET = "fallback:budget"
STATUS_TIMEOUT = "fallback:timeout"
STATUS_RATE_LIMIT = "fallback:rate_limit"
STATUS_API_ERROR = "fallback:api_error"
STATUS_PARSE_ERROR = "fallback:parse_error"

# Cache — full-set hash (judge calibrates against the set, not per-pair)
_CACHE_MAX = 64
_judge_cache: OrderedDict[str, list[dict]] = OrderedDict()

# Token pricing per million (gpt-4o-mini defaults; updated if JUDGE_MODEL switches)
_PRICING = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-4o": (2.50, 10.00),
}


def _model() -> str:
    return os.environ.get("JUDGE_MODEL", "gpt-4o-mini")


def _enabled() -> bool:
    return os.environ.get("JUDGE_ENABLED", "false").lower() in ("1", "true", "yes")


def _min_candidates() -> int:
    try:
        return int(os.environ.get("JUDGE_MIN_CANDIDATES", "4"))
    except ValueError:
        return 4


def _budget_usd() -> float:
    try:
        return float(os.environ.get("JUDGE_DAILY_BUDGET_USD", "0.50"))
    except ValueError:
        return 0.50


def _debug() -> bool:
    return os.environ.get("JUDGE_DEBUG", "false").lower() in ("1", "true", "yes")


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int, model: str | None = None) -> float:
    """Compute USD cost from token counts based on model pricing."""
    model = model or _model()
    in_rate, out_rate = _PRICING.get(model, _PRICING["gpt-4o-mini"])
    return (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000


def _cache_key(query: str, candidate_ids: list[str]) -> str:
    """Full-set hash — order-independent on candidate IDs."""
    payload = f"{query}\x00{','.join(sorted(candidate_ids))}"
    return hashlib.md5(payload.encode()).hexdigest()


SYSTEM_PROMPT = """You score memory relevance to a query (0-10 integer scale).

Score on INTENT match, not keyword overlap:
- 10: Memory directly answers/contains key info for query
- 7-9: Strongly related (same domain, related decisions/patterns)
- 4-6: Tangentially related (shared topic, different angle/project/era)
- 1-3: Surface keyword overlap only, contextually unrelated
- 0: Unrelated

CRITICAL:
- Project context matters: a memory about Project A scores LOW for a query about Project B even with shared keywords
- Temporal: query about "current state" prefers recent memories
- Type fit: query for "decisions about X" scores decision-type higher than entity-type mentions of X

Return ONLY JSON: {"scores": [{"id": "...", "score": N}, ...]}"""


def _format_candidates(candidates: list[dict]) -> str:
    """Format candidates with metadata header for judge prompt."""
    lines = []
    for c in candidates:
        tags = c.get("tags") or []
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        tag_str = ",".join(tags[:5]) if tags else "none"
        proj = c.get("project") or "null"
        mtype = c.get("type") or "unknown"
        content = (c.get("content") or "")[:200]
        cid = c.get("id", "")
        # Age computed by caller if available; fall back to created_at substring
        age = c.get("_age_label", c.get("created_at", "")[:10])
        lines.append(f"### [{cid}] {mtype}  tags={tag_str}  age={age}  project={proj}\n{content}")
    return "\n\n".join(lines)


def judge_relevance(
    query: str,
    candidates: list[dict],
    n: int,
) -> tuple[list[dict], str, dict]:
    """Rerank candidates by LLM-judged relevance to query.

    Args:
        query: User query string (already normalized by caller).
        candidates: List of memory dicts from hybrid_search (oversampled pool).
                    Each must have 'id', 'content'; should have 'type', 'tags',
                    'project', 'created_at' for richer context.
        n: Number of top results to return (caller's original k).

    Returns:
        Tuple of (top_n_candidates, status, telemetry).
        - top_n_candidates: candidates reordered by judge score, sliced to n.
                            On fallback, returns RRF top-n unchanged.
        - status: STATUS_* code indicating outcome.
        - telemetry: dict with keys: tokens_in, tokens_out, cost_usd,
                     latency_ms, cache_hit (all ints/floats/bools).
    """
    telemetry = {
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "latency_ms": 0,
        "cache_hit": False,
    }

    if not _enabled():
        return candidates[:n], STATUS_DISABLED, telemetry

    if len(candidates) < _min_candidates():
        return candidates[:n], STATUS_MIN_CANDIDATES, telemetry

    # Cache lookup
    cids = [c.get("id", "") for c in candidates]
    cache_key = _cache_key(query, cids)
    if cache_key in _judge_cache:
        _judge_cache.move_to_end(cache_key)
        cached_order = _judge_cache[cache_key]
        # Reorder current candidates by cached score order
        by_id = {c.get("id", ""): c for c in candidates}
        reordered = [by_id[cid] for cid in cached_order if cid in by_id]
        # Append any candidates not in cache at the end (rare race condition)
        extra = [c for c in candidates if c.get("id", "") not in cached_order]
        result = (reordered + extra)[:n]
        telemetry["cache_hit"] = True
        return result, STATUS_OK, telemetry

    # Build prompt
    user_prompt = f'Query: "{query}"\n\nCandidates:\n{_format_candidates(candidates)}'

    import time
    t0 = time.perf_counter()

    try:
        client = _get_client().with_options(timeout=1.5)
        resp = client.chat.completions.create(
            model=_model(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            seed=42,
        )
    except Exception as e:
        # Soft-fail on any error — return RRF top-n unchanged
        cls = type(e).__name__
        if "Timeout" in cls or "TimeoutError" in cls:
            status = STATUS_TIMEOUT
        elif "RateLimit" in cls:
            status = STATUS_RATE_LIMIT
        else:
            status = STATUS_API_ERROR
        print(f"[judge] {status}: {cls}: {e}", file=sys.stderr)
        telemetry["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return candidates[:n], status, telemetry

    telemetry["latency_ms"] = int((time.perf_counter() - t0) * 1000)

    # Parse response
    try:
        content = resp.choices[0].message.content
        parsed = json.loads(content)
        scores = parsed.get("scores", [])
        # Build id → score map
        score_map = {s["id"]: int(s["score"]) for s in scores if "id" in s and "score" in s}
    except Exception as e:
        print(f"[judge] parse error: {e}", file=sys.stderr)
        return candidates[:n], STATUS_PARSE_ERROR, telemetry

    # Telemetry
    usage = getattr(resp, "usage", None)
    if usage:
        telemetry["tokens_in"] = usage.prompt_tokens
        telemetry["tokens_out"] = usage.completion_tokens
        telemetry["cost_usd"] = estimate_cost_usd(usage.prompt_tokens, usage.completion_tokens)

    # Reorder candidates by judge score (descending). Candidates not scored
    # fall to the end in original RRF order.
    scored = []
    unscored = []
    for c in candidates:
        cid = c.get("id", "")
        if cid in score_map:
            scored.append((score_map[cid], c))
        else:
            unscored.append(c)
    scored.sort(key=lambda t: -t[0])
    ordered = [c for _, c in scored] + unscored

    # Cache result (store ID order for replay on identical query+pool)
    _judge_cache[cache_key] = [c.get("id", "") for c in ordered]
    if len(_judge_cache) > _CACHE_MAX:
        _judge_cache.popitem(last=False)

    return ordered[:n], STATUS_OK, telemetry


def get_budget_status(conn) -> tuple[float, float, bool]:
    """Return (cost_today, budget_limit, has_budget_remaining).

    Reads brain_meta. Auto-resets cost_today if stored date != today.
    """
    today = date.today().isoformat()
    limit = _budget_usd()
    try:
        stored_date = conn.execute(
            "SELECT value FROM brain_meta WHERE key = 'judge_cost_date'"
        ).fetchone()
        cost_row = conn.execute(
            "SELECT value FROM brain_meta WHERE key = 'judge_cost_today'"
        ).fetchone()
        if not stored_date or stored_date[0] != today:
            # New day — reset
            cost_today = 0.0
        else:
            cost_today = float(cost_row[0]) if cost_row else 0.0
    except Exception:
        cost_today = 0.0
    return cost_today, limit, cost_today < limit


def update_budget(conn, cost_usd: float) -> None:
    """Increment judge_cost_today by cost_usd, also bump telemetry counters."""
    today = date.today().isoformat()
    try:
        # Reset date marker if needed
        stored = conn.execute(
            "SELECT value FROM brain_meta WHERE key = 'judge_cost_date'"
        ).fetchone()
        if not stored or stored[0] != today:
            conn.execute(
                "INSERT OR REPLACE INTO brain_meta (key, value) VALUES ('judge_cost_date', ?)",
                (today,),
            )
            conn.execute(
                "INSERT OR REPLACE INTO brain_meta (key, value) VALUES ('judge_cost_today', '0.0')"
            )
        # Increment
        conn.execute(
            """INSERT OR REPLACE INTO brain_meta (key, value)
               VALUES ('judge_cost_today',
                       CAST((COALESCE((SELECT CAST(value AS REAL) FROM brain_meta
                                       WHERE key='judge_cost_today'), 0.0) + ?) AS TEXT))""",
            (cost_usd,),
        )
        conn.commit()
    except Exception:
        pass


def bump_telemetry(conn, telemetry: dict, status: str) -> None:
    """Increment judge_calls_total, tokens, fallback counters in brain_meta."""
    try:
        # Calls total
        conn.execute(
            """INSERT OR REPLACE INTO brain_meta (key, value)
               VALUES ('judge_calls_total',
                       CAST(COALESCE((SELECT CAST(value AS INTEGER) FROM brain_meta
                                      WHERE key='judge_calls_total'), 0) + 1 AS TEXT))"""
        )
        # Tokens
        if telemetry.get("tokens_in", 0) > 0:
            tin = telemetry["tokens_in"]
            tout = telemetry["tokens_out"]
            conn.execute(
                """INSERT OR REPLACE INTO brain_meta (key, value)
                   VALUES ('judge_tokens_total',
                           CAST(COALESCE((SELECT CAST(value AS INTEGER) FROM brain_meta
                                          WHERE key='judge_tokens_total'), 0) + ? AS TEXT))""",
                (tin + tout,),
            )
        # Fallback counter
        if status != STATUS_OK:
            conn.execute(
                """INSERT OR REPLACE INTO brain_meta (key, value)
                   VALUES ('judge_fallback_total',
                           CAST(COALESCE((SELECT CAST(value AS INTEGER) FROM brain_meta
                                          WHERE key='judge_fallback_total'), 0) + 1 AS TEXT))"""
            )
        conn.commit()
    except Exception:
        pass
