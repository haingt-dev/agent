# godot-dev

Godot 4.x development skills + bundled MCP server for Claude Code.

## Skills

- **godot-write-gdd**: author/update the project's GDD as a `docs/gdd/` self-contained Obsidian folder (master index + section notes; Summary/Core/Features/Content taxonomy)
- **godot-check-gdd**: check recent code changes against the GDD pillars + sections (drift / scope-creep alignment)
- **godot-new-scene**: scaffold a `.tscn`+`.gd` following the project's existing layout
- **godot-status**: standardized project status dashboard (`docs/STATUS.md` convention)
- **godot-debugging**: error interpretation, common bugs, Godot 3→4 migration
- **godot-gdscript-patterns**: state machines, autoloads, resources, pooling, component system, save system, performance

Skill `description`s are kept terse on purpose — discovery is driven by the brain Semantic Toolbox (`brain_tools`), curated via `/toolbox-curator`, not by verbose frontmatter. Tool/MCP routing → [`references/mcp-routing.md`](references/mcp-routing.md).

### GDD convention (`docs/gdd/`)

A project's GDD lives in the repo at `docs/gdd/` as a **self-contained Obsidian "mini-vault"** — a master index note + single-concern section notes, opened directly in Obsidian. Modular wiki over a monolith; a stable **Core** (pillars → loops → progression) anchors evolving **Features**/**Content**. `godot-write-gdd` authors it; templates live in that skill's `references/`. (Lint/test are intentionally NOT skills — `/ship` + the project's git Stop-hook cover gdformat/GUT.)

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
