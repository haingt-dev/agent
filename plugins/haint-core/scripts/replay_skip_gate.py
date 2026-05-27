#!/usr/bin/env python3
"""Replay recent user prompts through the skip gate to measure filter effectiveness.

Walks ~/.claude/projects/*/*.jsonl, extracts plain-text user prompts from the
last N days, runs each through prompt-context.py:should_skip_brain(), and
prints a distribution report.

Usage:
    python replay_skip_gate.py [--days 10] [--heuristic-only] [--llm-sample N]

Modes:
    --heuristic-only   Skip LLM tiebreaker entirely (treat all ambiguous as default-include).
                       Measures heuristic alone. Cost: $0.
    --llm-sample N     Call real LLM for first N ambiguous prompts (cost ~$0.00002 each).
                       Skip remaining ambiguous prompts.
                       Default: 100. Pass 0 for heuristic-only equivalent.
    --days N           Look back N days. Default 10.
"""

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

# Load prompt-context.py module
SCRIPT_DIR = Path(__file__).parent
_spec = importlib.util.spec_from_file_location(
    "prompt_context", SCRIPT_DIR / "prompt-context.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


PROJECTS_DIR = Path.home() / ".claude" / "projects"


def extract_prompts(days: int) -> list[tuple[Path, str]]:
    """Walk all project transcripts, return [(session_file, prompt_text), ...].

    Filters:
    - type='user' only
    - content is plain string (not list of tool_result blocks)
    - excludes synthetic system reminders, slash commands, attachments
    """
    cutoff = datetime.now() - timedelta(days=days)
    prompts: list[tuple[Path, str]] = []

    for jsonl in PROJECTS_DIR.glob("*/*.jsonl"):
        # File-level cutoff to skip old transcripts quickly
        try:
            if datetime.fromtimestamp(jsonl.stat().st_mtime) < cutoff:
                continue
        except OSError:
            continue

        try:
            with jsonl.open() as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") != "user":
                        continue
                    msg = obj.get("message") or {}
                    content = msg.get("content")
                    # Plain string content only (tool results are lists)
                    if not isinstance(content, str):
                        continue
                    content = content.strip()
                    if not content:
                        continue
                    # Filter synthetic content
                    if content.startswith("<") or content.startswith("[Request"):
                        continue
                    if content.startswith("/") or content.startswith("!"):
                        # Slash + bash already caught by confident gate; include for
                        # accuracy but they'll be confident:slash/bash
                        pass
                    prompts.append((jsonl, content))
        except OSError:
            continue
    return prompts


def run(days: int, llm_sample: int) -> None:
    print(f"Scanning ~/.claude/projects for last {days} days...")
    prompts = extract_prompts(days)
    print(f"Found {len(prompts)} user prompts.\n")

    if not prompts:
        return

    # Track LLM call count to enforce sample cap
    llm_call_count = [0]
    original_llm_classify = _mod.llm_classify

    def capped_llm(prompt: str):
        if llm_call_count[0] >= llm_sample:
            return None  # Treated as "API fail" → heuristic fallback
        llm_call_count[0] += 1
        return original_llm_classify(prompt)

    # Counters
    reasons: Counter[str] = Counter()
    skip_count = 0
    include_count = 0
    by_session: dict[str, Counter[str]] = {}

    with patch.object(_mod, "llm_classify", side_effect=capped_llm), \
         patch.object(_mod, "_log_skip"), \
         patch.object(_mod, "_log_llm_tiebreak"):
        for jsonl, prompt in prompts:
            try:
                skip, reason = _mod.should_skip_brain(prompt)
            except Exception as e:
                reason = f"error:{type(e).__name__}"
                skip = False
            reasons[reason] += 1
            if skip:
                skip_count += 1
            else:
                include_count += 1
            session_id = jsonl.stem[:8]
            by_session.setdefault(session_id, Counter())[reason] += 1

    total = skip_count + include_count
    print(f"{'='*70}")
    print(f"RESULTS ({total} prompts, {llm_call_count[0]} LLM calls)")
    print(f"{'='*70}")
    print(f"Skip:    {skip_count:5d}  ({skip_count/total*100:5.1f}%)")
    print(f"Include: {include_count:5d}  ({include_count/total*100:5.1f}%)")
    print()
    print(f"Estimated LLM cost: ${llm_call_count[0] * 0.00002:.4f}")
    print()
    print("Reason breakdown (top 20):")
    max_count = max(reasons.values())
    for reason, count in reasons.most_common(20):
        bar = "█" * int(count / max_count * 40)
        print(f"  {count:5d}  {reason:40s} {bar}")

    # Per-project breakdown
    by_project: dict[str, Counter[str]] = {}
    project_totals: Counter[str] = Counter()
    for session_id, counter in by_session.items():
        # Reverse-map session to project via prompts list
        pass
    # Rebuild via re-walk for clarity
    project_skip: Counter[str] = Counter()
    project_total: Counter[str] = Counter()
    for jsonl, prompt in prompts:
        proj = jsonl.parent.name.replace("-home-haint-Projects-", "")
        project_total[proj] += 1
        with patch.object(_mod, "llm_classify", return_value=None), \
             patch.object(_mod, "_log_skip"):
            skip, _ = _mod.should_skip_brain(prompt)
        if skip:
            project_skip[proj] += 1

    print()
    print("Per-project skip rate (heuristic-only):")
    for proj, total_p in project_total.most_common():
        skip_p = project_skip[proj]
        rate = skip_p / total_p * 100 if total_p else 0
        bar = "█" * int(rate / 60 * 30)
        print(f"  {proj:30s} {skip_p:4d}/{total_p:4d}  {rate:5.1f}%  {bar}")

    # Sample ambiguous-zone prompts (where LLM fires) for spot check
    print()
    print("Sample skipped prompts (5 random by reason):")
    seen_reasons: set[str] = set()
    skipped_samples: list[tuple[str, str]] = []
    for jsonl, prompt in prompts:
        with patch.object(_mod, "llm_classify", return_value=None), \
             patch.object(_mod, "_log_skip"):
            skip, reason = _mod.should_skip_brain(prompt)
        if skip and reason not in seen_reasons:
            seen_reasons.add(reason)
            skipped_samples.append((reason, prompt[:80].replace("\n", " ")))
            if len(skipped_samples) >= 5:
                break
    for reason, preview in skipped_samples:
        print(f"  [{reason}] {preview}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--llm-sample", type=int, default=100,
                        help="Max real LLM calls (cost ~$0.00002 each). 0 = heuristic only.")
    parser.add_argument("--heuristic-only", action="store_true",
                        help="Shortcut for --llm-sample 0")
    args = parser.parse_args()
    if args.heuristic_only:
        args.llm_sample = 0
    run(args.days, args.llm_sample)


if __name__ == "__main__":
    main()
