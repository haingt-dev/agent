# Claude Code — agent

## What This Is
Infrastructure hub for Claude Code — global config, skills, memories, and plugins.

## Project Structure
- `global/` — Source of truth for `~/.claude/` (CLAUDE.md, skills/, settings.json, brains/ all symlinked out)
- `bin/` — Hub scripts (bootstrap, registry audit/sync, shell aliases)
- `memories/` — Auto-memory storage (symlinked from `~/.claude/projects/*/memory`)
- `plugins/` — Claude Code plugins (haint-core, godot-dev)
- `mcp/haingt-brain/` — Custom MCP server (semantic memory + knowledge graph)
- `templates/memory-bank/` — Bootstrap templates

## Rules
- Changes to `global/CLAUDE.md` affect ALL projects — be careful
- `memories/` subdirs are symlink targets — don't delete even when empty, or auto-memory breaks
- `global/brains/*.md` files are symlinked from `~/.claude/brains/` — keep filenames stable
