#!/usr/bin/env python3
"""Stop hook: Surface candidates worth brain_saving from Claude's response.

Scans Claude's response for decision-dense content — version numbers, root causes,
architectural choices, benchmark figures. Prints a one-line suggestion when found.
Never auto-saves: user decides what's worth keeping.
"""

import json
import re
import sys

# Patterns that signal a save-worthy payload
DECISION_PHRASES = [
    r'\bwe decided\b', r'\broot cause\b', r'\bthe fix is\b',
    r'\barchitectural\b', r'\btrade-?off\b', r'\bapproach chosen\b',
    r'\bdeferred\b.*\bbecause\b', r'\bwon\'t\b.*\bbecause\b',
    r'\bkey insight\b', r'\bfundamental\b.*\bissue\b',
]

TECHNICAL_SIGNALS = [
    r'\bv\d+\.\d+\.\d+\b',             # version numbers
    r'\bgpt-[\w\.-]+\b',               # model names
    r'\b\d+%\b.*\b(accuracy|reduction|improvement|faster)\b',  # metrics
    r'\b(O\(n\^?\d*\)|O\(log\))\b',   # complexity
    r'\bSELECT\b.*\bFROM\b',          # SQL snippets (architectural)
    r'\bmin_cluster=\d+\b', r'\bsim_threshold=[\d.]+\b',  # tuning params
]

MIN_MATCH_LENGTH = 60  # minimum excerpt length to surface


def get_response_text(data: dict) -> str:
    """Extract response text from Stop hook payload."""
    # Stop hook format: {"response": "...", "transcript_path": "...", ...}
    return data.get("response", "")


def find_saveable_excerpt(text: str) -> str | None:
    """Find a short excerpt worth surfacing. Returns None if nothing found."""
    lines = text.split('\n')

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if len(line_stripped) < MIN_MATCH_LENGTH:
            continue

        # Check decision phrases
        for pattern in DECISION_PHRASES:
            if re.search(pattern, line_stripped, re.IGNORECASE):
                excerpt = line_stripped[:120]
                return excerpt

        # Check technical signals
        for pattern in TECHNICAL_SIGNALS:
            if re.search(pattern, line_stripped):
                excerpt = line_stripped[:120]
                return excerpt

    return None


def main():
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return

    response = get_response_text(data)
    if not response or len(response) < 200:
        return  # Too short to contain a meaningful save candidate

    excerpt = find_saveable_excerpt(response)
    if excerpt:
        print(f'Consider brain_save: "{excerpt}..."')


if __name__ == "__main__":
    main()
