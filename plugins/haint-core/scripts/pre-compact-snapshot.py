#!/usr/bin/env python3
"""PreCompact: Structured snapshot of conversation state before compaction.

Reads transcript_path JSONL, extracts 9 structured sections aligned with
Claude Code's compact prompt format. Writes structured snapshot to brain.db
as type="session". No LLM needed — pattern matching only (0 tokens).

Sections (CC-aligned compact format):
1. Primary Request and Intent   — main goal from early user messages
2. Key Technical Concepts       — patterns, architecture, concepts discussed
3. Files and Code Sections      — file paths touched via tool_use blocks
4. Errors and Fixes             — error messages, stack traces, fixes applied
5. Problem Solving              — decisions, discoveries, root cause analysis
6. All User Messages            — non-tool-use user messages (conversation tail)
7. Pending Tasks                — TODOs, commitments, next steps
8. Current Work                 — what was actively being done (last assistant msgs)
9. Optional Next Step           — last action signal or explicit "next step"
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

# ── Error signal patterns ─────────────────────────────────────────────────

ERROR_SIGNALS = re.compile(
    r"error|Error|ERROR|traceback|Traceback|exception|Exception|"
    r"failed|FAILED|✗|❌|exit code [1-9]|non-zero",
    re.IGNORECASE,
)

FIX_SIGNALS = re.compile(
    r"(?:fixed (?:by|in|with|the)|the fix is|resolved (?:by|with)|solution[: ])"
    r"|(?:patch(?:ed)?|workaround|corrected|adjusted)",
    re.IGNORECASE,
)

ERROR_PATTERNS = [
    (ERROR_SIGNALS, "error"),
    (FIX_SIGNALS, "fix"),
]

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

NEXT_STEP_SIGNALS = re.compile(
    r"(?:next (?:step|up|thing|task)[: ]|after this[,: ]|once (?:this|that) (?:is |'?s )?done)"
    r"|(?:then (?:we(?:'ll| will| can)?|i(?:'ll| will| can)?) (?:move|proceed|continue|work))"
    r"|(?:the (?:last|final|next) (?:thing|step|task))",
    re.IGNORECASE,
)

# ── File tool patterns ────────────────────────────────────────────────────

FILE_TOOL_PATTERN = re.compile(r'"(?:file_path|path)":\s*"([^"]+)"')
FILE_TOOLS = {"Read", "Edit", "Write", "Glob", "mcp__bash__bash"}

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


def parse_transcript(
    transcript_path: str,
) -> tuple[list[dict], list[dict], list[tuple[int, str]], list[str], list[tuple[int, str]]]:
    """Single-pass transcript parse.

    Returns:
        messages         — all non-system messages (role, content)
        brain_saves      — detected brain_save tool_use calls
        assistant_chunks — (line_num, text) from assistant text blocks
        file_paths       — unique file paths from tool_use inputs
        user_chunks      — (line_num, text) from user text blocks (non-tool)
    """
    messages = []
    saves = []
    chunks = []
    file_paths_seen: list[str] = []
    file_paths_set: set[str] = set()
    user_chunks: list[tuple[int, str]] = []

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
                        item_type = item.get("type")

                        if item_type == "text":
                            text = item.get("text", "")
                            text_parts.append(text)
                            if msg_type == "assistant":
                                chunks.append((line_num, text))
                            elif msg_type == "user":
                                user_chunks.append((line_num, text))

                        elif msg_type == "assistant" and item_type == "tool_use":
                            tool_name = item.get("name", "")
                            inp = item.get("input", {})

                            # brain_save tracking
                            if tool_name == "mcp__haingt-brain__brain_save":
                                saves.append({
                                    "content": inp.get("content", "")[:500],
                                    "type": inp.get("type", "unknown"),
                                    "line": line_num,
                                })

                            # File path extraction from tool inputs
                            inp_str = json.dumps(inp)
                            for m in FILE_TOOL_PATTERN.finditer(inp_str):
                                fp = m.group(1)
                                if fp and fp not in file_paths_set:
                                    file_paths_set.add(fp)
                                    file_paths_seen.append(fp)

                        elif msg_type == "user" and item_type == "tool_result":
                            # tool_result content can contain file paths too
                            result_content = item.get("content", "")
                            if isinstance(result_content, list):
                                for rc in result_content:
                                    if isinstance(rc, dict) and rc.get("type") == "text":
                                        for m in FILE_TOOL_PATTERN.finditer(rc.get("text", "")):
                                            fp = m.group(1)
                                            if fp and fp not in file_paths_set:
                                                file_paths_set.add(fp)
                                                file_paths_seen.append(fp)

                    content = "\n".join(text_parts)
                elif isinstance(content, str):
                    if msg_type == "assistant":
                        chunks.append((line_num, content))
                    elif msg_type == "user":
                        user_chunks.append((line_num, content))
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

    return messages[-MAX_MESSAGES:], saves, chunks, file_paths_seen, user_chunks


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
    """Extract technical signals: decisions, discoveries, architecture choices."""
    return _extract_signals(chunks, TECHNICAL_PATTERNS)


def extract_errors(chunks: list[tuple[int, str]]) -> list[dict]:
    """Extract error and fix signals: error messages, stack traces, fixes applied."""
    return _extract_signals(chunks, ERROR_PATTERNS)


def extract_actions(chunks: list[tuple[int, str]]) -> list[dict]:
    """Extract action signals: TODOs, commitments, next steps, waiting."""
    return _extract_signals(chunks, [(ACTION_SIGNALS, "action")])


def extract_next_step(chunks: list[tuple[int, str]]) -> str | None:
    """Extract the last explicit next-step signal from assistant chunks."""
    signals = _extract_signals(chunks, [(NEXT_STEP_SIGNALS, "next")])
    if not signals:
        return None
    last = signals[-1]
    ctx = last["context"]
    if len(ctx) > TAIL_CHAR_LIMIT:
        ctx = ctx[:TAIL_CHAR_LIMIT - 3] + "..."
    return ctx


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


def extract_primary_intent(user_chunks: list[tuple[int, str]]) -> str | None:
    """Extract the primary request from the first few user messages."""
    early = user_chunks[:3]
    for _, text in early:
        clean = text.strip().replace("\n", " ")
        if len(clean) > 10:
            if len(clean) > TAIL_CHAR_LIMIT:
                clean = clean[:TAIL_CHAR_LIMIT - 3] + "..."
            return clean
    return None


def extract_current_work(assistant_chunks: list[tuple[int, str]]) -> list[str]:
    """Extract what was actively being done from the last 2-3 assistant messages."""
    recent = assistant_chunks[-3:] if len(assistant_chunks) >= 3 else assistant_chunks
    lines = []
    for _, text in recent:
        clean = text.strip().replace("\n", " ")
        if len(clean) > 20:
            if len(clean) > TAIL_CHAR_LIMIT:
                clean = clean[:TAIL_CHAR_LIMIT - 3] + "..."
            lines.append(clean)
    return lines


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


def _truncate(text: str, limit: int = TAIL_CHAR_LIMIT) -> str:
    """Truncate text to limit with ellipsis."""
    if len(text) > limit:
        return text[:limit - 3] + "..."
    return text


def build_structured_snapshot(
    technical: list[dict],
    errors: list[dict],
    entities: dict,
    actions: list[dict],
    messages: list[dict],
    file_paths: list[str],
    user_chunks: list[tuple[int, str]],
    assistant_chunks: list[tuple[int, str]],
    project: str | None,
) -> str:
    """Build structured snapshot with 9 CC-aligned sections."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    proj_label = project or "unknown"
    parts = [f"## Session Snapshot — {proj_label} — {now}"]

    # Section 1: Primary Request and Intent
    intent = extract_primary_intent(user_chunks)
    if intent:
        parts.append(f"### 1. Primary Request and Intent\n- {intent}")

    # Section 2: Key Technical Concepts (decisions + discoveries — no errors)
    concept_sigs = [s for s in technical if s["type"] in ("decision", "discovery")]
    if concept_sigs:
        lines = [f"- [{s['type']}] {_truncate(s['context'])}" for s in concept_sigs[:5]]
        parts.append("### 2. Key Technical Concepts\n" + "\n".join(lines))

    # Section 3: Files and Code Sections
    if file_paths:
        # Deduplicate while preserving order, show most recent (tail) first
        seen: set[str] = set()
        unique_paths: list[str] = []
        for fp in reversed(file_paths):
            if fp not in seen:
                seen.add(fp)
                unique_paths.append(fp)
        unique_paths = unique_paths[:8]
        lines = [f"- {fp}" for fp in unique_paths]
        parts.append("### 3. Files and Code Sections\n" + "\n".join(lines))

    # Section 4: Errors and Fixes
    if errors:
        lines = [f"- [{s['type']}] {_truncate(s['context'])}" for s in errors[:5]]
        parts.append("### 4. Errors and Fixes\n" + "\n".join(lines))

    # Section 5: Problem Solving (technical remainder — not decisions/discoveries)
    ps_sigs = [s for s in technical if s["type"] == "technical"]
    if ps_sigs:
        lines = [f"- [{s['type']}] {_truncate(s['context'])}" for s in ps_sigs[:5]]
        parts.append("### 5. Problem Solving\n" + "\n".join(lines))

    # Section 6: All User Messages (conversation tail — user side only)
    if messages:
        user_msgs = [m for m in messages if m["role"] == "user"]
        tail = user_msgs[-TAIL_MESSAGES:]
        if tail:
            lines = []
            for msg in tail:
                content = msg["content"].strip().replace("\n", " ")
                lines.append(f"- {_truncate(content)}")
            parts.append(f"### 6. All User Messages (last {len(tail)})\n" + "\n".join(lines))

    # Section 7: Pending Tasks
    if actions:
        lines = [f"- {_truncate(s['context'])}" for s in actions[:5]]
        # Add entity context if useful
        entity_hints = []
        if entities.get("projects"):
            entity_hints.append(f"projects: {', '.join(entities['projects'])}")
        if entities.get("skills"):
            entity_hints.append(f"skills: {', '.join('/' + s for s in entities['skills'])}")
        if entity_hints:
            lines.append(f"  (context: {'; '.join(entity_hints)})")
        parts.append("### 7. Pending Tasks\n" + "\n".join(lines))
    elif entities.get("projects") or entities.get("skills"):
        # No actions but has context — include entities here
        entity_lines = []
        if entities.get("projects"):
            entity_lines.append(f"- Projects: {', '.join(entities['projects'])}")
        if entities.get("skills"):
            entity_lines.append(f"- Skills: {', '.join('/' + s for s in entities['skills'])}")
        if entities.get("technologies"):
            entity_lines.append(f"- Tech: {', '.join(entities['technologies'])}")
        parts.append("### 7. Pending Tasks\n" + "\n".join(entity_lines))

    # Section 8: Current Work
    current = extract_current_work(assistant_chunks)
    if current:
        lines = [f"- {c}" for c in current]
        parts.append("### 8. Current Work\n" + "\n".join(lines))

    # Section 9: Optional Next Step
    next_step = extract_next_step(assistant_chunks)
    if not next_step and actions:
        # Fall back to last action signal
        last_action = actions[-1]
        next_step = _truncate(last_action["context"])
    if next_step:
        parts.append(f"### 9. Optional Next Step\n- {next_step}")

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
        source = "pre-compact-hook"
        meta = json.dumps({
            "source": source,
            "format": "structured-v2",
            "counts": counts,
        })

        # Compute importance from type × source
        importance = 0.3  # default for session type
        try:
            brain_src = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / "src"
            sys.path.insert(0, str(brain_src))
            from haingt_brain.importance import compute_initial_importance
            importance = compute_initial_importance("session", source)
        except Exception:
            pass

        conn.execute(
            """INSERT INTO memories (id, content, type, tags, project, metadata, importance)
               VALUES (?, ?, 'session', ?, ?, ?, ?)""",
            (memory_id, snapshot, tags, project, meta, importance),
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
    """Format output message with section counts and unsaved warnings."""
    parts = []
    for key in ("technical", "errors", "files", "actions"):
        n = counts.get(key, 0)
        if n > 0:
            parts.append(f"{n} {key}")

    summary = ", ".join(parts) if parts else "no signals"
    msg = f"Pre-compact snapshot saved to brain ({message_count} messages captured, 9-section format). Extracted: {summary}."

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

    # Step 1: Single-pass transcript parse (extended return values)
    messages, brain_saves, assistant_chunks, file_paths, user_chunks = parse_transcript(transcript_path)
    if not messages:
        print(FALLBACK_MSG)
        sys.exit(0)

    # Step 2: Extract all signal categories
    technical = extract_technical(assistant_chunks)
    errors = extract_errors(assistant_chunks)
    entities = extract_entities_for_snapshot(assistant_chunks)
    actions = extract_actions(assistant_chunks)

    # Step 3: Coverage filter (only on technical — errors/actions always captured)
    unsaved_technical = find_unsaved(technical, brain_saves)

    # Step 4: Build structured snapshot
    project = _detect_project(transcript_path)

    entity_count = sum(len(v) for v in entities.values())
    counts = {
        "technical": len(unsaved_technical),
        "errors": len(errors),
        "files": len(file_paths),
        "entities": entity_count,
        "actions": len(actions),
        "messages": len(messages),
    }

    snapshot = build_structured_snapshot(
        technical=unsaved_technical,
        errors=errors,
        entities=entities,
        actions=actions,
        messages=messages,
        file_paths=file_paths,
        user_chunks=user_chunks,
        assistant_chunks=assistant_chunks,
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
