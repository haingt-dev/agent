# Claude Code — agent

## What This Is
Claude Code **tooling repo** — the custom MCP server (haingt-brain), plugins, and project-bootstrap scripts. Global config (CLAUDE.md, settings.json, skills, brains) now lives **natively in `~/.claude/`** (backed up by workstation-setup's bundle) — it is no longer sourced from here.

## Project Structure
- `mcp/haingt-brain/` — Custom MCP server (semantic memory + knowledge graph). Launched via `~/.claude.json`; haint-core hooks call its venv.
- `plugins/` — Claude Code plugins (haint-core, godot-dev). `haint-marketplace` source = this repo.
- `bin/` — Hub scripts (bootstrap, registry audit/sync, shell aliases sourced from `~/.zshrc`).
- `registry.json` — Orientation catalog of all projects (v2: `{path, type, summary, status?}`; capability lists derived on demand, not stored).

## Rules
- This repo hosts CODE (MCP, plugins, tooling), not the live Claude config. For global config edits → edit `~/.claude/` directly.
- Auto-memory lives in `~/.claude/projects/*/memory/` (Claude Code native) — backed up via recovery bundle, NOT by this repo.
