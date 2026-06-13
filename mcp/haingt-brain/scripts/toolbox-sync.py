#!/usr/bin/env python3
"""SessionStart auto-sync for the brain Semantic Toolbox.

Reindexes the toolbox in the BACKGROUND, but only when the skill / plugin / MCP-config surface
actually changed since the last index — so a session start is never delayed and we don't burn
embeddings every session. Wired as a SessionStart hook in ~/.claude/settings.json.

What it CAN keep in sync automatically (everything file/config-derived):
  - user / project / native / plugin skills (add, remove, edit, scope change)
  - per-server MCP scoping (a server moving between global and a project's .mcp.json)
  - the curated NATIVE_SKILLS / MCP_TOOLS lists (they live in index_tools.py, which is fingerprinted)

What it CANNOT do (a verified Claude Code limitation, not a bug):
  - discover MCP *tool schemas* for project-scoped servers (notebooklm, aseprite, civitai, ...).
    Hooks get no live tool list — no payload field, no env var, no CLI, and hooks can't call MCP
    (GitHub issues #6574, #26112). Those stay curated; capture them once from inside the project
    session where the server is actually connected.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
BRAIN = HOME / "Projects/agent/mcp/haingt-brain"
PY = BRAIN / ".venv/bin/python3"
IDX = BRAIN / "scripts/index_tools.py"
FP = BRAIN / ".toolbox-fingerprint"
LOCK = BRAIN / ".toolbox-sync.lock"


def _read(p) -> str:
    try:
        return Path(p).read_text(encoding="utf-8")
    except Exception:
        return ""


def _skill_files() -> list[Path]:
    files: list[Path] = []
    base = HOME / ".claude/skills"
    if base.exists():
        files += sorted(base.glob("*/SKILL.md"))
    pdir = HOME / "Projects"
    if pdir.exists():
        for proj in sorted(pdir.iterdir()):
            sd = proj / ".claude/skills"
            if sd.exists():
                files += sorted(sd.glob("*/SKILL.md"))
    cache = HOME / ".claude/plugins/cache"
    if cache.exists():
        files += sorted(cache.glob("*/*/*/skills/*/SKILL.md"))
    return files


def fingerprint() -> str:
    h = hashlib.sha256()
    # Skill content + path (path list catches add/remove; content catches edits)
    for f in _skill_files():
        h.update(str(f).encode())
        h.update(_read(f).encode())
    # Plugin install state + global enable state
    h.update(_read(HOME / ".claude/plugins/installed_plugins.json").encode())
    try:
        s = json.loads(_read(HOME / ".claude/settings.json") or "{}")
        h.update(json.dumps(s.get("enabledPlugins"), sort_keys=True).encode())
    except Exception:
        pass
    # MCP scope: per-project settings (enabledPlugins) + each project's .mcp.json
    pdir = HOME / "Projects"
    if pdir.exists():
        for proj in sorted(pdir.iterdir()):
            h.update(_read(proj / ".claude/settings.json").encode())
            h.update(_read(proj / ".mcp.json").encode())
    # ~/.claude.json churns constantly (session state) — hash ONLY the MCP-relevant slice
    try:
        cj = json.loads(_read(HOME / ".claude.json") or "{}")
        mcp = {
            "global": cj.get("mcpServers"),
            "per_project": {k: v.get("mcpServers") for k, v in cj.get("projects", {}).items()},
        }
        h.update(json.dumps(mcp, sort_keys=True).encode())
    except Exception:
        pass
    # The indexer itself carries the curated NATIVE_SKILLS / MCP_TOOLS lists
    h.update(_read(IDX).encode())
    return h.hexdigest()


def main() -> None:
    # Drain the hook payload from stdin; we don't need it.
    try:
        sys.stdin.read()
    except Exception:
        pass

    new = fingerprint()
    if new == _read(FP).strip():
        return  # nothing changed → no reindex, fast exit

    py = str(PY) if PY.exists() else "python3"
    # Detach the reindex (start_new_session=True) so it survives this hook returning and never
    # blocks session start. The fingerprint is written ONLY on success, so a failed/killed run
    # simply retries next session.
    # flock -n serializes reindexes: the indexer is a clear-all-then-rebuild pass, so two
    # sessions starting close together (or a still-running reindex) MUST NOT overlap or the tool
    # count corrupts. If the lock is held, flock exits immediately and this session just skips.
    cmd = f"flock -n {LOCK} -c '{py} {IDX} >/dev/null 2>&1 && printf %s {new} > {FP}'"
    subprocess.Popen(
        ["bash", "-c", cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


if __name__ == "__main__":
    main()
