#!/usr/bin/env python3
"""Index all MCP tools, skills, and CLI tools into haingt-brain Semantic Toolbox.

Skills are auto-discovered from filesystem:
  ~/.claude/skills/*/SKILL.md → global (project=None)
  ~/Projects/*/.claude/skills/*/SKILL.md → project-scoped

MCP tools and CLI tools are manually curated (stable, descriptions need curation).

Usage: uv run python scripts/index_tools.py
"""

import json
import re
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from haingt_brain.db import connect, init_schema
from haingt_brain.tools.save import brain_save
from haingt_brain.tools.forget import brain_forget

# ── MCP Tool Definitions ────────────────────────────────────────────────────
# Manually curated. Each entry: (mcp_server, tool_name, description, category)

MCP_TOOLS = [
    # Google Calendar
    ("Google_Calendar", "gcal_create_event", "Create a new event on Google Calendar with title, time, attendees, and description", "calendar"),
    ("Google_Calendar", "gcal_delete_event", "Delete an event from Google Calendar by event ID", "calendar"),
    ("Google_Calendar", "gcal_find_meeting_times", "Find available meeting times for multiple attendees on Google Calendar", "calendar"),
    ("Google_Calendar", "gcal_find_my_free_time", "Find free time slots on your Google Calendar for a given date range", "calendar"),
    ("Google_Calendar", "gcal_get_event", "Get details of a specific Google Calendar event by ID", "calendar"),
    ("Google_Calendar", "gcal_list_calendars", "List all available Google Calendars", "calendar"),
    ("Google_Calendar", "gcal_list_events", "List events from Google Calendar with optional date filtering", "calendar"),
    ("Google_Calendar", "gcal_respond_to_event", "Accept, decline, or tentatively accept a Google Calendar event", "calendar"),
    ("Google_Calendar", "gcal_update_event", "Update an existing Google Calendar event", "calendar"),

    # Gmail
    ("Gmail", "gmail_create_draft", "Create a draft email in Gmail with recipients, subject, and body", "email"),
    ("Gmail", "gmail_get_profile", "Get Gmail profile information (email address, messages count)", "email"),
    ("Gmail", "gmail_list_drafts", "List draft emails in Gmail", "email"),
    ("Gmail", "gmail_list_labels", "List all labels in Gmail", "email"),
    ("Gmail", "gmail_read_message", "Read a specific Gmail message by ID", "email"),
    ("Gmail", "gmail_read_thread", "Read an entire Gmail thread by thread ID", "email"),
    ("Gmail", "gmail_search_messages", "Search Gmail messages using query syntax", "email"),

    # Todoist
    ("todoist", "add-tasks", "Create tasks in Todoist with content, priority (p1-p4), due dates, duration, and project assignment", "tasks"),
    ("todoist", "update-tasks", "Update existing Todoist tasks — priority, description, labels. Do NOT use for rescheduling.", "tasks"),
    ("todoist", "reschedule-tasks", "Reschedule Todoist task due dates. Preserves recurring schedules. Use YYYY-MM-DD format.", "tasks"),
    ("todoist", "complete-tasks", "Mark Todoist tasks as completed", "tasks"),
    ("todoist", "find-tasks", "Search and filter Todoist tasks by project, label, priority, or text", "tasks"),
    ("todoist", "find-tasks-by-date", "Find Todoist tasks due on a specific date or date range", "tasks"),
    ("todoist", "find-projects", "List or search Todoist projects", "tasks"),
    ("todoist", "find-sections", "List sections within a Todoist project", "tasks"),
    ("todoist", "find-labels", "List all Todoist labels", "tasks"),
    ("todoist", "add-projects", "Create a new Todoist project", "tasks"),
    ("todoist", "add-sections", "Create sections within a Todoist project", "tasks"),
    ("todoist", "add-comments", "Add comments to Todoist tasks or projects", "tasks"),
    ("todoist", "find-comments", "List comments on a Todoist task or project", "tasks"),
    ("todoist", "get-overview", "Get overview of Todoist workload and progress", "tasks"),
    ("todoist", "search", "Full-text search across all Todoist tasks and projects", "tasks"),
    ("todoist", "get-productivity-stats", "Get Todoist productivity statistics (karma, streaks)", "tasks"),

    # Readwise
    ("readwise", "readwise_search_highlights", "Search book and article highlights in Readwise by meaning or keywords", "reading"),
    ("readwise", "readwise_list_highlights", "List recent Readwise highlights with filtering", "reading"),
    ("readwise", "reader_search_documents", "Search saved articles and documents in Readwise Reader", "reading"),
    ("readwise", "reader_list_documents", "List documents in Readwise Reader by location (inbox, later, archive)", "reading"),
    ("readwise", "reader_get_document_details", "Get full details of a Readwise Reader document", "reading"),
    ("readwise", "reader_create_document", "Save a new document/URL to Readwise Reader", "reading"),
    ("readwise", "reader_get_document_highlights", "Get highlights from a specific Readwise Reader document", "reading"),
    ("readwise", "readwise_get_daily_review", "Get today's Readwise daily review highlights", "reading"),

    # Context7
    ("Context7", "resolve-library-id", "Resolve a library name to its Context7 ID for documentation lookup", "docs"),
    ("Context7", "query-docs", "Query library documentation via Context7 for up-to-date code examples", "docs"),

    # haingt-brain (self-reference)
    ("haingt-brain", "brain_save", "Save a memory (decision, discovery, pattern, entity, preference) with semantic embedding", "memory"),
    ("haingt-brain", "brain_recall", "Search memories using hybrid semantic + keyword search", "memory"),
    ("haingt-brain", "brain_forget", "Delete a memory by ID. Full CRUD.", "memory"),
    ("haingt-brain", "brain_update", "Update a memory's content, tags, or metadata while preserving ID and access history", "memory"),
    ("haingt-brain", "brain_tools", "Semantic Toolbox — find the right tool/skill for a task by meaning", "memory"),
    ("haingt-brain", "brain_session", "Session lifecycle — start, save learnings, check status", "memory"),
    ("haingt-brain", "brain_graph", "Traverse knowledge graph from a memory entity", "memory"),
]

# ── CLI Tools ──────────────────────────────────────────────────────────────
# Manually curated. Each entry: (command, description, category)

CLI_TOOLS = [
    ("chub search", "Search curated LLM-optimized docs and skills for libraries/frameworks. Usage: chub search [query] --json", "docs"),
    ("chub get", "Fetch curated documentation by ID with language variant. Usage: chub get <id> --lang py|js", "docs"),
    ("chub annotate", "Attach persistent notes to a doc or skill for future sessions. Usage: chub annotate [id] [note]", "docs"),
]


# ── Skill Auto-Discovery ──────────────────────────────────────────────────

GLOBAL_SKILLS_DIR = Path.home() / ".claude" / "skills"
PROJECTS_DIR = Path.home() / "Projects"
PLUGINS_DIR = Path.home() / "Projects" / "agent" / "plugins"

# Skip patterns
SKIP_DIRS = {"skill-snapshot", "workspace"}


def _parse_skill(path: Path) -> dict | None:
    """Parse a SKILL.md file. Returns {name, description, body_context} or None.

    description: from frontmatter (trimmed label, used for display)
    body_context: first ~300 chars of body content (enriches brain index for search)
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # Match YAML frontmatter between ---
    match = re.match(r"^---\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if not match:
        return None

    frontmatter = match.group(1)
    body = match.group(2).strip()
    result = {}

    # Extract name
    name_match = re.search(r'^name:\s*(.+)$', frontmatter, re.MULTILINE)
    if name_match:
        result["name"] = name_match.group(1).strip().strip('"\'')

    # Extract description (single-line or multi-line >- / >)
    desc_match = re.search(r'^description:\s*[>|]-?\s*\n((?:\s+.+\n?)+)', frontmatter, re.MULTILINE)
    if desc_match:
        # Multi-line: join folded lines
        lines = desc_match.group(1).strip().split("\n")
        result["description"] = " ".join(line.strip() for line in lines)
    else:
        # Single-line
        desc_match = re.search(r'^description:\s*(.+)$', frontmatter, re.MULTILINE)
        if desc_match:
            result["description"] = desc_match.group(1).strip().strip('"\'')

    # Extract body context: first ~300 chars after frontmatter for richer search signal
    if body:
        # Strip markdown headers for cleaner text
        body_clean = re.sub(r'^#+\s+', '', body, flags=re.MULTILINE)
        result["body_context"] = body_clean[:300].strip()

    if "name" in result and "description" in result:
        return result
    return None


def _infer_category(description: str) -> str:
    """Infer category from skill description using keyword matching.

    Order matters: more specific categories first, broader ones last.
    """
    desc_lower = description.lower()

    # Most specific first → broadest last
    categories = [
        # Domain-specific (narrow, unambiguous keywords)
        ("game-dev", ["godot", "gdd", "gut test", "gdscript", "gdformat", "gdlint"]),
        ("infra", ["podman", "setup.sh", "prerequisite", "diagnostics", "media stack"]),
        ("finance", ["financial", "budget", "projection", "runway"]),
        ("freelance", ["upwork", "proposal", "gig"]),
        ("triage", ["inbox", "triage"]),
        ("coaching", ["accountability", "milestone", "mentor"]),
        ("self", ["reflect", "profile dimension", "staleness", "satisfaction"]),
        ("learning", ["anki", "flashcard", "vocab", "learning path"]),
        ("scheduling", ["schedule", "quest", "calendar", "optimize day"]),
        ("optimization", ["token", "consumption", "context waste"]),
        # Content creation (before creative — video/storyboard/prompts are content pipeline)
        ("content", ["video", "storyboard", "tts", "book video", "youtube", "facebook",
                      "metadata for", "narrative arc", "pacing", "per-scene", "image prompts"]),
        ("creative", ["generate image", "concept art"]),
        ("research", ["research", "decision intelligence"]),
        # Development (ship, fix, commit, scaffold) — before knowledge to avoid "memory bank" in ship desc
        ("development", ["github issue", "commit", "open pr", "ship change", "fix.*issue",
                         "ship", "lint.*test.*review", "sub-project", "scaffold"]),
        ("knowledge", ["obsidian", "vault note", "catalog insight", "memory bank", "sync.*compact"]),
        # Fallback for setup/config skills
        ("infra", ["setup", "dry-run", "prerequisite"]),
    ]
    for category, keywords in categories:
        if any(re.search(kw, desc_lower) for kw in keywords):
            return category
    return "general"


def discover_skills() -> list[dict]:
    """Auto-discover skills from filesystem.

    Returns: [{"name", "description", "body_context", "category", "project"}, ...]
    Scans:
      ~/.claude/skills/*/SKILL.md → global (project=None)
      ~/Projects/*/.claude/skills/*/SKILL.md → project-scoped
    """
    skills = []

    # Global skills
    if GLOBAL_SKILLS_DIR.exists():
        for skill_dir in sorted(GLOBAL_SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            if any(skip in skill_dir.name for skip in SKIP_DIRS):
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            parsed = _parse_skill(skill_file)
            if parsed:
                desc = parsed["description"]
                body = parsed.get("body_context", "")
                category = _infer_category(desc)
                skills.append({
                    "name": parsed["name"],
                    "description": desc,
                    "body_context": body,
                    "category": category,
                    "project": None,
                })

    # Project skills
    if PROJECTS_DIR.exists():
        for project_dir in sorted(PROJECTS_DIR.iterdir()):
            if not project_dir.is_dir():
                continue
            skills_dir = project_dir / ".claude" / "skills"
            if not skills_dir.exists():
                continue
            project_name = project_dir.name
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                if any(skip in skill_dir.name for skip in SKIP_DIRS):
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                parsed = _parse_skill(skill_file)
                if parsed:
                    desc = parsed["description"]
                    body = parsed.get("body_context", "")
                    category = _infer_category(desc)
                    skills.append({
                        "name": parsed["name"],
                        "description": desc,
                        "body_context": body,
                        "category": category,
                        "project": project_name,
                    })

    # Plugin skills (agent/plugins/*/skills/*)
    if PLUGINS_DIR.exists():
        for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
            if not plugin_dir.is_dir():
                continue
            skills_dir = plugin_dir / "skills"
            if not skills_dir.exists():
                continue
            plugin_name = plugin_dir.name
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                if any(skip in skill_dir.name for skip in SKIP_DIRS):
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                parsed = _parse_skill(skill_file)
                if parsed:
                    desc = parsed["description"]
                    body = parsed.get("body_context", "")
                    category = _infer_category(desc)
                    skills.append({
                        "name": parsed["name"],
                        "description": desc,
                        "body_context": body,
                        "category": category,
                        "project": f"plugin:{plugin_name}",
                    })

    return skills


# ── Drift Validation ──────────────────────────────────────────────────────

def validate_tool_index(conn) -> dict | None:
    """Compare indexed skills vs filesystem. Returns drift report or None if synced."""
    rows = conn.execute(
        "SELECT json_extract(metadata, '$.name') as name, project FROM memories "
        "WHERE type='tool' AND json_extract(metadata, '$.protocol')='skill'"
    ).fetchall()
    indexed = {(row["name"], row["project"]) for row in rows if row["name"]}

    discovered = {(s["name"], s["project"]) for s in discover_skills()}

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


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    conn = connect()
    init_schema(conn)

    # Clear existing tool entries
    existing = conn.execute("SELECT id FROM memories WHERE type = 'tool'").fetchall()
    if existing:
        print(f"Clearing {len(existing)} existing tool entries...")
        for row in existing:
            brain_forget(conn, row["id"])

    # Index MCP tools
    print(f"\nIndexing {len(MCP_TOOLS)} MCP tools...")
    for mcp_server, tool_name, description, category in MCP_TOOLS:
        content = f"{tool_name}: {description}"
        brain_save(
            conn, content, "tool",
            tags=[mcp_server, tool_name, category],
            metadata={
                "protocol": "mcp",
                "server": mcp_server,
                "name": tool_name,
                "category": category,
            },
        )
        print(f"  + {mcp_server}/{tool_name}")

    # Auto-discover and index skills
    skills = discover_skills()
    global_skills = [s for s in skills if s["project"] is None]
    project_skills = [s for s in skills if s["project"] is not None]

    print(f"\nDiscovered {len(skills)} skills ({len(global_skills)} global, {len(project_skills)} project)...")

    for skill in skills:
        name = skill["name"]
        project = skill["project"]
        category = skill["category"]
        scope = f"[{project}]" if project else "[global]"

        # Enriched content: description + body context for better search
        content = f"/{name}: {skill['description']}"
        if skill.get("body_context"):
            content += f" — {skill['body_context']}"

        brain_save(
            conn, content, "tool",
            tags=["skill", name, category],
            project=project,
            metadata={
                "protocol": "skill",
                "name": name,
                "category": category,
            },
        )
        print(f"  + /{name} {scope} ({category})")

    # Index CLI tools
    print(f"\nIndexing {len(CLI_TOOLS)} CLI tools...")
    for command, description, category in CLI_TOOLS:
        content = f"{command}: {description}"
        brain_save(
            conn, content, "tool",
            tags=["cli", command.split()[0], category],
            metadata={
                "protocol": "cli",
                "command": command,
                "name": command,
                "category": category,
            },
        )
        print(f"  + {command}")

    total = len(MCP_TOOLS) + len(skills) + len(CLI_TOOLS)
    print(f"\nDone! Indexed {total} capabilities into Semantic Toolbox.")
    print(f"  MCP tools: {len(MCP_TOOLS)}")
    print(f"  Skills: {len(skills)} ({len(global_skills)} global + {len(project_skills)} project)")
    print(f"  CLI tools: {len(CLI_TOOLS)}")

    # Project breakdown
    projects = {}
    for s in project_skills:
        proj = s["project"]
        projects[proj] = projects.get(proj, 0) + 1
    if projects:
        print(f"\n  Project skills breakdown:")
        for proj, count in sorted(projects.items()):
            print(f"    {proj}: {count}")

    # Quick verification
    from haingt_brain.tools.toolbox import brain_tools
    print("\n=== Verification ===")
    tests = [
        ("find free time on calendar", None),
        ("create a task", None),
        ("write video script", "Bookie"),
        ("create godot scene", "Wildtide"),
        ("check financial health", "digital-identity"),
        ("find docs for fastapi", None),
    ]
    for query, project in tests:
        results = brain_tools(conn, query, k=1, project=project)
        if results:
            r = results[0]
            name = r.get("name", "?")
            proj = r.get("project", "global")
            print(f'  "{query}" (project={project}) → {name} [{proj}]')
        else:
            print(f'  "{query}" (project={project}) → NO MATCH')

    # Drift check
    drift = validate_tool_index(conn)
    if drift:
        print(f"\n⚠ Tool index drift detected: {drift}")
    else:
        print("\n✓ Tool index in sync with filesystem")


if __name__ == "__main__":
    main()
