# Agent Global Hub

A personal infrastructure layer for Claude Code — centralizing plugins, skills, hooks, and project bootstrapping across a multi-project workspace.

## Why

Claude Code is powerful but each project is an island. This hub provides the shared **code** layer: a brain MCP for cross-project memory, plugins that inject context at session start, a registry that tracks all projects, and bootstrapping for new ones. (Global config + skills live natively in `~/.claude/`.)

## Features

- **Plugins**: `haint-core` (session hooks, context injection), `godot-dev` (Godot workflows)
- **Brain-powered memory** (haingt-brain MCP) for cross-project context
- **Project registry** with drift detection
- **Bootstrap script** for new projects

> Global config + skills (`CLAUDE.md`, `settings.json`, `skills/`, `brains/`) live natively in `~/.claude/` — not in this repo.

---

**Note**: All agent rules and configs are per-project. This hub only contains shared scripts, templates, and plugins.

## Structure

```
~/Projects/agent/
├── bin/
│   ├── bootstrap-project.sh   # Bootstrap new project + auto-register in hub
│   ├── ag-registry-audit.sh   # Full drift check: registry vs actual state
│   └── shell-aliases.sh       # Shell shortcuts (source in ~/.zshrc)
├── registry.json              # Reverse index of all child projects
├── .claude/scripts/
│   └── registry-check.sh      # SessionStart hook: lightweight drift alert
├── plugins/
│   ├── haint-core/            # Core plugin: hooks (SessionStart, PreToolUse, PreCompact, ...)
│   └── godot-dev/             # Godot plugin: gdformat, GDScript workflows
├── mcp/
│   └── haingt-brain/          # Custom MCP server: semantic memory + knowledge graph
└── templates/
    └── .claudeignore          # Default ignore template for new projects
```

## Per-Project Structure

Every project has this structure (created by `bootstrap`):

```
project/
├── .claude/
│   ├── CLAUDE.md           # Project context, values, conventions, security
│   ├── settings.json       # Project-specific hooks (if any)
│   └── skills/<name>/      # Skills (SKILL.md + supporting files)
└── .mcp.json               # Project-level MCP servers (where needed)
```

## Architecture

### Token Optimization

Rules are minimized to reduce per-turn token cost:

| What | Where | Token cost |
|------|-------|------------|
| Enforcement (security, dangerous commands) | `settings.json` hooks | **0** (runs as shell) |
| Core directives (no dirty state, reversibility) | `.claude/CLAUDE.md` Values | Once per session |
| Brain context (decisions, prefs, last session) | `SessionStart` hook output | Once per session |
| Project-specific workflows | `skills/<name>/SKILL.md` | On invocation only |

### Skills (`.claude/skills/<name>/SKILL.md`)

Skills use YAML frontmatter for invocation control:

- All skills are invocable by Claude when relevant or by user with `/name`
- Supporting files (templates, references) live alongside SKILL.md in the same directory

### Hooks (`settings.json`)

| Hook | Purpose |
|------|---------|
| `SessionStart` | Inject git status + brain context |
| `PreToolUse` (Bash) | Block dangerous commands, scan for secrets in staged files |
| `Stop` (project-specific) | Auto-format on save (e.g., gdformat for Godot) |

### Project Registry

The hub maintains a reverse index (`registry.json`) of all child projects — which plugins, rules, skills, and MCPs each project uses.

| Component | Role |
|-----------|------|
| `registry.json` | Source of truth: project metadata, resources used |
| `bin/ag-registry-audit.sh` | Full audit: compares registry against filesystem + installed_plugins.json |
| `.claude/scripts/registry-check.sh` | SessionStart hook: silent when clean, alerts on drift |
| `bin/bootstrap-project.sh` | Auto-registers new projects on bootstrap |

**Drift detection**: hybrid pull model — hub SessionStart detects drift automatically, scripts that modify children update the registry as a side effect.

## Quick Commands

```bash
ag-help          # Show all commands
bootstrap <dir>  # Setup new project
ag-status        # Check agent setup across all projects
cdc <project>    # Switch to project directory
```

MIT License
