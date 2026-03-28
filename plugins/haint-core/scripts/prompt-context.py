#!/usr/bin/env python3
"""UserPromptSubmit: Inject relevant brain context per user prompt.

Architecture: embed once → search twice (general hybrid + tool vector).
Zero additional API cost vs original (same single embedding call).

Dedup: tracks injected memory IDs in /tmp cache file. Only injects NEW
memories not already in the conversation's context window. Prevents
duplicate system-reminders accumulating tokens across prompts.

Phase 1: Hybrid search (FTS5 + vector RRF) for general memories
  - Project-scoped: (project = ? OR project IS NULL)
  - Type-weighted: decisions/discoveries/patterns rank before sessions
  - Max 3 results

Phase 2: Vector search for Semantic Toolbox (type='tool' only)
  - Max 5 results

Returns hookSpecificOutput JSON with additionalContext for Claude's context window.
"""

import hashlib
import json
import os
import sqlite3
import struct
import sys
import time
import urllib.request
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"
BRAIN_ENV = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / ".env"

# General memory config
MAX_GENERAL_RESULTS = 3
MAX_CONTENT_LEN = 200
MIN_PROMPT_LENGTH = 10

# Tool search config
MAX_TOOL_RESULTS = 5

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

# sqlite-vec: optional, enables vector search
try:
    import sqlite_vec

    HAS_VEC = True
except ImportError:
    HAS_VEC = False


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


def save_cache(new_ids: set[str], current_prompt: str) -> None:
    """Save injected IDs + extract and accumulate keywords from current prompt."""
    path = _cache_path()
    try:
        cache = _load_cache()
        # Merge IDs
        all_ids = set(cache.get("ids", [])) | new_ids
        if len(all_ids) > CACHE_MAX_IDS:
            all_ids = set(list(all_ids)[-CACHE_MAX_IDS:])
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
    query_words = [w for w in words if len(w) > 2 and w.isalnum()]
    if not query_words:
        return []

    fts_query = " OR ".join(query_words[:5])
    try:
        rows = conn.execute(
            """SELECT m.id, m.content, m.type, rank
               FROM memory_fts f
               JOIN memories m ON m.id = f.memory_id
               WHERE memory_fts MATCH ?
                 AND m.type != 'tool'
                 AND (m.project = ? OR m.project IS NULL)
               ORDER BY rank
               LIMIT 20""",
            (fts_query, project),
        ).fetchall()
        return [
            {"id": r["id"], "content": r["content"], "type": r["type"], "fts_rank": i}
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
            SELECT m.id, m.content, m.type, v.distance
            FROM vec_results v
            JOIN memories m ON m.id = v.memory_id
            WHERE m.type != 'tool'
              AND (m.project = :project OR m.project IS NULL)
            ORDER BY v.distance
            LIMIT 20""",
            {"embedding": emb_bytes, "fetch_k": VEC_FETCH_K, "project": project},
        ).fetchall()
        return [
            {"id": r["id"], "content": r["content"], "type": r["type"], "vec_rank": i}
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

    if embedding is None:
        for r in fts_results:
            r["score"] = 1.0 / (RRF_K + r["fts_rank"])
            r["score"] -= TYPE_PRIORITY.get(r["type"], 2) * 0.001
        fts_results.sort(key=lambda x: -x["score"])
        return [
            {"id": r["id"], "content": r["content"][:MAX_CONTENT_LEN], "type": r["type"]}
            for r in fts_results[:MAX_GENERAL_RESULTS]
        ]

    vec_results = _vec_search_general(conn, embedding, project)

    scores: dict[str, dict] = {}

    for r in fts_results:
        mid = r["id"]
        scores[mid] = {
            "id": mid,
            "content": r["content"],
            "type": r["type"],
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
                "score": vec_score,
            }

    for entry in scores.values():
        entry["score"] -= TYPE_PRIORITY.get(entry["type"], 2) * 0.001

    ranked = sorted(scores.values(), key=lambda x: -x["score"])
    return [
        {"id": r["id"], "content": r["content"][:MAX_CONTENT_LEN], "type": r["type"]}
        for r in ranked[:MAX_GENERAL_RESULTS]
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
            {"embedding": emb_bytes, "fetch_k": VEC_FETCH_K, "limit": MAX_TOOL_RESULTS},
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


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    prompt = get_prompt()
    if not prompt or len(prompt.strip()) < MIN_PROMPT_LENGTH:
        sys.exit(0)

    stripped = prompt.strip()
    if stripped.startswith("/") or stripped.startswith("!"):
        sys.exit(0)

    project = detect_project()
    injected = load_injected_ids()
    context_kw = load_context_keywords()
    sections = []
    new_ids: set[str] = set()

    # Build combined query from current prompt + accumulated keywords
    combined = build_combined_query(stripped, context_kw)

    # Embed once — reuse for both phases
    embedding = None
    if HAS_VEC:
        api_key = get_api_key()
        if api_key:
            embedding = embed_prompt(combined, api_key)

    conn = connect_db(need_vec=(embedding is not None))
    if conn:
        # Phase 1: General memories — hybrid FTS5 + vector RRF
        general = search_general_hybrid(conn, combined, embedding, project)
        new_general = [r for r in general if r["id"] not in injected]
        if new_general:
            lines = [f"- [{r['type']}] {r['content']}" for r in new_general]
            sections.append("Brain context:\n" + "\n".join(lines))
            new_ids.update(r["id"] for r in new_general)

        # Phase 2: Semantic Toolbox — vector search for relevant tools
        if embedding is not None:
            tools = search_tools_vector(conn, embedding)
            new_tools = [t for t in tools if t["id"] not in injected]
            if new_tools:
                lines = [f"- {t['name']}: {t['content']}" for t in new_tools]
                sections.append("Relevant tools:\n" + "\n".join(lines))
                new_ids.update(t["id"] for t in new_tools)

        conn.close()

    # Save IDs + current prompt to cache (always save prompt for multi-turn)
    save_cache(new_ids, stripped)

    if not sections:
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n\n".join(sections),
        }
    }
    print(json.dumps(output))
