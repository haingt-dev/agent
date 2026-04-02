#!/usr/bin/env python3
"""UserPromptSubmit: Inject relevant brain context per user prompt.

Architecture: FTS5 pre-filter for tools, embed once for general memories.
Phase 2 skips the embedding API call when FTS5 returns enough tool results (~80%
of prompts), saving ~$0.001/prompt and ~300ms latency.

Dedup: tracks injected memory IDs in /tmp cache file. Only injects NEW
memories not already in the conversation's context window. Prevents
duplicate system-reminders accumulating tokens across prompts.

Over-fetch + post-filter dedup: searches return more results than needed
(FETCH_K > MAX_RESULTS), then dedup filters already-seen IDs, then top-K
selects from remaining. This ensures deduped slots get filled by next-best
results instead of being wasted.

Token cap: tracks cumulative injected chars across session. Stops injecting
when budget (MAX_INJECTED_CHARS) is exhausted, preventing context bloat
in long conversations. Resets with cache TTL (2 hours).

Phase 1: Hybrid search (FTS5 + vector RRF) for general memories
  - Project-scoped: (project = ? OR project IS NULL)
  - Type-weighted: decisions/discoveries/patterns rank before sessions
  - Over-fetch 8, output max 3

Phase 2: Semantic Toolbox (type='tool' only)
  - FTS5 first (~1ms, free): if 3+ results → skip embedding
  - Fall back to vector search only when FTS5 returns <3 results
  - Output max 3

Returns hookSpecificOutput JSON with additionalContext for Claude's context window.
"""

import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"
BRAIN_ENV = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / ".env"

# General memory config
FETCH_K_GENERAL = 8  # over-fetch to compensate for dedup filtering
MAX_GENERAL_RESULTS = 3  # max results after dedup
MAX_CONTENT_LEN = 200
MIN_PROMPT_LENGTH = 10

# Tool search config
FETCH_K_TOOLS = 10  # over-fetch for dedup-free re-ranking
MAX_TOOL_RESULTS = 3  # top-3 tools per prompt

# Token budget caps
MAX_INJECTED_CHARS = 3000  # ~750 tokens, general memories across session
MAX_TOOL_INJECTED_CHARS = 6000  # ~1500 tokens, safety net for tool injections

# Embedding config
EMBED_MODEL = "text-embedding-3-large"
EMBED_DIMS = 3072
EMBED_TIMEOUT = 3  # seconds

# RRF config
RRF_K = 60  # balances FTS5 and vector scores
VEC_FETCH_K = 50  # over-fetch for post-filter

# Dedup + multi-turn config
CACHE_DIR = Path("/tmp")
CACHE_MAX_AGE = 7200  # 2 hours — reset after stale session or compaction
CACHE_MAX_IDS = 100  # cap tracked IDs to prevent unbounded growth
CACHE_MAX_KEYWORDS = 30  # max accumulated context words from recent prompts
CURRENT_PROMPT_MAX_CHARS = 1000  # current prompt keeps full text for embedding
MIN_WORD_LEN = 3  # filter very short words (articles, particles)

# Type priority: lower = higher priority in results
TYPE_PRIORITY = {
    "decision": 0,
    "discovery": 0,
    "pattern": 0,
    "entity": 0,
    "preference": 1,
    "session": 2,
}

# Emotional signal detection — expand query when personal/emotional context detected
# Only unambiguous signals. Avoid short Vietnamese words that appear in technical contexts.
EMOTIONAL_WORD_SIGNALS = {
    "khóc", "buồn", "giận", "tức", "stress", "anxious",
    "crying", "funeral", "grieving", "depressed",
}
EMOTIONAL_PHRASE_SIGNALS = [
    "mệt mỏi", "tâm lý", "cảm xúc", "lo lắng", "đau lòng",
    "ổn định lại", "đám tang", "đám cưới",
    "nói chuyện với vợ", "nói chuyện với duyên",
]
EMOTIONAL_EXPANSION = "emotional family relationships personal reflect"


def detect_emotional_signals(text: str) -> bool:
    """Check if prompt contains emotional/personal signals.
    Uses strip_viet() for fuzzy phrase matching (handles diacritic typos).
    """
    lower = text.lower()
    stripped_text = _strip_viet(text)
    # Phrase-level check (exact + fuzzy via diacritic stripping)
    for phrase in EMOTIONAL_PHRASE_SIGNALS:
        if phrase in lower:
            return True
        if _strip_viet(phrase) in stripped_text:
            return True
    # Single-word check (only unambiguous words)
    words = set(lower.split())
    stripped = {w.strip(",.!?;:'\"()[]{}") for w in words}
    return bool((words | stripped) & EMOTIONAL_WORD_SIGNALS)


# sqlite-vec: optional, enables vector search
try:
    import sqlite_vec

    HAS_VEC = True
except ImportError:
    HAS_VEC = False

# Vietnamese normalizer — imported from brain package (same pattern as entity-extract.py)
_BRAIN_SRC = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / "src"
try:
    sys.path.insert(0, str(_BRAIN_SRC))
    from haingt_brain.vn_normalize import normalize_vn as _normalize_vn
    from haingt_brain.vn_normalize import strip_viet as _strip_viet
except Exception:
    _normalize_vn = lambda x: x  # no-op fallback
    _strip_viet = lambda x: x.lower()  # fallback: just lowercase


# ── Input ─────────────────────────────────────────────────────────────────

def get_prompt() -> str | None:
    """Extract user prompt from hook stdin JSON."""
    try:
        data = json.loads(sys.stdin.read())
        return data.get("prompt", "")
    except Exception:
        return None


def detect_project() -> str | None:
    """Detect project from cwd by walking up to ~/Projects."""
    cwd = Path.cwd()
    projects_dir = Path.home() / "Projects"
    try:
        return cwd.relative_to(projects_dir).parts[0]
    except (ValueError, IndexError):
        return None


def get_api_key() -> str | None:
    """Load OpenAI API key from env or brain's .env file."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    if BRAIN_ENV.exists():
        for line in BRAIN_ENV.read_text().strip().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line.startswith("OPENAI_API_KEY"):
                _, _, val = line.partition("=")
                return val.strip().strip('"').strip("'")
    return None


# ── Dedup ─────────────────────────────────────────────────────────────────

def _cache_path() -> Path:
    """Session-stable cache file path based on cwd."""
    cwd_hash = hashlib.md5(str(Path.cwd()).encode()).hexdigest()[:8]
    return CACHE_DIR / f"brain-prompt-ctx-{cwd_hash}.json"


def _extract_words(text: str) -> list[str]:
    """Extract unique words from text. No stop word filtering needed —
    embedding model handles semantic weighting, FTS5 BM25 handles term frequency.
    Only filters very short words (<3 chars) that are mostly particles/articles.
    """
    words = text.lower().split()
    seen = set()
    result = []
    for w in words:
        if len(w) >= MIN_WORD_LEN and w.isalnum() and w not in seen:
            seen.add(w)
            result.append(w)
    return result


def _load_cache() -> dict:
    """Load cache file (IDs + context keywords)."""
    path = _cache_path()
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("ts", 0) > CACHE_MAX_AGE:
            return {"ids": [], "keywords": []}
        return data
    except Exception:
        return {"ids": [], "keywords": []}


def load_injected_ids() -> set[str]:
    """Load previously injected memory IDs from cache."""
    return set(_load_cache().get("ids", []))


def load_context_keywords() -> list[str]:
    """Load accumulated keywords from recent prompts."""
    return _load_cache().get("keywords", [])


def load_injected_chars() -> int:
    """Load total injected chars from cache."""
    return _load_cache().get("total_chars", 0)


def load_last_tools() -> list[str]:
    """Load last injected tool names for skip-if-unchanged."""
    return _load_cache().get("last_tools", [])


def load_last_memory_ids() -> list[str]:
    """Load last injected general memory IDs for skip-if-unchanged."""
    return _load_cache().get("last_memory_ids", [])


def load_tool_chars() -> int:
    """Load total tool injected chars from cache."""
    return _load_cache().get("tool_chars", 0)


def save_cache(
    new_ids: set[str],
    current_prompt: str,
    new_chars: int = 0,
    tool_names: list[str] | None = None,
    new_tool_chars: int = 0,
    memory_ids: list[str] | None = None,
) -> None:
    """Save injected IDs + keywords + memory chars + tool state + last memory IDs."""
    path = _cache_path()
    try:
        cache = _load_cache()
        # Merge IDs
        all_ids = set(cache.get("ids", [])) | new_ids
        if len(all_ids) > CACHE_MAX_IDS:
            all_ids = set(list(all_ids)[-CACHE_MAX_IDS:])
        # Accumulate total injected chars (memories only)
        total_chars = cache.get("total_chars", 0) + new_chars
        # Tool state
        last_tools = tool_names if tool_names is not None else cache.get("last_tools", [])
        tool_chars = cache.get("tool_chars", 0) + new_tool_chars
        # General memory IDs for skip-if-unchanged
        last_memory_ids = memory_ids if memory_ids is not None else cache.get("last_memory_ids", [])
        # Extract and accumulate keywords (deduped, capped)
        existing_kw = cache.get("keywords", [])
        new_kw = _extract_words(current_prompt)
        # Merge: existing + new, deduplicate, keep most recent up to cap
        seen = set()
        merged = []
        for kw in existing_kw + new_kw:
            if kw not in seen:
                seen.add(kw)
                merged.append(kw)
        merged = merged[-CACHE_MAX_KEYWORDS:]  # keep most recent
        path.write_text(json.dumps({
            "ids": list(all_ids),
            "keywords": merged,
            "total_chars": total_chars,
            "last_tools": last_tools,
            "tool_chars": tool_chars,
            "last_memory_ids": last_memory_ids,
            "ts": time.time(),
        }))
    except Exception:
        pass


# ── Embedding ─────────────────────────────────────────────────────────────

def build_combined_query(current: str, context_keywords: list[str]) -> str:
    """Combine current prompt with accumulated keywords from recent prompts.

    Current prompt: full text (intent + detail).
    Context keywords: distilled signal from recent turns (no filler, no truncation loss).
    """
    query = current[:CURRENT_PROMPT_MAX_CHARS]
    if context_keywords:
        query += " " + " ".join(context_keywords)
    return query


def embed_prompt(text: str, api_key: str) -> list[float] | None:
    """Embed text via OpenAI API using urllib (no external deps beyond stdlib)."""
    try:
        body = json.dumps(
            {"input": text[:2000], "model": EMBED_MODEL, "dimensions": EMBED_DIMS}
        ).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        resp = urllib.request.urlopen(req, timeout=EMBED_TIMEOUT)
        return json.loads(resp.read())["data"][0]["embedding"]
    except Exception:
        return None


# ── Database ──────────────────────────────────────────────────────────────

def connect_db(need_vec: bool = False) -> sqlite3.Connection | None:
    """Connect to brain.db, optionally loading sqlite-vec extension."""
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        if need_vec and HAS_VEC:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


# ── Phase 1: General memories (hybrid FTS5 + vector RRF) ─────────────────

def _fts_search(
    conn: sqlite3.Connection, prompt: str, project: str | None
) -> list[dict]:
    """FTS5 keyword search for general memories with project scoping."""
    words = prompt[:100].split()
    words = [w.strip(",.!?;:'\"()[]{}") for w in words]
    query_words = [w for w in words if len(w) > 2 and w.isalnum()]
    if not query_words:
        return []

    fts_query = " OR ".join(query_words[:5])
    try:
        rows = conn.execute(
            """SELECT m.id, m.content, m.type, m.created_at, m.importance, rank
               FROM memory_fts f
               JOIN memories m ON m.id = f.memory_id
               WHERE memory_fts MATCH ?
                 AND m.type NOT IN ('tool', 'session')
                 AND COALESCE(m.importance, 0.5) >= 0.3
                 AND (m.project = ? OR m.project IS NULL)
               ORDER BY rank
               LIMIT 20""",
            (fts_query, project),
        ).fetchall()
        return [
            {"id": r["id"], "content": r["content"], "type": r["type"],
             "created_at": r["created_at"], "importance": r["importance"] or 0.5,
             "fts_rank": i}
            for i, r in enumerate(rows)
        ]
    except Exception:
        return []


def _vec_search_general(
    conn: sqlite3.Connection, embedding: list[float], project: str | None
) -> list[dict]:
    """Vector similarity search for general memories with project scoping."""
    emb_bytes = struct.pack(f"{len(embedding)}f", *embedding)
    try:
        rows = conn.execute(
            """WITH vec_results AS (
                SELECT memory_id, distance
                FROM memory_vectors
                WHERE embedding MATCH :embedding
                  AND k = :fetch_k
            )
            SELECT m.id, m.content, m.type, m.created_at, m.importance, v.distance
            FROM vec_results v
            JOIN memories m ON m.id = v.memory_id
            WHERE m.type NOT IN ('tool', 'session')
              AND COALESCE(m.importance, 0.5) >= 0.3
              AND (m.project = :project OR m.project IS NULL)
            ORDER BY v.distance
            LIMIT 20""",
            {"embedding": emb_bytes, "fetch_k": VEC_FETCH_K, "project": project},
        ).fetchall()
        return [
            {"id": r["id"], "content": r["content"], "type": r["type"],
             "created_at": r["created_at"], "importance": r["importance"] or 0.5,
             "vec_rank": i}
            for i, r in enumerate(rows)
        ]
    except Exception:
        return []


def search_general_hybrid(
    conn: sqlite3.Connection,
    prompt: str,
    embedding: list[float] | None,
    project: str | None,
) -> list[dict]:
    """Hybrid search with RRF fusion + type weighting. Returns results with IDs."""
    fts_results = _fts_search(conn, prompt, project)
    today_str = date.today().isoformat()

    if embedding is None:
        for r in fts_results:
            r["score"] = 1.0 / (RRF_K + r["fts_rank"])
            imp = r.get("importance", 0.5)
            r["score"] *= (0.7 + 0.3 * imp)
            r["score"] -= TYPE_PRIORITY.get(r["type"], 2) * 0.001
            if r.get("created_at", "")[:10] == today_str:
                r["score"] += 0.005
        fts_results.sort(key=lambda x: (-x["score"], -x.get("importance", 0.5)))
        return [
            {"id": r["id"], "content": r["content"][:MAX_CONTENT_LEN], "type": r["type"],
             "importance": r.get("importance", 0.5)}
            for r in fts_results[:FETCH_K_GENERAL]
        ]

    vec_results = _vec_search_general(conn, embedding, project)

    scores: dict[str, dict] = {}

    for r in fts_results:
        mid = r["id"]
        scores[mid] = {
            "id": mid,
            "content": r["content"],
            "type": r["type"],
            "created_at": r.get("created_at", ""),
            "importance": r.get("importance", 0.5),
            "score": 1.0 / (RRF_K + r["fts_rank"]),
        }

    for r in vec_results:
        mid = r["id"]
        vec_score = 1.0 / (RRF_K + r["vec_rank"])
        if mid in scores:
            scores[mid]["score"] += vec_score
        else:
            scores[mid] = {
                "id": mid,
                "content": r["content"],
                "type": r["type"],
                "created_at": r.get("created_at", ""),
                "importance": r.get("importance", 0.5),
                "score": vec_score,
            }

    for entry in scores.values():
        # Importance-weighted RRF: mild multiplier (0.7 at imp=0, 1.0 at imp=1)
        imp = entry.get("importance", 0.5)
        entry["score"] *= (0.7 + 0.3 * imp)
        entry["score"] -= TYPE_PRIORITY.get(entry["type"], 2) * 0.001
        # Same-day recency boost: today's memories are more likely relevant
        if entry.get("created_at", "")[:10] == today_str:
            entry["score"] += 0.005

    ranked = sorted(scores.values(), key=lambda x: (-x["score"], -x.get("importance", 0.5)))
    return [
        {"id": r["id"], "content": r["content"][:MAX_CONTENT_LEN], "type": r["type"],
         "importance": r.get("importance", 0.5)}
        for r in ranked[:FETCH_K_GENERAL]
    ]


# ── Phase 2: Tool search (vector only) ───────────────────────────────────

def search_tools_vector(
    conn: sqlite3.Connection, embedding: list[float]
) -> list[dict]:
    """Vector similarity search for tool memories (Semantic Toolbox). Returns with IDs."""
    emb_bytes = struct.pack(f"{len(embedding)}f", *embedding)
    try:
        rows = conn.execute(
            """WITH vec_results AS (
                SELECT memory_id, distance
                FROM memory_vectors
                WHERE embedding MATCH :embedding
                  AND k = :fetch_k
            )
            SELECT m.id, m.content, m.metadata, v.distance
            FROM vec_results v
            JOIN memories m ON m.id = v.memory_id
            WHERE m.type = 'tool'
            ORDER BY v.distance
            LIMIT :limit""",
            {"embedding": emb_bytes, "fetch_k": VEC_FETCH_K, "limit": FETCH_K_TOOLS},
        ).fetchall()

        results = []
        for r in rows:
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
            results.append({
                "id": r["id"],
                "name": meta.get("name", "unknown"),
                "content": r["content"],
            })
        return results
    except Exception:
        return []


def _fts5_tool_search(conn: sqlite3.Connection, query: str, limit: int = 3) -> list[dict]:
    """Fast FTS5 search for tools. Returns [] if no good matches or on error.

    Used as a pre-filter before the embedding API call — if FTS5 returns
    enough results (>= limit), the caller skips the vector search entirely,
    saving ~$0.001 per prompt and ~300ms of latency.
    """
    # Sanitize query for FTS5 (remove special chars that break MATCH syntax)
    safe_query = re.sub(r'[^\w\s]', ' ', query)
    words = safe_query.split()
    if not words:
        return []

    # Build FTS5 OR query from first 5 words (longer queries risk FTS5 parse errors)
    fts_query = " OR ".join(words[:5])

    try:
        rows = conn.execute(
            """SELECT m.id, m.content, m.metadata, rank
               FROM memory_fts
               JOIN memories m ON m.id = memory_fts.memory_id
               WHERE memory_fts MATCH ?
                 AND m.type = 'tool'
               ORDER BY rank
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()

        results = []
        for r in rows:
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
            results.append({
                "id": r["id"],
                "name": meta.get("name", "unknown"),
                "content": r["content"],
            })
        return results
    except Exception:
        return []  # FTS5 failure (syntax error, etc.) → fall back to vector


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    prompt = get_prompt()
    if not prompt or len(prompt.strip()) < MIN_PROMPT_LENGTH:
        sys.exit(0)

    stripped = prompt.strip()
    if stripped.startswith("/") or stripped.startswith("!"):
        sys.exit(0)

    # Normalize Vietnamese Telex leaks before search + embedding
    normalized = _normalize_vn(stripped)

    project = detect_project()
    injected = load_injected_ids()
    context_kw = load_context_keywords()
    budget_used = load_injected_chars()
    budget_remaining = max(0, MAX_INJECTED_CHARS - budget_used)
    sections = []
    new_ids: set[str] = set()
    new_chars = 0

    # Build combined query from normalized prompt + accumulated keywords
    combined = build_combined_query(normalized, context_kw)

    # Expand query when emotional/personal signals detected
    if detect_emotional_signals(normalized):
        combined += " " + EMOTIONAL_EXPANSION

    # Embed once — reuse for both phases
    embedding = None
    if HAS_VEC:
        api_key = get_api_key()
        if api_key:
            embedding = embed_prompt(combined, api_key)

    conn = connect_db(need_vec=(embedding is not None))
    memory_ids_to_save = None
    if conn and budget_remaining > 0:
        # Phase 1: General memories — over-fetch, dedup, top-K, token cap
        general = search_general_hybrid(conn, combined, embedding, project)
        new_general = [r for r in general if r["id"] not in injected]
        new_general = new_general[:MAX_GENERAL_RESULTS]  # top-K after dedup
        # Apply token cap
        capped_general = []
        capped_chars = 0
        for r in new_general:
            entry_len = len(r["content"]) + len(r["type"]) + 10  # overhead
            if capped_chars + entry_len > budget_remaining:
                break
            capped_general.append(r)
            capped_chars += entry_len

        # Skip-if-unchanged: avoid re-injecting same memories on consecutive prompts
        # Only skip after at least one previous injection (total_chars > 0) and
        # when the cache has a non-empty last_memory_ids (not the first prompt).
        prev_memory_ids = load_last_memory_ids()
        current_memory_ids = [r["id"] for r in capped_general]
        if current_memory_ids and current_memory_ids == prev_memory_ids and budget_used > 0:
            # Same memories as last prompt — skip injection, preserve existing context
            pass
        elif capped_general:
            lines = [f"- [{r['type']}] {r['content']}" for r in capped_general]
            sections.append("Brain context:\n" + "\n".join(lines))
            new_ids.update(r["id"] for r in capped_general)
            new_chars += capped_chars
            memory_ids_to_save = current_memory_ids

        # Phase 2: Semantic Toolbox — FTS5 pre-filter, fall back to vector if needed
        # Tools refresh per-prompt (no dedup), but skip injection when results identical
        tool_names_to_save = None
        new_tool_chars = 0
        prev_tools = load_last_tools()
        tool_budget_used = load_tool_chars()

        # Try FTS5 first (free, ~1ms) — avoids embedding API call ~80% of the time
        tools = _fts5_tool_search(conn, normalized, limit=MAX_TOOL_RESULTS)
        if len(tools) < MAX_TOOL_RESULTS and embedding is not None:
            # FTS5 returned insufficient results — fall back to vector search
            tools = search_tools_vector(conn, embedding)

        tools = tools[:MAX_TOOL_RESULTS]
        current_tool_names = [t["name"] for t in tools]
        # Skip if same tools as last prompt (avoid redundant system-reminders)
        if current_tool_names != prev_tools and tools:
            tool_text = "\n".join(f"- {t['name']}: {t['content']}" for t in tools)
            new_tool_chars = len(tool_text)
            if tool_budget_used + new_tool_chars <= MAX_TOOL_INJECTED_CHARS:
                sections.append("Relevant tools:\n" + tool_text)
        tool_names_to_save = current_tool_names

        conn.close()

    # Save IDs + normalized prompt + chars + tool state + memory IDs to cache
    save_cache(new_ids, normalized, new_chars, tool_names_to_save, new_tool_chars, memory_ids_to_save)

    if not sections:
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n\n".join(sections),
        }
    }
    print(json.dumps(output))
