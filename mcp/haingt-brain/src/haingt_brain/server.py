"""haingt-brain MCP server: Memory-first architecture with semantic search."""

import json
import sqlite3

from mcp.server.fastmcp import FastMCP

from . import db
from .tools.forget import brain_forget as _forget
from .tools.graph import brain_graph as _graph
from .tools.index import brain_index as _index
from .tools.outline import brain_outline as _outline
from .tools.radar import brain_radar as _radar
from .tools.recall import brain_recall as _recall
from .tools.save import brain_save as _save
from .tools.update import brain_update as _update
from .tools.session import (
    brain_session_save as _session_save,
    brain_session_start as _session_start,
    brain_session_status as _session_status,
)
from .tools.toolbox import brain_tools as _tools

# Initialize MCP server
mcp = FastMCP(
    "haingt-brain",
    instructions="Memory-first MCP server with semantic search, knowledge graph, and Semantic Toolbox",
)

# Database connection (lazy init)
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = db.connect()
        db.init_schema(_conn)
    return _conn


# ── brain_save ──────────────────────────────────────────────────────────────

@mcp.tool()
def brain_save(
    content: str,
    type: str,
    tags: list[str] | None = None,
    project: str | None = None,
    metadata: str | dict | None = None,
    relations: str | list | None = None,
) -> str:
    """Save a memory with automatic embedding for semantic search.

    Use this to persist decisions, discoveries, patterns, entities, or preferences.
    Memories are searchable via brain_recall using natural language.

    Args:
        content: The text content to remember. Be specific and descriptive.
        type: Memory type — one of: decision, discovery, pattern, entity, preference, session, tool
        tags: Optional tags for filtering (e.g., ["python", "architecture"]).
        project: Project scope (omit for global memories accessible everywhere).
        metadata: Extra data (JSON string or dict).
                  Use {"source": "reflect|wrap|manual|hook|research|mentor"} to set importance weighting.
        relations: List of {target_id, relation_type, weight?} (JSON string or list).
                   relation_type: causes, fixes, contradicts, relates_to, used_in, part_of, supersedes
    """
    meta = json.loads(metadata) if isinstance(metadata, str) else metadata
    rels = json.loads(relations) if isinstance(relations, str) else relations

    result = _save(get_conn(), content, type, tags, project, meta, rels)
    return json.dumps(result, indent=2)


# ── brain_recall ────────────────────────────────────────────────────────────

@mcp.tool()
def brain_recall(
    query: str,
    type: str | None = None,
    project: str | None = None,
    k: int = 5,
    time_range: str | None = None,
) -> str:
    """Search memories using hybrid semantic + keyword search.

    Use BEFORE starting work to find prior decisions, patterns, and context.
    Returns the most relevant memories ranked by combined keyword and meaning match.

    Args:
        query: Natural language search query. Be descriptive for better results.
        type: Filter by memory type (decision, discovery, pattern, entity, preference, session, tool).
        project: Filter by project. Omit to search all (global + project-scoped).
        k: Number of results (default 5).
        time_range: SQLite time modifier to filter recent memories (e.g., '-7 days', '-30 days').
    """
    results = _recall(get_conn(), query, type, project, k, time_range)
    if not results:
        return "No memories found matching your query."
    return json.dumps(results, indent=2, ensure_ascii=False)


# ── brain_forget ────────────────────────────────────────────────────────────

@mcp.tool()
def brain_forget(memory_id: str) -> str:
    """Delete a memory by ID. Removes the memory, its embedding, FTS entry, and all relationships.

    Use to clean up incorrect, outdated, or duplicate memories.

    Args:
        memory_id: The ID of the memory to delete (from brain_recall results).
    """
    result = _forget(get_conn(), memory_id)
    return json.dumps(result, indent=2)


# ── brain_update ───────────────────────────────────────────────────────────

@mcp.tool()
def brain_update(
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    metadata: str | dict | None = None,
) -> str:
    """Update a memory's content, tags, or metadata while preserving its ID and history.

    Keeps access_count, created_at, and relations intact. Only provided fields are changed.
    If content changes, the embedding and FTS entry are automatically re-generated.

    Args:
        memory_id: The ID of the memory to update (from brain_recall results).
        content: New text content (triggers re-embedding if changed).
        tags: New tags list (replaces existing tags).
        metadata: Extra data (JSON string or dict).
    """
    meta = json.loads(metadata) if isinstance(metadata, str) else metadata
    result = _update(get_conn(), memory_id, content, tags, meta)
    return json.dumps(result, indent=2)


# ── brain_tools ─────────────────────────────────────────────────────────────

@mcp.tool()
def brain_tools(query: str, k: int = 3, project: str | None = None) -> str:
    """Semantic Toolbox: find the right tool or skill for a task.

    Searches the registered tool/skill registry by meaning, not just name.
    Returns relevant tools with their MCP server, schemas, and usage info.
    Use when unsure which tool/skill to use for a given task.

    Args:
        query: Natural language description of what you want to accomplish.
        k: Number of tools to return (default 3).
        project: Filter to global + project-specific tools. Omit to search all.
    """
    results = _tools(get_conn(), query, k, project)
    if not results:
        return "No matching tools found. Try a different description."
    return json.dumps(results, indent=2, ensure_ascii=False)


# ── brain_session ───────────────────────────────────────────────────────────

@mcp.tool()
def brain_session(
    action: str,
    project: str | None = None,
    session_id: str | None = None,
    summary: str | None = None,
    decisions: list[str] | None = None,
    discoveries: list[str] | None = None,
    entities: list[str] | None = None,
) -> str:
    """Manage session lifecycle: start, save learnings, check status, or consolidate.

    Actions:
      - "start": Begin a new session. Returns recent context (last sessions, active entities, decisions).
      - "save": End session and persist learnings. Requires summary. session_id is optional (auto-creates if missing).
      - "status": Return memory health stats (counts by type, recent activity).
      - "consolidate": Run auto-consolidation (merge duplicates, decay stale patterns, compress old sessions).

    Args:
        action: One of "start", "save", "status", "consolidate".
        project: Project name for scoping context.
        session_id: Optional for "save" — the session ID from "start". Auto-creates if missing.
        summary: Required for "save" — brief summary of what happened this session.
        decisions: Optional list of decisions made (auto-saved as decision memories).
        discoveries: Optional list of things learned (auto-saved as discovery memories).
        entities: Optional list of entities encountered (auto-saved as entity memories).
    """
    conn = get_conn()

    if action == "start":
        result = _session_start(conn, project)
    elif action == "save":
        if not summary:
            return json.dumps({"error": "summary is required for 'save'"})
        result = _session_save(conn, session_id, summary, decisions, discoveries, entities)
    elif action == "status":
        result = _session_status(conn)
    elif action == "consolidate":
        from .consolidate import consolidate_all
        result = consolidate_all(conn)
    else:
        return json.dumps({"error": f"Unknown action: {action}. Use 'start', 'save', 'status', or 'consolidate'."})

    return json.dumps(result, indent=2, ensure_ascii=False)


# ── brain_graph ─────────────────────────────────────────────────────────────

@mcp.tool()
def brain_graph(entity: str, depth: int = 2) -> str:
    """Traverse the knowledge graph from a memory.

    Finds related memories through typed relationships (causes, fixes, relates_to, etc.).
    Start from a memory ID or search term.

    Args:
        entity: Memory ID to start from, or a search term to find the starting node.
        depth: How many relationship hops to traverse (default 2).
    """
    result = _graph(get_conn(), entity, depth)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ── brain_radar ─────────────────────────────────────────────────────────────

@mcp.tool()
def brain_radar(project: str | None = None, scope: str | None = None) -> str:
    """Scan projects for status, hot files, brain topics, and file reference graph.

    Use BEFORE blind glob/grep/read to orient.

    Args:
        project: Focus on a single project (e.g., "Wildtide"). Scans only that directory.
        scope: Override — "all" (every project) or "ecosystem" (4 core projects).
               If neither project nor scope given, scans all projects.
    """
    result = _radar(get_conn(), project=project, scope=scope)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ── brain_outline ────────────────────────────────────────────────────────────

@mcp.tool()
def brain_outline(filepath: str) -> str:
    """Extract file structure — headings, functions, classes, keys with line numbers.

    Use before reading large files (>100 lines). Returns structure with line numbers
    so you can Read with precise offset+limit instead of reading the entire file.

    Supports: .md (headings), .py (def/class), .gd (GDScript), .yml/.yaml (top keys),
    .json (structure), .sh/.bash (functions). Unknown types return first 8 lines.

    Args:
        filepath: Absolute path (or ~-expanded) to the file to outline.

    Returns JSON with:
      - file: absolute path
      - total_lines: int
      - type: file extension without dot
      - outline: list of {line, text} or type-specific entries
    """
    result = _outline(filepath)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ── brain_index ─────────────────────────────────────────────────────────────

@mcp.tool()
def brain_index(days: int = 60) -> str:
    """Get a topic breakdown of what's in brain memory.

    Use before brain_recall to understand available topics and recent activity.
    Gives you a snapshot of tags, memory types, stale entries, and recent activity.

    Args:
        days: Number of days to include in topic breakdown (default 60).

    Returns JSON with:
      - total_memories: total count across all time
      - topics: {tag_name: {"total": N, "by_type": {...}}, ...} sorted by total desc
      - stale: [{"tag": str, "count": int}, ...] entries 30+ days old with 0 access
      - recent_tags: [str, ...] distinct tags from last 7 days, up to 8
    """
    result = _index(get_conn(), days)
    return json.dumps(result, indent=2, ensure_ascii=False)


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
