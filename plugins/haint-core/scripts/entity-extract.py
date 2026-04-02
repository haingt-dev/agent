#!/usr/bin/env python3
"""Stop hook: Auto-extract entities from assistant responses.

High-precision regex extraction → LLM distillation → dedup via FTS5 → save/bump in brain.db.
Fire-and-forget (output ignored by Stop hook).

Entity categories:
- Projects: ecosystem project references
- Skills: /slash commands invoked
- Technologies: curated tech terms mentioned
"""

import json
import os
import re
import sqlite3
import sys
import uuid
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"
BRAIN_SRC = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / "src"
BRAIN_ENV = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / ".env"

MIN_RESPONSE_LENGTH = 200

# ── API key ────────────────────────────────────────────────────────────────

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


# ── LLM distillation ───────────────────────────────────────────────────────

def _distill_findings(findings: list[dict], api_key: str) -> list[dict]:
    """Refine regex-extracted findings via LLM distillation."""
    if not findings or not api_key:
        return findings  # Graceful fallback

    # Take top 5 findings
    top = findings[:5]
    raw_text = "\n".join(f"- [{f['type']}] {f['content']}" for f in top)

    prompt = f"""Extract atomic facts from these session findings. For each, output one line:
FACT: category | confidence 0-10 | concise self-contained fact

Categories: decision, discovery, pattern, entity, preference
Rules:
- Each fact must be self-contained (no pronouns, no "the above")
- Include specific names, versions, dates
- Skip generic observations
- If a finding is already atomic and clear, keep it as-is
- Output NOTHING if no facts worth remembering

Findings:
{raw_text}"""

    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps({
                "model": "gpt-4.1-nano",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.0,
            }).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            text = result["choices"][0]["message"]["content"].strip()

        # Parse FACT: lines
        distilled = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("FACT:"):
                parts = line[5:].split("|", 2)
                if len(parts) == 3:
                    category = parts[0].strip()
                    confidence = float(parts[1].strip()) / 10.0
                    content = parts[2].strip()
                    if content:
                        distilled.append({
                            "type": category,
                            "content": content,
                            "confidence": confidence,
                        })
        return distilled if distilled else findings  # Fallback to originals
    except Exception:
        return findings  # Any failure → use regex results as-is


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
    source = "entity-extract-hook"
    meta = json.dumps({"source": source, "category": category, "name": name})

    # Compute importance from type × source
    importance = 0.5
    try:
        sys.path.insert(0, str(BRAIN_SRC))
        from haingt_brain.importance import compute_initial_importance
        importance = compute_initial_importance("entity", source)
    except Exception:
        pass

    conn.execute(
        """INSERT INTO memories (id, content, type, tags, project, metadata, importance)
           VALUES (?, ?, 'entity', ?, ?, ?, ?)""",
        (memory_id, content, tags, project, meta, importance),
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

    # LLM distillation: refine top 5 regex findings into higher-quality atomic facts
    api_key = get_api_key()
    findings = [{"type": e["category"], "content": f"{e['name']} — {e['description']}"} for e in entities]
    distilled = _distill_findings(findings, api_key)

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

        # Use distilled facts as the save candidates (fall back to regex entities if distillation failed)
        if distilled is not findings:
            # Distillation succeeded: save distilled facts, bump existing entities from regex set
            for entity in entities:
                existing = find_existing_entity(conn, entity["name"], entity["category"])
                if existing:
                    bump_access(conn, existing["id"])
                    bump_count += 1
            for fact in distilled:
                name = fact["content"][:80]  # Use content as name for distilled facts
                category = fact["type"]
                description = fact["content"]
                existing = find_existing_entity(conn, name, category)
                if existing:
                    bump_access(conn, existing["id"])
                    bump_count += 1
                else:
                    save_entity(conn, name, category, description, project)
                    new_count += 1
        else:
            # Fallback: distillation failed or was skipped, use original regex entities
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
