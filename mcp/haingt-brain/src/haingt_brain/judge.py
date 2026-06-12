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
- Candidates scored <= JUDGE_DROP_MAX (default 3) are DROPPED, not just
  demoted — an empty recall beats confidently returned noise
- Timeout JUDGE_TIMEOUT_S (default 6s) per API call; one flex->default retry
"""

import hashlib
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from collections import OrderedDict
from datetime import date

from .embeddings import _load_env

# Ensure .env vars (JUDGE_ENABLED, JUDGE_MODEL, etc.) are loaded into os.environ
# at module import time. Brain MCP server triggers .env load via _get_client()
# when embedding, but hook context (prompt-context.py) uses urllib for embeddings
# and never calls _get_client — so without this, hook-side judge would never see
# JUDGE_ENABLED=true from the .env file.
_load_env()

# Judge uses urllib directly (NOT openai SDK) — same pattern as
# prompt-context.py's embed_prompt and llm_classify. Reason: hook context runs
# in fresh process per prompt, and openai SDK's httpx pool initialization adds
# ~2-3s cold-start latency. urllib has minimal overhead (~50ms TCP+TLS).
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

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

# Token pricing per million tokens (input, output) at standard tier.
# Flex tier applies 50% discount; cached input tokens are 10% of standard rate
# (handled at OpenAI's billing layer — we just halve when service_tier=flex).
_PRICING = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-4o": (2.50, 10.00),
}


def _model() -> str:
    return os.environ.get("JUDGE_MODEL", "gpt-5.4-nano")


def _service_tier() -> str | None:
    """OpenAI service tier — 'flex' = 50% discount + variable latency.
    Set JUDGE_SERVICE_TIER=default to disable. Returns None if disabled.
    """
    tier = os.environ.get("JUDGE_SERVICE_TIER", "flex").lower()
    if tier in ("flex", "default", "scale", "priority"):
        return tier
    return None


def _enabled() -> bool:
    return os.environ.get("JUDGE_ENABLED", "false").lower() in ("1", "true", "yes")


def _min_candidates() -> int:
    try:
        return int(os.environ.get("JUDGE_MIN_CANDIDATES", "4"))
    except ValueError:
        return 4


def _drop_threshold() -> int:
    """Judge scores at or below this are dropped from results entirely.
    Rubric: 1-3 = surface keyword overlap only, contextually unrelated."""
    try:
        return int(os.environ.get("JUDGE_DROP_MAX", "3"))
    except ValueError:
        return 3


def _timeout_s() -> float:
    """Per-call API timeout. Telemetry showed p50 ~1.5-2.5s; 6s covers the
    tail without letting a recall block for 10-20s like the old 10s x2 did."""
    try:
        return float(os.environ.get("JUDGE_TIMEOUT_S", "6.0"))
    except ValueError:
        return 6.0


def _budget_usd() -> float:
    try:
        return float(os.environ.get("JUDGE_DAILY_BUDGET_USD", "0.50"))
    except ValueError:
        return 0.50


def _debug() -> bool:
    return os.environ.get("JUDGE_DEBUG", "false").lower() in ("1", "true", "yes")


def estimate_cost_usd(
    prompt_tokens: int,
    completion_tokens: int,
    model: str | None = None,
    flex: bool = False,
) -> float:
    """Compute USD cost from token counts based on model pricing.
    Applies 50% Flex tier discount if flex=True. Does NOT account for prompt
    caching discount (10% rate on cached tokens) — caching shows up as lower
    OpenAI billing but isn't tracked here.
    """
    model = model or _model()
    in_rate, out_rate = _PRICING.get(model, _PRICING["gpt-5.4-nano"])
    cost = (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000
    if flex:
        cost *= 0.5
    return cost


def _cache_key(query: str, candidate_ids: list[str]) -> str:
    """Full-set hash — order-independent on candidate IDs."""
    payload = f"{query}\x00{','.join(sorted(candidate_ids))}"
    return hashlib.md5(payload.encode()).hexdigest()


SYSTEM_PROMPT = """You are a memory relevance scorer. Given a user query and N memory candidates, output one integer score (0-10) per candidate, in the same order they appear, as a positional JSON array.

OUTPUT FORMAT (strict, no deviation):
{"s": [N, N, N, ...]}

Where the array length equals the number of input candidates and each integer is 0-10. Do NOT include candidate IDs, explanations, reasoning, prose, markdown, or any field other than "s". No trailing comma. No nested objects.

SCORING RUBRIC (intent match, not keyword overlap):
- 10: Memory directly answers the query or contains the key information needed. Same project, same topic, same era.
- 7-9: Strongly related — same domain, related decision/pattern/discovery, useful supporting context.
- 4-6: Tangentially related — shared keywords or topic but different angle, project, era, or intent.
- 1-3: Surface keyword overlap only. Contextually unrelated despite lexical similarity.
- 0: Unrelated. Different domain entirely.

CRITICAL JUDGMENT RULES:

1. Project context dominates. A memory about Project Alpha scores LOW for a query about Project Beta even if both mention the same technology, library, file, or pattern. Cross-project leaks are the main hard distractor we filter out.

2. Temporal relevance matters. If the query implies "current state" (e.g., "what does X look like now", "current config", "latest decision"), prefer recent memories. An old superseded decision should score low if a newer one exists, even with identical keywords.

3. Type fit matters. A query asking "what decisions have we made about X" should rank decision-type memories higher than entity-type memories that merely mention X. A query asking "how do we implement X" should rank pattern-type memories higher than discovery-type research notes.

4. Specificity beats vagueness. If two memories match the query equally on topic, the one with concrete details (file paths, specific decisions, named modules) scores higher than the abstract or general one.

5. Avoid superficial keyword bait. Memories that share rare keywords with the query but discuss them in unrelated context (different problem domain, different motivation) should score 1-3 not 5-6. Hard distractors look relevant by similarity but reveal mismatch on intent inspection.

6. Old high-importance memories beat new low-importance ones for stable patterns. A 6-month-old preference about workflow has more relevance value than a 2-day-old session summary about an unrelated bug fix.

EXAMPLES OF CORRECT SCORING:

Query: "godot navigation in IronCradle"
- Memory about IronCradle pathfinding implementation: 9 (direct topic + project)
- Memory about godot signals best practices (no project context): 5 (related domain, different angle)
- Memory about chimera-protocol navigation system: 2 (different project — hard distractor)
- Memory about Bookie video pipeline: 0 (unrelated entirely)

Query: "current finance recurring routing"
- Recent decision about routing v3 (this month): 9
- Older decision about routing v1 superseded: 3 (stale, prefer recent)
- Pattern about Todoist API quirks: 4 (related infrastructure, not the question)
- Random preference about color blindness: 0 (unrelated)

Query: "how do we handle hard distractors in the brain"
- Discovery about First Drop of Ink research: 9 (exact match)
- Decision to implement Path C skip gate: 8 (action taken on this exact issue)
- Pattern about consolidation feedback loops: 4 (related brain hygiene, different mechanism)
- Entity record for haingt-brain MCP server: 5 (the affected system)
- Session summary about unrelated debug work: 0

EDGE CASES:

- If two memories are near-duplicates (one superseded by another), score the superseded one 2-3 points lower.
- If a memory is in the same project as the query but on a totally different subsystem, score 4-6 (relevant codebase context but not directly answering).
- If a memory predates the current project state (e.g., from before a major rewrite), score lower for "current state" queries.
- If the query is generic ("how do I do X") and memory is highly specific to a niche project, score 4-5 not 8 (specificity is wrong direction).
- If a memory references a renamed entity (e.g., old name Wildtide vs new name IronCradle), treat them as the same entity but score historical memories slightly lower for "current state" queries.

COMMON FAILURE MODES TO AVOID:

- Ranking by surface similarity. Two memories sharing the word "brain" but discussing different brain implementations (haingt-brain MCP vs claude brain feature) are NOT both high-scoring for either query.
- Conflating types. A query "how do we handle X" wants action-oriented memories (decision, pattern), not catalog-style memories (entity records that merely list X).
- Ignoring project boundaries. Vietnamese/English mixed queries about home-server projects should NOT pull memories about Idea_Vault unless explicitly relevant.
- Over-scoring tagged memories. A memory tagged with the query keyword scores by content match, not by tag presence alone.

OUTPUT REQUIREMENT REMINDER:

Output exactly: {"s": [N, N, N, ...]} with one integer per input candidate, same order, 0-10 scale. No prose. No fields other than "s". No deviation. Now score the candidates."""


def _chat_completion(
    messages: list[dict],
    timeout: float,
    model: str | None = None,
    force_tier: str | None = None,
) -> tuple[dict | None, str]:
    """POST to OpenAI chat completions via urllib. Returns (response_dict, status).

    On success: (parsed_json, STATUS_OK).
    On failure: (None, STATUS_* code). Soft-fail by design — caller treats
    None response as fallback to RRF order.

    Tests should mock this function rather than urllib directly.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None, STATUS_API_ERROR

    payload = {
        "model": model or _model(),
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "seed": 42,
    }
    tier = force_tier if force_tier is not None else _service_tier()
    if tier and tier != "default":
        payload["service_tier"] = tier
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        OPENAI_CHAT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data, STATUS_OK
    except urllib.error.HTTPError as e:
        if e.code == 429:
            status = STATUS_RATE_LIMIT
        else:
            status = STATUS_API_ERROR
        print(f"[judge] {status}: HTTP {e.code}: {e.reason}", file=sys.stderr)
        return None, status
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        print(f"[judge] {STATUS_TIMEOUT}: {type(e).__name__}: {e}", file=sys.stderr)
        return None, STATUS_TIMEOUT
    except Exception as e:
        print(f"[judge] {STATUS_API_ERROR}: {type(e).__name__}: {e}", file=sys.stderr)
        return None, STATUS_API_ERROR


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

    # Cache lookup. Key is a full-set hash, so a hit implies the identical
    # candidate set — the cached order already reflects judge drops; do NOT
    # re-append candidates missing from it (those were dropped as noise).
    cids = [c.get("id", "") for c in candidates]
    cache_key = _cache_key(query, cids)
    if cache_key in _judge_cache:
        _judge_cache.move_to_end(cache_key)
        cached_order = _judge_cache[cache_key]
        by_id = {c.get("id", ""): c for c in candidates}
        result = [by_id[cid] for cid in cached_order if cid in by_id][:n]
        telemetry["cache_hit"] = True
        return result, STATUS_OK, telemetry

    # Build prompt
    user_prompt = f'Query: "{query}"\n\nCandidates:\n{_format_candidates(candidates)}'

    import time
    t0 = time.perf_counter()

    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    used_flex = _service_tier() == "flex"
    timeout = _timeout_s()
    raw_resp, status = _chat_completion(messages=msgs, timeout=timeout)
    # Flex tier is best-effort (50% off) → transient api_error/timeout/rate_limit
    # under load. Retry once on the reliable default tier before falling to RRF.
    if status in (STATUS_API_ERROR, STATUS_TIMEOUT, STATUS_RATE_LIMIT) and used_flex:
        raw_resp, status = _chat_completion(messages=msgs, timeout=timeout, force_tier="default")
        if status == STATUS_OK:
            used_flex = False  # retry billed at full default-tier price
    telemetry["latency_ms"] = int((time.perf_counter() - t0) * 1000)

    if status != STATUS_OK:
        return candidates[:n], status, telemetry

    # Parse response — compact positional array {"s": [N, N, N, ...]}
    # Map back to candidate IDs by index. Defensive on length mismatch.
    try:
        content = raw_resp["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        scores_list = parsed.get("s", [])
        if not isinstance(scores_list, list):
            raise ValueError(f"expected list for 's', got {type(scores_list).__name__}")
        score_map: dict[str, int] = {}
        for i, c in enumerate(candidates):
            if i < len(scores_list):
                try:
                    score_map[c.get("id", "")] = int(scores_list[i])
                except (TypeError, ValueError):
                    pass  # leave unscored — falls to RRF tail
    except Exception as e:
        print(f"[judge] parse error: {e}", file=sys.stderr)
        return candidates[:n], STATUS_PARSE_ERROR, telemetry

    # Telemetry — apply Flex discount if service_tier=flex
    usage = raw_resp.get("usage") or {}
    if usage.get("prompt_tokens"):
        flex_active = used_flex
        telemetry["tokens_in"] = usage["prompt_tokens"]
        telemetry["tokens_out"] = usage.get("completion_tokens", 0)
        telemetry["cost_usd"] = estimate_cost_usd(
            usage["prompt_tokens"], usage.get("completion_tokens", 0),
            flex=flex_active,
        )

    # Reorder candidates by judge score (descending), DROPPING anything at or
    # below the threshold (rubric: <=3 = keyword-bait, contextually unrelated).
    # Unscored candidates (length-mismatch tail) keep their RRF order at the
    # end — defensive, never drop what the judge didn't actually score.
    threshold = _drop_threshold()
    scored = []
    unscored = []
    dropped = 0
    for c in candidates:
        cid = c.get("id", "")
        if cid in score_map:
            if score_map[cid] <= threshold:
                dropped += 1
            else:
                scored.append((score_map[cid], c))
        else:
            unscored.append(c)
    scored.sort(key=lambda t: -t[0])
    ordered = [c for _, c in scored] + unscored
    if _debug() and dropped:
        print(f"[judge] dropped {dropped}/{len(candidates)} candidates <= {threshold}", file=sys.stderr)

    # Cache result (post-drop ID order for replay on identical query+pool)
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
        # Fallback counter (+ per-reason breakdown so api_error can be told
        # apart from benign min_candidates skips)
        if status != STATUS_OK:
            conn.execute(
                """INSERT OR REPLACE INTO brain_meta (key, value)
                   VALUES ('judge_fallback_total',
                           CAST(COALESCE((SELECT CAST(value AS INTEGER) FROM brain_meta
                                          WHERE key='judge_fallback_total'), 0) + 1 AS TEXT))"""
            )
            reason = status.split(":", 1)[-1]  # "fallback:api_error" -> "api_error"
            fb_key = f"judge_fb_{reason}"
            conn.execute(
                """INSERT OR REPLACE INTO brain_meta (key, value)
                   VALUES (?, CAST(COALESCE((SELECT CAST(value AS INTEGER) FROM brain_meta
                                             WHERE key=?), 0) + 1 AS TEXT))""",
                (fb_key, fb_key),
            )
        # Latency ring buffer (last 100 non-zero samples) → enables p50/p95.
        # latency_ms is set on the real API path incl. timeouts (the tail we
        # care about); cache hits / disabled / min_candidates report 0 and skip.
        lat = telemetry.get("latency_ms", 0)
        if lat and lat > 0:
            row = conn.execute(
                "SELECT value FROM brain_meta WHERE key='judge_latency_samples'"
            ).fetchone()
            try:
                samples = json.loads(row[0]) if row and row[0] else []
                if not isinstance(samples, list):
                    samples = []
            except Exception:
                samples = []
            samples.append(int(lat))
            samples = samples[-100:]
            conn.execute(
                "INSERT OR REPLACE INTO brain_meta (key, value) VALUES ('judge_latency_samples', ?)",
                (json.dumps(samples),),
            )
        conn.commit()
    except Exception:
        pass
