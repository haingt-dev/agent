# godot-dev

Godot 4.x development skills + bundled MCP server for Claude Code.

## Skills

- **godot-gdscript-patterns**: State machines, autoloads, resources, object pooling, component system, scene management, save system, performance tips
- **godot-debugging**: Error interpretation, common bugs, debugging techniques, Godot 4 migration issues
- **godot-status**: Standardized project status dashboard (docs/STATUS.md convention)

## MCP server (since v2.4.0)

Bundles [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) (`npx -y @coding-solo/godot-mcp`, `GODOT_PATH=~/.local/bin/godot`) — starts automatically wherever the plugin is enabled. 14 tools: run/debug-output/stop loop, project introspection, scene scaffolding.

**Probe-verified 2026-06-12** (6-agent hands-on probe, chimera): run→observe loop is clean; scene-op tools have false-success traps. **Usage law lives in the consuming project** — chimera: `docs/tech.md` § "Godot MCP"; patch list for fork day: chimera auto-memory `godot-mcp-install.md`. Read the law before driving the scene tools.

Note: project-level `.mcp.json` `godot` entries are retired — IronCradle's was removed 2026-06-12 when it got plugin v2.4.0; the plugin is now the single source for the godot MCP across all Godot projects.

## Install

```bash
claude plugin marketplace add ~/Projects/agent
claude plugin install godot-dev@haint-marketplace --scope project
```

Note: IronCradle's Stop hook (gdformat) is project-specific — kept in IronCradle's `.claude/settings.json`. (Project formerly named Wildtide.)
