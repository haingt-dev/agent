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


def extract_search_content(data: dict) -> tuple[str, str] | None:
    """Extract saveable content from research tool results.

    Returns (content_to_save, tool_type) or None if nothing worth saving.
    """
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_result = _get_tool_result(data)

    if not tool_result:
        return None

    if tool_name == "WebSearch":
        query = tool_input.get("query", "unknown query")
        content = f"Web search: \"{query}\"\n{tool_result[:MAX_TOTAL_CHARS]}"
        return content, "web-search"

    elif tool_name == "WebFetch":
        url = tool_input.get("url", "unknown URL")
        content = f"Web fetch: {url}\n{tool_result[:MAX_TOTAL_CHARS]}"
        return content, "web-fetch"

    elif tool_name == "mcp__claude_ai_Context7__query-docs":
        library_id = tool_input.get("libraryId", "unknown")
        topic = tool_input.get("topic", "unknown topic")
        content = f"Context7 docs: {library_id} — {topic}\n{tool_result[:MAX_TOTAL_CHARS]}"
        return content, "context7"

    return None


def save_to_brain(content: str, tool_type: str, project: str | None = None) -> bool:
    """Write search result to brain.db with embedding."""
    if not DB_PATH.exists():
        return False

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
        return True
    except Exception:
        return False


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

    saved = save_to_brain(content, tool_type, project)
    if saved:
        print(f"Auto-captured {tool_type} result to brain. Consider brain_save for deeper analysis if this finding is significant.")
    else:
        print("Consider: brain_save this finding as type 'discovery' if it's reusable.")
