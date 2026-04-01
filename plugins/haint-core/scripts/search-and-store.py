#!/usr/bin/env python3
"""PostToolUse: Auto-persist WebSearch/WebFetch results to brain.db.

Parses tool_result from stdin, extracts key content, embeds, and writes to brain.db.
Still prints reminder for Claude to save deeper analysis if warranted.
"""

import json
import sqlite3
import struct
import sys
import uuid
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"
BRAIN_SRC = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / "src"

# Max content to store per search result
MAX_RESULT_CHARS = 500
MAX_TOTAL_CHARS = 1500


def get_hook_input() -> dict | None:
    """Read hook input from stdin."""
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return None


def _get_tool_result(data: dict) -> str:
    """Extract tool result text, handling both string and object formats."""
    for field in ("tool_result", "tool_response"):
        val = data.get(field)
        if val:
            return val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
    return ""


def _distill_to_facts(raw_content: str, tool_type: str) -> str:
    """P2: Atomic decomposition — distill raw search results into key facts.

    Uses a lightweight LLM call to extract 1-3 self-contained facts from
    raw search/fetch output. Each fact is context-independent (no pronouns,
    no "the above", dates resolved to absolute).

    Falls back to truncated raw content if LLM call fails.
    """
    try:
        import openai
        import os

        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        if not client.api_key:
            return raw_content[:MAX_TOTAL_CHARS]

        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{
                "role": "user",
                "content": f"""Extract 1-3 key facts from this {tool_type} result. Rules:
- Each fact must be self-contained (no pronouns, no "the article says")
- Include specific names, versions, numbers, dates
- Skip generic/obvious information
- If nothing specific worth remembering → respond with just "SKIP"
- Format: one fact per line, no bullets or numbering

Content:
{raw_content[:2000]}"""
            }],
            max_tokens=200,
            temperature=0,
        )
        facts = response.choices[0].message.content.strip()
        if facts.upper() == "SKIP" or len(facts) < 20:
            return ""  # Signal to skip saving entirely
        return facts
    except Exception:
        return raw_content[:MAX_TOTAL_CHARS]  # Fallback: raw truncated


def extract_search_content(data: dict) -> tuple[str, str] | None:
    """Extract saveable content from research tool results.

    P2: Distills raw content into atomic facts before saving.
    Returns (content_to_save, tool_type) or None if nothing worth saving.
    """
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_result = _get_tool_result(data)

    if not tool_result:
        return None

    if tool_name == "WebSearch":
        query = tool_input.get("query", "unknown query")
        raw = f"Web search: \"{query}\"\n{tool_result[:MAX_TOTAL_CHARS]}"
        distilled = _distill_to_facts(raw, "web-search")
        if not distilled:
            return None  # LLM said SKIP — nothing worth saving
        content = f"Search [{query[:80]}]: {distilled}"
        return content, "web-search"

    elif tool_name == "WebFetch":
        url = tool_input.get("url", "unknown URL")
        raw = f"Web fetch: {url}\n{tool_result[:MAX_TOTAL_CHARS]}"
        distilled = _distill_to_facts(raw, "web-fetch")
        if not distilled:
            return None
        content = f"Fetch [{url[:80]}]: {distilled}"
        return content, "web-fetch"

    elif tool_name == "mcp__claude_ai_Context7__query-docs":
        library_id = tool_input.get("libraryId", "unknown")
        topic = tool_input.get("topic", "unknown topic")
        raw = f"Context7 docs: {library_id} — {topic}\n{tool_result[:MAX_TOTAL_CHARS]}"
        distilled = _distill_to_facts(raw, "context7")
        if not distilled:
            return None
        content = f"Docs [{library_id}: {topic[:60]}]: {distilled}"
        return content, "context7"

    return None


def _is_duplicate(conn, content: str, threshold: float = 0.75) -> bool:
    """P1: Entropy-aware filtering — check if content is semantically redundant.

    Computes embedding and checks cosine similarity against top-3 existing memories.
    If any sim >= threshold, this content adds no new information → skip.
    """
    try:
        sys.path.insert(0, str(BRAIN_SRC))
        from haingt_brain.embeddings import embed_text
        from haingt_brain.db import serialize_embedding

        emb = embed_text(content)
        emb_bytes = serialize_embedding(emb)

        neighbors = conn.execute(
            "SELECT memory_id, distance FROM memory_vectors WHERE embedding MATCH ? AND k = 3",
            (emb_bytes,),
        ).fetchall()

        if not neighbors:
            return False

        # Convert L2 distance to approximate cosine similarity for normalized embeddings
        import struct, math
        for nb in neighbors:
            nb_vec = conn.execute(
                "SELECT embedding FROM memory_vectors WHERE memory_id = ?",
                (nb["memory_id"],),
            ).fetchone()
            if not nb_vec:
                continue
            # Direct cosine computation
            n = len(emb_bytes) // 4
            a = struct.unpack(f"{n}f", emb_bytes)
            b = struct.unpack(f"{n}f", nb_vec["embedding"])
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a > 0 and norm_b > 0:
                sim = dot / (norm_a * norm_b)
                if sim >= threshold:
                    return True
        return False
    except Exception:
        return False  # On failure, allow save (safe default)


def save_to_brain(content: str, tool_type: str, project: str | None = None) -> str:
    """Write search result to brain.db with embedding.

    Returns: "saved", "skipped:duplicate", "skipped:too_short", or "error".
    """
    if not DB_PATH.exists():
        return "error"

    # P1: Skip content that's too short to be useful
    if len(content.strip()) < 80:
        return "skipped:too_short"

    try:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except (ImportError, Exception):
            pass  # FTS-only if sqlite-vec unavailable
        conn.row_factory = sqlite3.Row

        # P1: Entropy-aware dedup — skip if brain already has similar content
        if _is_duplicate(conn, content):
            conn.close()
            return "skipped:duplicate"

        memory_id = uuid.uuid4().hex[:12]
        tags = json.dumps([tool_type, "auto-captured"])
        source = "search-and-store-hook"
        meta = json.dumps({"source": source})

        # Compute importance from type × source
        importance = 0.5  # default
        try:
            sys.path.insert(0, str(BRAIN_SRC))
            from haingt_brain.importance import compute_initial_importance
            importance = compute_initial_importance("discovery", source)
        except Exception:
            pass

        conn.execute(
            """INSERT INTO memories (id, content, type, tags, project, metadata, importance)
               VALUES (?, ?, 'discovery', ?, ?, ?, ?)""",
            (memory_id, content, tags, project, meta, importance),
        )

        # Insert into FTS
        conn.execute(
            "INSERT INTO memory_fts (memory_id, content, tags, project) VALUES (?, ?, ?, ?)",
            (memory_id, content, tags, project or ""),
        )

        # Try to embed (import from brain source)
        try:
            sys.path.insert(0, str(BRAIN_SRC))
            from haingt_brain.embeddings import embed_text
            from haingt_brain.db import serialize_embedding

            embedding = embed_text(content)
            emb_bytes = serialize_embedding(embedding)
            conn.execute(
                "INSERT INTO memory_vectors (memory_id, embedding) VALUES (?, ?)",
                (memory_id, emb_bytes),
            )
        except Exception:
            pass  # FTS-only is still useful, embedding is bonus

        conn.commit()
        conn.close()
        return "saved"
    except Exception:
        return "error"


if __name__ == "__main__":
    data = get_hook_input()
    if not data:
        sys.exit(0)

    result = extract_search_content(data)
    if not result:
        sys.exit(0)

    content, tool_type = result

    # Detect project from cwd
    cwd = Path.cwd()
    projects_dir = Path.home() / "Projects"
    try:
        project = cwd.relative_to(projects_dir).parts[0]
    except (ValueError, IndexError):
        project = None

    result = save_to_brain(content, tool_type, project)
    if result == "saved":
        print(f"Auto-captured {tool_type} result to brain. Consider brain_save for deeper analysis if this finding is significant.")
    elif result.startswith("skipped"):
        pass  # Silent skip — no noise in output for duplicates/too-short
    else:
        print("Consider: brain_save this finding as type 'discovery' if it's reusable.")
