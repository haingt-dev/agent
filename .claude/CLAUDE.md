# Claude Code — agent

## What This Is
Infrastructure hub for Claude Code — global config, skills, and plugins.

## Project Structure
- `global/` — Source of truth for `~/.claude/` (CLAUDE.md, skills/, settings.json, brains/ all symlinked out)
- `bin/` — Hub scripts (bootstrap, registry audit/sync, shell aliases)
- `plugins/` — Claude Code plugins (haint-core, godot-dev)
- `mcp/haingt-brain/` — Custom MCP server (semantic memory + knowledge graph)
- `templates/memory-bank/` — Bootstrap templates

## Rules
- Changes to `global/CLAUDE.md` affect ALL projects — be careful
- `global/brains/*.md` files are symlinked from `~/.claude/brains/` — keep filenames stable
- Auto-memory lives in `~/.claude/projects/*/memory/` (Claude Code native) — backed up via recovery bundle, NOT by this repo
