#!/usr/bin/env python3
"""PreCompact: Snapshot conversation state to brain.db before compaction.

Reads transcript_path JSONL, extracts last N user+assistant messages,
and writes a structured snapshot to brain.db as type="session".
Also detects unsaved decisions/discoveries and outputs specific warnings.
No LLM needed — pattern matching + truncation.
"""

import json
import re
import sqlite3
import sys
import uuid
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"
MAX_MESSAGES = 20
MAX_CONTENT_PER_MSG = 300
MAX_SNAPSHOT_CHARS = 2000
CONTEXT_WINDOW_DISPLAY = 80
CONTEXT_WINDOW_MATCH = 400

# Signal patterns for detecting decisions/discoveries in assistant messages
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


def detect_signals(chunks: list[tuple[int, str]]) -> list[dict]:
    """Detect decision/discovery signals in assistant text chunks. Returns candidates."""
    candidates = []
    seen_lines = []  # track (line_num) for proximity dedup across chunks

    for line_num, text in chunks:
        for pattern, signal_type in [(DECISION_SIGNALS, "decision"), (DISCOVERY_SIGNALS, "discovery")]:
            for match in pattern.finditer(text):
                # Skip if too close to an already-detected signal (same line or within 300 chars in same chunk)
                if any(ln == line_num for ln in seen_lines):
                    continue

                # Display context (short, for output)
                d_start = max(0, match.start() - CONTEXT_WINDOW_DISPLAY // 2)
                d_end = min(len(text), match.end() + CONTEXT_WINDOW_DISPLAY // 2)
                display = text[d_start:d_end].strip().replace("\n", " ")

                # Match context (wide, for fuzzy comparison with saves)
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


def build_snapshot(messages: list[dict]) -> str:
    """Build a compact snapshot from extracted messages."""
    if not messages:
        return ""

    lines = []
    for msg in messages:
        role = msg["role"].upper()
        content = msg["content"].strip().replace("\n", " ")
        lines.append(f"[{role}] {content}")

    snapshot = "\n".join(lines)

    # Truncate to max chars
    if len(snapshot) > MAX_SNAPSHOT_CHARS:
        snapshot = snapshot[:MAX_SNAPSHOT_CHARS] + "\n[...truncated]"

    return snapshot


def save_to_brain(snapshot: str, project: str | None = None) -> bool:
    """Write snapshot directly to brain.db (no MCP needed)."""
    if not DB_PATH.exists():
        return False

    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row

        memory_id = uuid.uuid4().hex[:12]
        tags = json.dumps(["pre-compact", "auto-snapshot"])
        meta = json.dumps({"source": "pre-compact-hook"})

        conn.execute(
            """INSERT INTO memories (id, content, type, tags, project, metadata)
               VALUES (?, ?, 'session', ?, ?, ?)""",
            (memory_id, snapshot, tags, project, meta),
        )

        # Insert into FTS (no embedding — too expensive for hook, FTS is sufficient)
        conn.execute(
            "INSERT INTO memory_fts (memory_id, content, tags, project) VALUES (?, ?, ?, ?)",
            (memory_id, snapshot, tags, project or ""),
        )

        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def format_unsaved(unsaved: list[dict], max_items: int = 3) -> str:
    """Format unsaved items into a concise warning message."""
    items = unsaved[:max_items]
    parts = []
    for item in items:
        ctx = item["context"]
        # Trim to ~60 chars for readability
        if len(ctx) > 60:
            ctx = ctx[:57] + "..."
        parts.append(f"  - [{item['type']}] {ctx}")

    msg = "Potentially unsaved:\n" + "\n".join(parts)
    if len(unsaved) > max_items:
        msg += f"\n  ...and {len(unsaved) - max_items} more"
    msg += "\nConsider brain_save for items worth keeping."
    return msg


FALLBACK_MSG = "Context approaching limit. Use brain_save for any unsaved decisions/discoveries before compaction."


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

    # Step 2: Save snapshot (existing behavior)
    snapshot = build_snapshot(messages)
    cwd = Path.cwd()
    project = cwd.name if cwd.parent == Path.home() / "Projects" else None
    saved = save_to_brain(snapshot, project) if snapshot else False

    # Step 3: Detect unsaved decisions/discoveries
    candidates = detect_signals(assistant_chunks)
    unsaved = find_unsaved(candidates, brain_saves)

    # Step 4: Output specific message
    if saved:
        msg = f"Pre-compact snapshot saved to brain ({len(messages)} messages captured)."
        if unsaved:
            msg += "\n" + format_unsaved(unsaved)
        else:
            msg += " Use brain_save for any additional context worth preserving."
        print(msg)
    else:
        print(FALLBACK_MSG)
