#!/usr/bin/env python3
"""Deterministic STATUS.md freshness check — the enforceable half of godot-status.

A Claude skill can't run inside a git pre-commit hook (it needs Claude), so the
anti-rot guarantee lives here as a plain, dependency-free script you CAN wire into
pre-commit (mirrors IronCradle's tools/derive_status.py --check). It does NOT judge
content — it only enforces the cheap, deterministic invariant: docs/STATUS.md exists
and its `updated:` date is not older than the newest *code* change.

Exit codes: 0 = fresh · 1 = stale or missing (with a message on stderr).

Usage:
    python3 status_check.py [repo_root]          # default: cwd
    python3 status_check.py --quiet              # exit code only

Pre-commit (.pre-commit-config.yaml), once init drops this into the repo's tools/:
    - repo: local
      hooks:
        - id: status-fresh
          name: STATUS.md is fresh
          entry: python3 tools/status_check.py
          language: system
          pass_filenames: false
"""
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# Paths whose changes do NOT require a STATUS bump (docs about status itself, etc.).
IGNORE_PREFIXES = ("docs/", ".github/", ".claude/")


def sh(args: list[str], cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True).stdout.strip()


def last_code_commit_date(root: Path) -> date | None:
    """Date (YYYY-MM-DD) of the newest commit that touched a non-doc, non-meta file."""
    out = sh(["git", "log", "-30", "--format=%cs|%H"], root)
    for line in out.splitlines():
        cdate, _, sha = line.partition("|")
        files = sh(["git", "show", "--name-only", "--format=", sha], root).splitlines()
        if any(f and not f.startswith(IGNORE_PREFIXES) for f in files):
            try:
                return date.fromisoformat(cdate)
            except ValueError:
                return None
    return None


def status_updated_date(status_md: Path) -> date | None:
    text = status_md.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^updated:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, re.MULTILINE)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    quiet = "--quiet" in sys.argv
    root = Path(args[0]) if args else Path.cwd()
    status_md = root / "docs" / "STATUS.md"

    if not status_md.exists():
        if not quiet:
            print("FAIL: docs/STATUS.md missing — run `/godot-status init`.", file=sys.stderr)
        return 1

    updated = status_updated_date(status_md)
    if updated is None:
        if not quiet:
            print("FAIL: docs/STATUS.md has no valid `updated: YYYY-MM-DD` frontmatter.", file=sys.stderr)
        return 1

    code_date = last_code_commit_date(root)
    if code_date and updated < code_date:
        if not quiet:
            print(
                f"FAIL: docs/STATUS.md is stale — updated {updated}, last code change {code_date}. "
                "Run `/godot-status update` (or update STATUS.md) before committing.",
                file=sys.stderr,
            )
        return 1

    if not quiet:
        print(f"OK: docs/STATUS.md fresh (updated {updated}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
