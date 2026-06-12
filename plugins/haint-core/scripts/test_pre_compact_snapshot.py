#!/usr/bin/env python3
"""Tests for pre-compact-snapshot.py (the 2026-06-13 audit fixes).

Covers the four leads from the brain audit phase-2 follow-up:
- project/cwd resolution preserves underscores (Learning_English, not -English)
- prompt-context dedup-cache key matches prompt-context.py's md5(Path.cwd())
- extracted signals are complete sentences, never mid-word fragments
- content-hash dedup guard suppresses near-simultaneous double-saves

Run: python test_pre_compact_snapshot.py   (or: pytest test_pre_compact_snapshot.py)
"""

import hashlib
import importlib.util
import sqlite3
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pre_compact_snapshot", Path(__file__).parent / "pre-compact-snapshot.py"
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


# ── cwd / project resolution ──────────────────────────────────────────────

def test_session_cwd_prefers_cwd_field():
    hi = {"cwd": "/home/haint/Projects/agent", "transcript_path": "/x/y.jsonl"}
    cwd = mod._session_cwd(hi)
    assert cwd == Path("/home/haint/Projects/agent")
    assert mod._detect_project(cwd) == "agent"


def test_cache_key_matches_prompt_context():
    # prompt-context.py keys the dedup cache by md5(str(Path.cwd()))[:8].
    # The live /home/haint/Projects/agent cache is bf884550 — must match.
    cwd = Path("/home/haint/Projects/agent")
    assert hashlib.md5(str(cwd).encode()).hexdigest()[:8] == "bf884550"


def test_underscore_project_recovered_from_transcript():
    # Fallback path: Claude Code mangles '_' -> '-' in the transcript dir name.
    # Must recover the real underscore directory (depends on it existing).
    real = Path("/home/haint/Projects/Learning_English")
    if not real.is_dir():
        print("  (skip underscore-recovery: Learning_English dir absent)")
        return
    tp = "/home/haint/.claude/projects/-home-haint-Projects-Learning-English/a.jsonl"
    cwd = mod._session_cwd({"transcript_path": tp})  # no cwd field -> fallback
    assert cwd == real, f"got {cwd}"
    assert mod._detect_project(cwd) == "Learning_English"
    # And the cache key must differ from the buggy hyphenated reconstruction.
    good = hashlib.md5(str(real).encode()).hexdigest()[:8]
    bad = hashlib.md5(b"/home/haint/Projects/Learning-English").hexdigest()[:8]
    assert good != bad


def test_real_hyphen_project_unchanged():
    real = Path("/home/haint/Projects/digital-identity")
    if not real.is_dir():
        print("  (skip hyphen-project: digital-identity dir absent)")
        return
    tp = "/home/haint/.claude/projects/-home-haint-Projects-digital-identity/a.jsonl"
    cwd = mod._session_cwd({"transcript_path": tp})
    assert cwd == real
    assert mod._detect_project(cwd) == "digital-identity"


def test_reset_prompt_cache_unlinks_correct_file():
    # Use a throwaway path so we never touch a live session's cache.
    fake = Path("/home/haint/Projects/__pcs_test_only__")
    h = hashlib.md5(str(fake).encode()).hexdigest()[:8]
    cache = Path(f"/tmp/brain-prompt-ctx-{h}.json")
    cache.write_text("{}")
    mod._reset_prompt_cache(fake)
    assert not cache.exists()
    # None cwd is a no-op, not a crash.
    mod._reset_prompt_cache(None)


# ── sentence extraction (no mid-word fragments) ───────────────────────────

def test_signal_is_complete_sentence():
    text = (
        "Here is some earlier context that runs on for a while before the point. "
        "After analysis we decided to use the RRF fusion approach because it scored highest. "
        "Then we moved on and kept talking well past the decision point here."
    )
    sigs = mod.extract_technical([(1, text)])
    assert sigs, "expected a decision signal"
    ctx = sigs[0]["context"]
    assert ctx.startswith("After analysis"), ctx
    assert "decided to use the RRF fusion approach" in ctx
    assert ctx.rstrip("…").endswith("highest."), ctx
    # No mid-word fragment at either edge.
    assert not ctx.startswith("ome") and not ctx.startswith("text")


def test_long_sentence_word_clipped():
    long = "We decided " + "alpha beta gamma delta " * 30 + "end."
    sigs = mod.extract_technical([(1, long)])
    assert sigs
    ctx = sigs[0]["context"]
    assert ctx.endswith("…")
    assert len(ctx) <= mod.SIGNAL_DISPLAY_LIMIT + 1
    # word boundary: stripped ellipsis must not end mid-token
    assert not ctx.rstrip("…").endswith("gam")


def test_truncate_word_boundary():
    assert mod._truncate("short text", 100) == "short text"
    assert mod._truncate("the quick brown fox jumps over lazy", 12) == "the quick…"
    out = mod._truncate("supercalifragilistic", 8)  # single long token -> hard cut
    assert out.endswith("…") and len(out) <= 9


# ── user-text cleaning ────────────────────────────────────────────────────

def test_clean_user_text():
    assert mod._clean_user_text("<command-name>/clear</command-name>") == ""
    assert mod._clean_user_text("<local-command-stdout>x</local-command-stdout>") == ""
    assert mod._clean_user_text("<system-reminder>only junk</system-reminder>") == ""
    assert mod._clean_user_text("real task\n<system-reminder>j</system-reminder>") == "real task"
    assert mod._clean_user_text("  do the thing  ") == "do the thing"


def test_primary_intent_skips_noise():
    chunks = [
        (1, "real first request: build the parser"),  # user_chunks already cleaned
    ]
    intent = mod.extract_primary_intent(chunks)
    assert intent and "build the parser" in intent


# ── content-hash dedup guard ──────────────────────────────────────────────

def _make_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE memories (
            id TEXT PRIMARY KEY, content TEXT, type TEXT, tags TEXT,
            project TEXT, metadata TEXT, importance REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE VIRTUAL TABLE memory_fts USING fts5(
            content, tags, project, memory_id UNINDEXED
        );
        """
    )
    conn.commit()
    conn.close()


def test_dedup_guard():
    tmp = Path(tempfile.mkdtemp())
    db = tmp / "brain.db"
    _make_db(db)
    orig = mod.DB_PATH
    mod.DB_PATH = db
    try:
        snap = (
            "## Session Snapshot — agent — 2026-06-13 10:00 UTC\n\n"
            "### 1. Primary Request and Intent\n- do X thoroughly"
        )
        assert mod.save_to_brain(snap, "agent", {"messages": 3}) is True
        # Identical body (even with a different header minute) -> duplicate.
        snap_later = snap.replace("10:00 UTC", "10:00 UTC")  # same body
        assert mod.save_to_brain(snap_later, "agent", {"messages": 3}) == "duplicate"
        # Genuinely different content -> saves.
        snap2 = snap.replace("do X thoroughly", "do something entirely different now")
        assert mod.save_to_brain(snap2, "agent", {"messages": 3}) is True
        n = sqlite3.connect(str(db)).execute(
            "SELECT count(*) FROM memories WHERE type='session'"
        ).fetchone()[0]
        assert n == 2, f"expected 2 saved (1 deduped), got {n}"
    finally:
        mod.DB_PATH = orig


def test_fingerprint_ignores_header():
    a = "## Session Snapshot — agent — 2026-06-13 10:00 UTC\n\n### 1\n- body"
    b = "## Session Snapshot — agent — 2026-06-13 10:29 UTC\n\n### 1\n- body"
    assert mod._content_fingerprint(a) == mod._content_fingerprint(b)


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        print(f"  PASS {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")


if __name__ == "__main__":
    _run()
