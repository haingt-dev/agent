#!/usr/bin/env python3
"""Stop hook: Auto-extract entities from assistant responses.

High-precision regex extraction → dedup via FTS5 → save/bump in brain.db.
Zero LLM tokens. Fire-and-forget (output ignored by Stop hook).

Entity categories:
- Projects: ecosystem project references
- Skills: /slash commands invoked
- Technologies: curated tech terms mentioned
"""

import json
import re
import sqlite3
import sys
import uuid
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"
BRAIN_SRC = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / "src"

MIN_RESPONSE_LENGTH = 200

# ── Entity patterns ────────────────────────────────────────────────────────

# Known ecosystem projects (lowercase for matching)
ECOSYSTEM_PROJECTS = {
    "wildtide": "Automation lazy game (Godot), center of gravity for ecosystem",
    "bookie": "Community (9+ years), video production pipeline",
    "digital-identity": "Profile center, source of truth for AI systems",
    "portfolio": "Public-facing presence, haingt.dev (Astro + Cloudflare Pages)",
    "agent": "Claude Code plugin system, haingt-brain MCP server",
    "upwork-mcp": "Upwork API integration MCP server",
    "learning_english": "English learning tools and resources",
    "idea_vault": "Knowledge base, journals, notes (Obsidian)",
}

# Path pattern: ~/Projects/X or /home/haint/Projects/X
PROJECT_PATH_RE = re.compile(
    r"(?:~/Projects/|/home/haint/Projects/)(\w[\w-]*)", re.IGNORECASE
)

# Known skills (match /skillname in text, not in code blocks)
KNOWN_SKILLS = {
    "alfred", "finance", "mentor", "reflect", "inbox", "upwork",
    "learn", "research", "ship", "simplify",
}

# Technology terms (curated, high-signal)
TECH_TERMS = {
    "godot": "Game engine for Wildtide",
    "sqlite-vec": "Vector search extension for SQLite",
    "fastmcp": "Python MCP server framework",
    "astro": "Static site generator for portfolio",
    "cloudflare pages": "Hosting for haingt.dev",
    "openai": "Embedding API provider (text-embedding-3-large)",
    "todoist": "Task management integration",
    "readwise": "Reading highlights integration",
}

# Code block pattern (to strip before extraction)
CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`[^`]+`")


# ── Extraction ─────────────────────────────────────────────────────────────

def strip_code(text: str) -> str:
    """Remove code blocks and inline code to avoid false positives."""
    text = CODE_BLOCK_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def extract_entities(text: str) -> list[dict]:
    """Extract entity candidates from response text. Returns list of {name, category, description}."""
    clean = strip_code(text)
    entities = {}  # name → {category, description} (dedup within response)

    # 1. Projects via path pattern
    for match in PROJECT_PATH_RE.finditer(text):  # Use original text for paths
        name = match.group(1).lower()
        if name in ECOSYSTEM_PROJECTS:
            entities[name] = {
                "category": "project",
                "description": ECOSYSTEM_PROJECTS[name],
            }

    # 2. Projects via name mention (in clean text, not code)
    clean_lower = clean.lower()
    for name, desc in ECOSYSTEM_PROJECTS.items():
        if name.replace("-", " ") in clean_lower or name.replace("_", " ") in clean_lower:
            if name not in entities:
                entities[name] = {"category": "project", "description": desc}

    # 3. Skills invoked (match /skillname pattern in clean text)
    for match in re.finditer(r"(?<!\w)/(\w+)(?!\w)", clean):
        skill = match.group(1).lower()
        if skill in KNOWN_SKILLS:
            entities[f"/{skill}"] = {
                "category": "skill",
                "description": f"Skill invocation: /{skill}",
            }

    # 4. Technologies (in clean text)
    for term, desc in TECH_TERMS.items():
        if term in clean_lower:
            entities[term] = {"category": "technology", "description": desc}

    return [
        {"name": name, "category": e["category"], "description": e["description"]}
        for name, e in entities.items()
    ]


# ── Brain DB operations ────────────────────────────────────────────────────

def find_existing_entity(conn: sqlite3.Connection, name: str, category: str) -> dict | None:
    """Search for existing entity by name+category via FTS5.

    Category check prevents false positives (e.g., "agent" matching "agent-triggered"
    in an unrelated entity).
    """
    try:
        row = conn.execute(
            """SELECT m.id, m.access_count
               FROM memory_fts f
               JOIN memories m ON m.id = f.memory_id
               WHERE memory_fts MATCH ?
                 AND m.type = 'entity'
                 AND json_extract(m.metadata, '$.category') = ?
               LIMIT 1""",
            (f'"{name}"', category),
        ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def bump_access(conn: sqlite3.Connection, memory_id: str) -> None:
    """Increment access_count and update last_accessed."""
    conn.execute(
        "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ?",
        (memory_id,),
    )


def save_entity(conn: sqlite3.Connection, name: str, category: str, description: str, project: str | None) -> str:
    """Save new entity to brain.db with embedding."""
    memory_id = uuid.uuid4().hex[:12]
    content = f"{category.title()}: {name} — {description}"
    tags = json.dumps([category, "auto-extracted"])
    meta = json.dumps({"source": "entity-extract-hook", "category": category, "name": name})

    conn.execute(
        """INSERT INTO memories (id, content, type, tags, project, metadata)
           VALUES (?, ?, 'entity', ?, ?, ?)""",
        (memory_id, content, tags, project, meta),
    )

    # FTS entry
    conn.execute(
        "INSERT INTO memory_fts (memory_id, content, tags, project) VALUES (?, ?, ?, ?)",
        (memory_id, content, tags, project or ""),
    )

    # Try to embed (graceful fallback)
    try:
        sys.path.insert(0, str(BRAIN_SRC))
        from haingt_brain.db import serialize_embedding
        from haingt_brain.embeddings import embed_text

        embedding = embed_text(content)
        emb_bytes = serialize_embedding(embedding)
        conn.execute(
            "INSERT INTO memory_vectors (memory_id, embedding) VALUES (?, ?)",
            (memory_id, emb_bytes),
        )
    except Exception:
        pass  # FTS-only is still useful

    return memory_id


# ── Main ───────────────────────────────────────────────────────────────────

def get_hook_input() -> dict | None:
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return None


if __name__ == "__main__":
    data = get_hook_input()
    if not data:
        sys.exit(0)

    response = data.get("last_assistant_message", "")
    if not response or len(response) < MIN_RESPONSE_LENGTH:
        sys.exit(0)

    entities = extract_entities(response)
    if not entities:
        sys.exit(0)

    # Detect project from cwd, fallback to transcript_path
    project = None
    cwd = Path(data.get("cwd", ""))
    projects_dir = Path.home() / "Projects"
    try:
        project = cwd.relative_to(projects_dir).parts[0]
    except (ValueError, IndexError):
        tp = data.get("transcript_path", "")
        if tp:
            dir_name = Path(tp).parent.name
            marker = "Projects-"
            idx = dir_name.find(marker)
            if idx >= 0:
                project = dir_name[idx + len(marker):]

    if not DB_PATH.exists():
        sys.exit(0)

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

        new_count = 0
        bump_count = 0

        for entity in entities:
            existing = find_existing_entity(conn, entity["name"], entity["category"])
            if existing:
                bump_access(conn, existing["id"])
                bump_count += 1
            else:
                save_entity(conn, entity["name"], entity["category"], entity["description"], project)
                new_count += 1

        conn.commit()
        conn.close()
    except Exception:
        sys.exit(0)
