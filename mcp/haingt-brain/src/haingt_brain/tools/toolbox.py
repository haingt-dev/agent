"""brain_tools: Semantic Toolbox — find the right tool/skill for a task."""

import json
import re
import sqlite3
from pathlib import Path

from ..search import hybrid_search

# Skill discovery paths (same as index_tools.py)
_GLOBAL_SKILLS_DIR = Path.home() / ".claude" / "skills"
_PROJECTS_DIR = Path.home() / "Projects"
_PLUGINS_DIR = Path.home() / "Projects" / "agent" / "plugins"
_SKIP_DIRS = {"skill-snapshot", "workspace"}


def brain_tools(
    conn: sqlite3.Connection,
    query: str,
    k: int = 3,
    project: str | None = None,
) -> list[dict]:
    """
    Search the tool/skill registry for capabilities matching a task description.

    Returns the most relevant tools with their schemas and usage info.

    Args:
        query: Natural language description of what you want to accomplish.
        k: Number of tools to return (default 3).
        project: Filter to global + project-specific tools. Omit for all.

    Returns:
        List of matching tools with name, description, MCP server, and schema.
    """
    results = hybrid_search(conn, query, memory_type="tool", project=project, k=k)

    formatted = []
    for r in results:
        meta = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else (r["metadata"] or {})
        tags = json.loads(r["tags"]) if isinstance(r["tags"], str) else (r["tags"] or [])

        entry = {
            "content": r["content"],
            "tags": tags,
        }

        # Add protocol and project
        if meta.get("protocol"):
            entry["protocol"] = meta["protocol"]
        if r.get("project"):
            entry["project"] = r["project"]

        # Add tool-specific metadata
        if meta.get("server"):
            entry["server"] = meta["server"]
        if meta.get("name"):
            entry["name"] = meta["name"]
        if meta.get("command"):
            entry["command"] = meta["command"]
        if meta.get("category"):
            entry["category"] = meta["category"]

        formatted.append(entry)

    return formatted


def _discover_skill_names() -> set[tuple[str, str | None]]:
    """Lightweight filesystem scan — returns {(name, project)} tuples only."""
    names = set()
    name_re = re.compile(r'^name:\s*(.+)$', re.MULTILINE)

    def _scan_dir(skills_dir: Path, project: str | None):
        if not skills_dir.exists():
            return
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir() or any(s in skill_dir.name for s in _SKIP_DIRS):
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            try:
                # Read only first 500 bytes — just need the name field
                text = skill_file.read_text(encoding="utf-8")[:500]
                match = name_re.search(text)
                if match:
                    names.add((match.group(1).strip().strip('"\''), project))
            except (OSError, UnicodeDecodeError):
                continue

    _scan_dir(_GLOBAL_SKILLS_DIR, None)
    if _PROJECTS_DIR.exists():
        for project_dir in _PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                _scan_dir(project_dir / ".claude" / "skills", project_dir.name)
    if _PLUGINS_DIR.exists():
        for plugin_dir in _PLUGINS_DIR.iterdir():
            if plugin_dir.is_dir():
                _scan_dir(plugin_dir / "skills", f"plugin:{plugin_dir.name}")

    return names


def validate_tool_index(conn: sqlite3.Connection) -> dict | None:
    """Compare indexed skills vs filesystem. Returns drift report or None if synced."""
    rows = conn.execute(
        "SELECT json_extract(metadata, '$.name') as name, project FROM memories "
        "WHERE type='tool' AND json_extract(metadata, '$.protocol')='skill'"
    ).fetchall()
    indexed = {(row["name"], row["project"]) for row in rows if row["name"]}
    discovered = _discover_skill_names()

    missing = {f"{n} [{p or 'global'}]" for n, p in (discovered - indexed)}
    stale = {f"{n} [{p or 'global'}]" for n, p in (indexed - discovered)}

    if missing or stale:
        return {
            "missing": sorted(missing),
            "stale": sorted(stale),
            "indexed_count": len(indexed),
            "filesystem_count": len(discovered),
        }
    return None
