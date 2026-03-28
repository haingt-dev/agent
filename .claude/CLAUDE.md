# Claude Code — agent

## What This Is
Infrastructure hub for Claude Code — global config, skills, memories, and plugins.

## Project Structure
- `global/CLAUDE.md` — Master copy of global CLAUDE.md (symlinked to `~/.claude/CLAUDE.md`)
- `memories/` — Centralized memory storage (symlinked from `~/.claude/projects/*/memory`)
- Skills and hooks managed via Claude Code plugin system

## Rules
- Changes to `global/CLAUDE.md` affect ALL projects — be careful
- Memory files in `memories/` are symlink targets — don't reorganize without updating symlinks
