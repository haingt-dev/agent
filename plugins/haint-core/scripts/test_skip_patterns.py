#!/usr/bin/env python3
"""Tests for Path C skip gate + Hybrid Option 2 LLM tiebreaker.

Two test sets:
- CONFIDENT cases: heuristic alone decides, LLM must NOT be called.
- AMBIGUOUS cases: heuristic + LLM tiebreaker; verify hybrid decision logic.

Run: python test_skip_patterns.py
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

_spec = importlib.util.spec_from_file_location(
    "prompt_context", Path(__file__).parent / "prompt-context.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
should_skip_brain = _mod.should_skip_brain


# Confident cases — heuristic only. LLM mock raises if called.
CONFIDENT_CASES = [
    # (prompt, expected_skip, label)
    # too_short
    ("ok", True, "too_short"),
    ("yes", True, "too_short"),
    ("tiếp tục", True, "VN too_short"),
    ("hi", True, "too_short <10c"),
    # confident pattern (slash, bash)
    ("/research compare React vs Vue", True, "slash command"),
    ("/loop 5m /foo", True, "slash with args"),
    ("!ls -la /tmp", True, "bash escape"),
    # trivial_short (≤4 words, no ?)
    ("go run that", True, "trivial_short 3w"),
    ("done thanks bro", True, "trivial_short 3w"),
    ("just do it", True, "trivial_short 3w"),
    # substantive_length (>8 words)
    ("how do I implement a binary search tree in Python?", False, "long question"),
    ("the test is failing because of a race condition somehow", False, "long diagnostic"),
    ("explain the architecture of the authentication system in detail", False, "explain request"),
    ("a" * 6000, False, "long_prompt >5000c"),
    # contrast marker (any length)
    ("tiếp tục theo plan A nhưng chỉnh sửa abc", False, "VN contrast nhưng"),
    ("ok continue but check recall.py logic", False, "EN contrast but"),
    ("ok let me try actually wait", False, "actually contrast"),
]


# Ambiguous cases — 5-8 word prompts without contrast, no confident pattern.
# Each tuple: (prompt, llm_returns, expected_skip, expected_reason_match, label)
AMBIGUOUS_CASES = [
    # Both signals agree: SKIP
    ("ok let me try that approach", "skip", True, "agree_skip:continuation_en", "EN ack + LLM agrees skip"),
    ("tiếp tục với cách đó nhé", "skip", True, "agree_skip:continuation_vn", "VN ack + LLM agrees skip"),
    # Heuristic wants skip, LLM overrides → include
    ("ok let me try recall.py fix", "include", False, "llm_override_pattern:continuation_en", "EN ack but file ref"),
    ("tiếp tục sửa file judge.py giúp", "include", False, "llm_override_pattern:continuation_vn", "VN ack but file ref"),
    # Heuristic default-include, LLM detects ack → skip
    ("fix the typo in line 5", "skip", True, "llm_only_skip", "code task LLM skip"),
    ("rename foo to bar everywhere", "skip", True, "llm_only_skip", "rename LLM skip"),
    # Both agree: include
    ("fix the bug in parser.py", "include", False, "agree_include", "code task w/ file"),
    ("update database schema this morning", "include", False, "agree_include", "task with context"),
    # LLM fails → trust heuristic
    ("ok let me try that thing", None, True, "pattern:continuation_en|llm_fail", "LLM fail → trust skip"),
    ("update something in the system", None, False, "default_include|llm_fail", "LLM fail → default include"),
]


def run_confident() -> int:
    fails = 0
    print("─" * 72)
    print("CONFIDENT CASES (heuristic only — LLM must NOT be called)")
    print("─" * 72)
    for prompt, expected, label in CONFIDENT_CASES:
        with patch.object(
            _mod, "llm_classify",
            side_effect=AssertionError("LLM called when heuristic was confident"),
        ):
            try:
                actual_skip, reason = should_skip_brain(prompt)
                ok = actual_skip == expected
            except AssertionError:
                ok = False
                actual_skip, reason = "?", "LLM was called"
        status = "✓" if ok else "✗"
        if not ok:
            fails += 1
        print(f"  {status} [{label}] expect={expected} got={actual_skip} reason={reason}")
    return fails


def run_ambiguous() -> int:
    fails = 0
    print("\n" + "─" * 72)
    print("AMBIGUOUS CASES (LLM tiebreaker)")
    print("─" * 72)
    for prompt, llm_ret, expected_skip, expected_reason, label in AMBIGUOUS_CASES:
        with patch.object(_mod, "llm_classify", return_value=llm_ret), \
             patch.object(_mod, "_log_llm_tiebreak"):
            actual_skip, reason = should_skip_brain(prompt)
        ok = (actual_skip == expected_skip) and (reason == expected_reason)
        status = "✓" if ok else "✗"
        if not ok:
            fails += 1
        print(f"  {status} [{label}] llm={llm_ret} got=({actual_skip}, {reason})")
    return fails


def main():
    total = len(CONFIDENT_CASES) + len(AMBIGUOUS_CASES)
    fails = run_confident() + run_ambiguous()
    print(f"\n{total - fails}/{total} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
