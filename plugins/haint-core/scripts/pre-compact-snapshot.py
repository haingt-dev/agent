#!/usr/bin/env python3
"""PreCompact: Structured snapshot of conversation state before compaction.

Reads transcript_path JSONL, extracts 4 structured categories
(Technical, Emotional, Entities, Actions) via regex, plus a conversation tail.
Writes structured snapshot to brain.db as type="session".
No LLM needed — pattern matching only (0 tokens).

Categories (from Building Memory-Aware Agents course L4):
- Technical: decisions, discoveries, bug fixes, architecture choices
- Emotional: frustration, uncertainty, breakthrough, blockers
- Entities: ecosystem projects, skills, technologies mentioned
- Actions: TODOs, commitments, next steps, blockers
"""

import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"
MAX_MESSAGES = 20
MAX_CONTENT_PER_MSG = 300
MAX_SNAPSHOT_CHARS = 2500
CONTEXT_WINDOW_DISPLAY = 80
CONTEXT_WINDOW_MATCH = 400
TAIL_MESSAGES = 8
TAIL_CHAR_LIMIT = 60

# ── Technical signal patterns ─────────────────────────────────────────────

DECISION_SIGNALS = re.compile(
    r"(?:verdict|decided|let'?s go with|recommendation|chose to|will use|should not|don'?t (?:consolidate|use|do))"
    r"|(?:\*\*(?:verdict|recommendation|winner)\*\*)",
    re.IGNORECASE,
)
DISCOVERY_SIGNALS = re.compile(
    r"(?:found that|turns out|key finding|TL;DR|learned that|discovery:|evidence shows)"
    r"|(?:##\s*Research:)|(?:###\s*(?:Recommendation|Key Findings))",
    re.IGNORECASE,
)
TECHNICAL_EXTRA = re.compile(
    r"(?:bug (?:fix|found|confirmed|reproduced)|root cause[: ]|the (?:issue|bug|problem) (?:is|was))"
    r"|(?:fixed (?:by|in|with)|the fix is)"
    r"|(?:refactor(?:ed|ing)? (?:to|into|by)|extract(?:ed)? (?:into|to) a? ?(?:function|class|module))"
    r"|(?:architecture[: ]|design (?:decision|pattern|choice)|trade[-\s]?off)"
    r"|(?:chose .+ over|instead of .+ we(?:'re| are| will))",
    re.IGNORECASE,
)

TECHNICAL_PATTERNS = [
    (DECISION_SIGNALS, "decision"),
    (DISCOVERY_SIGNALS, "discovery"),
    (TECHNICAL_EXTRA, "technical"),
]

# ── Emotional signal patterns ─────────────────────────────────────────────

EMOTIONAL_SIGNALS = re.compile(
    # Frustration
    r"(?:this is (?:really |so )?(?:frustrating|annoying|painful|broken))"
    r"|(?:i(?:'m| am) (?:confused|lost|stuck|not sure|unsure|frustrated))"
    r"|(?:(?:why|how) (?:does|is|would) this (?:even )?(?:work|not work|happen))"
    # Uncertainty
    r"|(?:not (?:sure|certain|confident) (?:if|whether|about|why))"
    r"|(?:(?:might|maybe|perhaps) (?:worth|better|easier))"
    # Breakthrough
    r"|(?:this (?:actually )?(?:works?|clicked|makes sense now))"
    r"|(?:(?:ah|oh|wait)[,.]? (?:right|yes|ok|got it|that'?s? (?:it|why|how)))"
    r"|(?:(?:finally|at last)[.!,])"
    # Blocker
    r"|(?:(?:can'?t|cannot|won'?t|doesn'?t) (?:work|run|compile|connect)(?:\s+at all)?)"
    r"|(?:blocked (?:on|by)|blocking issue)",
    re.IGNORECASE,
)

# ── Action signal patterns ────────────────────────────────────────────────

ACTION_SIGNALS = re.compile(
    # TODOs
    r"(?:TODO|FIXME|HACK|XXX)(?:\s*:|\s+\w)"
    r"|(?:- \[ \])"
    # Commitments
    r"|(?:(?:i'?ll|we'?ll|let'?s) (?:add|fix|update|change|refactor|move|remove|create|write|test|deploy|migrate|check))"
    r"|(?:(?:need to|needs to|have to|should) (?:add|fix|update|change|refactor|be (?:done|updated|fixed)))"
    # Next steps
    r"|(?:next (?:step|up|thing)|action (?:item|required|needed))"
    r"|(?:follow[ -]?up(?:\s*:|\s+(?:on|with)))"
    r"|(?:remaining (?:work|tasks?|items?))"
    # Waiting
    r"|(?:waiting (?:on|for) (?:a |the )?(?:response|fix|approval|review|PR|deploy))"
    r"|(?:before (?:we can|i can|this (?:can|will)) (?:proceed|continue|move|work))",
    re.IGNORECASE,
)

# ── Entity patterns (copied from entity-extract.py — keep in sync) ───────

ECOSYSTEM_PROJECTS = {
    "wildtide": "Automation lazy game (Godot)",
    "bookie": "Community, video production pipeline",
    "digital-identity": "Profile center for AI systems",
    "portfolio": "Public-facing presence, haingt.dev",
    "agent": "Claude Code plugin system, haingt-brain MCP",
    "upwork-mcp": "Upwork API integration MCP server",
    "learning_english": "English learning tools",
    "idea_vault": "Knowledge base, journals (Obsidian)",
}

PROJECT_PATH_RE = re.compile(
    r"(?:~/Projects/|/home/haint/Projects/)(\w[\w-]*)", re.IGNORECASE
)

KNOWN_SKILLS = {
    "alfred", "finance", "mentor", "reflect", "inbox", "upwork",
    "learn", "research", "ship", "simplify",
}

TECH_TERMS = {
    "godot", "sqlite-vec", "fastmcp", "astro",
    "cloudflare pages", "openai", "todoist", "readwise",
}

CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`[^`]+`")

# Stopwords for fuzzy matching
STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could of in to for with on at by from as into "
    "that this it its and or but not no nor so yet both either neither each "
    "every all any few more most other some such than too very".split()
)


def get_hook_input() -> dict | None:
    """Read hook input JSON from stdin."""
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return None


def parse_transcript(transcript_path: str) -> tuple[list[dict], list[dict], list[tuple[int, str]]]:
    """Single-pass transcript parse. Returns (messages, brain_saves, assistant_chunks)."""
    messages = []
    saves = []
    chunks = []

    try:
        with open(transcript_path) as f:
            for line_num, line in enumerate(f):
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = obj.get("type")
                if msg_type not in ("user", "assistant"):
                    continue

                message = obj.get("message", {})
                content = message.get("content", "")

                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                            if msg_type == "assistant":
                                chunks.append((line_num, item.get("text", "")))
                        elif (msg_type == "assistant"
                              and item.get("type") == "tool_use"
                              and item.get("name") == "mcp__haingt-brain__brain_save"):
                            inp = item.get("input", {})
                            saves.append({
                                "content": inp.get("content", "")[:500],
                                "type": inp.get("type", "unknown"),
                                "line": line_num,
                            })
                    content = "\n".join(text_parts)
                elif isinstance(content, str):
                    if msg_type == "assistant":
                        chunks.append((line_num, content))
                else:
                    content = str(content)

                # Build snapshot messages
                if not content.strip() or content.startswith("<system-reminder>"):
                    continue
                if "<system-reminder>" in content:
                    content = content[:content.index("<system-reminder>")]

                role = message.get("role", msg_type)
                messages.append({
                    "role": role,
                    "content": content[:MAX_CONTENT_PER_MSG],
                })
    except Exception:
        pass

    return messages[-MAX_MESSAGES:], saves, chunks


def strip_code(text: str) -> str:
    """Remove code blocks and inline code to avoid false positives."""
    text = CODE_BLOCK_RE.sub("", text)
    text = INLINE_CODE_RE.sub("", text)
    return text


def _extract_signals(chunks: list[tuple[int, str]], patterns: list[tuple[re.Pattern, str]]) -> list[dict]:
    """Generic signal extractor. Returns candidates from chunks matching any pattern."""
    candidates = []
    seen_lines = []

    for line_num, text in chunks:
        for pattern, signal_type in patterns:
            for match in pattern.finditer(text):
                if any(ln == line_num for ln in seen_lines):
                    continue

                d_start = max(0, match.start() - CONTEXT_WINDOW_DISPLAY // 2)
                d_end = min(len(text), match.end() + CONTEXT_WINDOW_DISPLAY // 2)
                display = text[d_start:d_end].strip().replace("\n", " ")

                m_start = max(0, match.start() - CONTEXT_WINDOW_MATCH // 2)
                m_end = min(len(text), match.end() + CONTEXT_WINDOW_MATCH // 2)
                match_text = text[m_start:m_end]

                seen_lines.append(line_num)
                candidates.append({
                    "type": signal_type,
                    "context": display,
                    "match_text": match_text,
                    "keyword": match.group(),
                    "line": line_num,
                })

    return candidates


def extract_technical(chunks: list[tuple[int, str]]) -> list[dict]:
    """Extract technical signals: decisions, discoveries, bug fixes, architecture."""
    return _extract_signals(chunks, TECHNICAL_PATTERNS)


def extract_emotional(chunks: list[tuple[int, str]]) -> list[dict]:
    """Extract emotional signals: frustration, uncertainty, breakthrough, blockers."""
    return _extract_signals(chunks, [(EMOTIONAL_SIGNALS, "emotional")])


def extract_actions(chunks: list[tuple[int, str]]) -> list[dict]:
    """Extract action signals: TODOs, commitments, next steps, waiting."""
    return _extract_signals(chunks, [(ACTION_SIGNALS, "action")])


def extract_entities_for_snapshot(chunks: list[tuple[int, str]]) -> dict:
    """Extract entity mentions from chunks. Returns {projects: [], skills: [], technologies: []}."""
    all_text = " ".join(text for _, text in chunks)
    clean = strip_code(all_text)
    clean_lower = clean.lower()

    projects = set()
    skills = set()
    technologies = set()

    # Projects via path pattern (use original text for paths)
    for match in PROJECT_PATH_RE.finditer(all_text):
        name = match.group(1).lower()
        if name in ECOSYSTEM_PROJECTS:
            projects.add(name)

    # Projects via name mention
    for name in ECOSYSTEM_PROJECTS:
        if name.replace("-", " ") in clean_lower or name.replace("_", " ") in clean_lower:
            projects.add(name)

    # Skills
    for match in re.finditer(r"(?<!\w)/(\w+)(?!\w)", clean):
        skill = match.group(1).lower()
        if skill in KNOWN_SKILLS:
            skills.add(skill)

    # Technologies
    for term in TECH_TERMS:
        if term in clean_lower:
            technologies.add(term)

    return {
        "projects": sorted(projects),
        "skills": sorted(skills),
        "technologies": sorted(technologies),
    }


def keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text (lowercased, stopwords removed)."""
    words = set(re.findall(r"[a-zA-Z]{3,}", text.lower()))
    return words - STOPWORDS


PROXIMITY_LINES = 10  # brain_save within N transcript lines = likely covers the signal


def find_unsaved(candidates: list[dict], saves: list[dict]) -> list[dict]:
    """Filter candidates to those not already covered by brain_save calls."""
    if not candidates:
        return []
    if not saves:
        return candidates

    save_keywords = [keywords(s["content"]) for s in saves]
    save_lines = [s.get("line", -999) for s in saves]

    unsaved = []
    for candidate in candidates:
        candidate_line = candidate.get("line", -999)

        # Check 1: Positional proximity — brain_save made within N lines of signal
        if any(abs(candidate_line - sl) <= PROXIMITY_LINES for sl in save_lines):
            continue

        # Check 2: Keyword overlap (for saves not near the signal position)
        candidate_kw = keywords(candidate.get("match_text", candidate["context"]))
        if not candidate_kw:
            continue

        covered = False
        for skw in save_keywords:
            if not skw:
                continue
            shared = len(candidate_kw & skw)
            overlap_from_candidate = shared / len(candidate_kw) if candidate_kw else 0
            overlap_from_save = shared / len(skw) if skw else 0
            if overlap_from_candidate > 0.25 or overlap_from_save > 0.25:
                covered = True
                break

        if not covered:
            unsaved.append(candidate)

    return unsaved


def build_structured_snapshot(
    technical: list[dict],
    emotional: list[dict],
    entities: dict,
    actions: list[dict],
    messages: list[dict],
    project: str | None,
) -> str:
    """Build structured snapshot with 4 categories + conversation tail."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    proj_label = project or "unknown"
    parts = [f"## Session Snapshot — {proj_label} — {now}"]

    # Technical
    if technical:
        lines = []
        for sig in technical[:8]:
            ctx = sig["context"]
            if len(ctx) > TAIL_CHAR_LIMIT:
                ctx = ctx[:TAIL_CHAR_LIMIT - 3] + "..."
            lines.append(f"- [{sig['type']}] {ctx}")
        parts.append("### Technical\n" + "\n".join(lines))

    # Emotional
    if emotional:
        lines = []
        for sig in emotional[:5]:
            ctx = sig["context"]
            if len(ctx) > TAIL_CHAR_LIMIT:
                ctx = ctx[:TAIL_CHAR_LIMIT - 3] + "..."
            lines.append(f"- [{sig['type']}] {ctx}")
        parts.append("### Emotional\n" + "\n".join(lines))

    # Entities
    entity_lines = []
    if entities.get("projects"):
        entity_lines.append(f"- Projects: {', '.join(entities['projects'])}")
    if entities.get("skills"):
        entity_lines.append(f"- Skills: {', '.join('/' + s for s in entities['skills'])}")
    if entities.get("technologies"):
        entity_lines.append(f"- Technologies: {', '.join(entities['technologies'])}")
    if entity_lines:
        parts.append("### Entities\n" + "\n".join(entity_lines))

    # Actions
    if actions:
        lines = []
        for sig in actions[:5]:
            ctx = sig["context"]
            if len(ctx) > TAIL_CHAR_LIMIT:
                ctx = ctx[:TAIL_CHAR_LIMIT - 3] + "..."
            lines.append(f"- [{sig['type']}] {ctx}")
        parts.append("### Actions\n" + "\n".join(lines))

    # Conversation tail
    if messages:
        tail = messages[-TAIL_MESSAGES:]
        lines = []
        for msg in tail:
            role = msg["role"].upper()
            content = msg["content"].strip().replace("\n", " ")
            if len(content) > TAIL_CHAR_LIMIT:
                content = content[:TAIL_CHAR_LIMIT - 3] + "..."
            lines.append(f"[{role}] {content}")
        parts.append(f"### Conversation Tail (last {len(tail)} messages)\n" + "\n".join(lines))

    snapshot = "\n\n".join(parts)
    if len(snapshot) > MAX_SNAPSHOT_CHARS:
        snapshot = snapshot[:MAX_SNAPSHOT_CHARS] + "\n[...truncated]"
    return snapshot


def save_to_brain(snapshot: str, project: str | None, counts: dict) -> bool:
    """Write structured snapshot to brain.db (no MCP needed)."""
    if not DB_PATH.exists():
        return False

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        memory_id = uuid.uuid4().hex[:12]
        tags = json.dumps(["pre-compact", "auto-snapshot", "structured"])
        meta = json.dumps({
            "source": "pre-compact-hook",
            "format": "structured-v1",
            "counts": counts,
        })

        conn.execute(
            """INSERT INTO memories (id, content, type, tags, project, metadata)
               VALUES (?, ?, 'session', ?, ?, ?)""",
            (memory_id, snapshot, tags, project, meta),
        )

        conn.execute(
            "INSERT INTO memory_fts (memory_id, content, tags, project) VALUES (?, ?, ?, ?)",
            (memory_id, snapshot, tags, project or ""),
        )

        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def format_output(counts: dict, unsaved: list[dict], message_count: int) -> str:
    """Format output message with category counts and unsaved warnings."""
    parts = []
    for key in ("technical", "emotional", "entities", "actions"):
        n = counts.get(key, 0)
        if n > 0:
            parts.append(f"{n} {key}")

    summary = ", ".join(parts) if parts else "no signals"
    msg = f"Pre-compact snapshot saved to brain ({message_count} messages captured). Extracted: {summary}."

    if unsaved:
        items = unsaved[:3]
        lines = []
        for item in items:
            ctx = item["context"]
            if len(ctx) > 60:
                ctx = ctx[:57] + "..."
            lines.append(f"  - [{item['type']}] {ctx}")
        msg += "\nPotentially unsaved:\n" + "\n".join(lines)
        if len(unsaved) > 3:
            msg += f"\n  ...and {len(unsaved) - 3} more"
        msg += "\nUse brain_save for any additional context worth preserving."

    return msg


FALLBACK_MSG = "Context approaching limit. Use brain_save for any unsaved decisions/discoveries before compaction."


def _detect_project(transcript_path: str | None) -> str | None:
    """Derive project name from transcript path instead of cwd (hook cwd != session cwd)."""
    if not transcript_path:
        return None
    # Path format: ~/.claude/projects/-home-haint-Projects-{project}/xxx.jsonl
    dir_name = Path(transcript_path).parent.name
    marker = "Projects-"
    idx = dir_name.find(marker)
    if idx >= 0:
        return dir_name[idx + len(marker):]
    return None


def _reset_prompt_cache(transcript_path: str | None) -> None:
    """Reset prompt-context dedup cache for this session.

    Compact wipes all system-reminders from context window, so dedup IDs,
    token caps, and tool state must reset to allow re-injection.

    Cache file is keyed by md5(cwd)[:8]. Reconstruct cwd from project name
    since hook cwd != session cwd.
    """
    import hashlib
    project = _detect_project(transcript_path)
    if not project:
        return
    session_cwd = str(Path.home() / "Projects" / project)
    cwd_hash = hashlib.md5(session_cwd.encode()).hexdigest()[:8]
    cache_file = Path(f"/tmp/brain-prompt-ctx-{cwd_hash}.json")
    cache_file.unlink(missing_ok=True)


if __name__ == "__main__":
    hook_input = get_hook_input()
    transcript_path = hook_input.get("transcript_path") if hook_input else None

    if not transcript_path:
        print(FALLBACK_MSG)
        sys.exit(0)

    # Step 1: Single-pass transcript parse
    messages, brain_saves, assistant_chunks = parse_transcript(transcript_path)
    if not messages:
        print(FALLBACK_MSG)
        sys.exit(0)

    # Step 2: Extract all 4 categories
    technical = extract_technical(assistant_chunks)
    emotional = extract_emotional(assistant_chunks)
    entities = extract_entities_for_snapshot(assistant_chunks)
    actions = extract_actions(assistant_chunks)

    # Step 3: Coverage filter (only on technical — emotional/actions always captured)
    unsaved_technical = find_unsaved(technical, brain_saves)

    # Step 4: Build structured snapshot
    project = _detect_project(transcript_path)

    entity_count = sum(len(v) for v in entities.values())
    counts = {
        "technical": len(unsaved_technical),
        "emotional": len(emotional),
        "entities": entity_count,
        "actions": len(actions),
        "messages": len(messages),
    }

    snapshot = build_structured_snapshot(
        technical=unsaved_technical,
        emotional=emotional,
        entities=entities,
        actions=actions,
        messages=messages,
        project=project,
    )

    # Step 5: Save to brain
    saved = save_to_brain(snapshot, project, counts) if snapshot else False

    # Step 6: Reset prompt-context cache (compact wipes system-reminders)
    _reset_prompt_cache(transcript_path)

    # Step 7: Output
    if saved:
        print(format_output(counts, unsaved_technical, len(messages)))
    else:
        print(FALLBACK_MSG)
