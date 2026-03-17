# Agent Global Hub

A personal infrastructure layer for Claude Code — centralizing plugins, skills, hooks, and project bootstrapping across a multi-project workspace.

## Why

Claude Code is powerful but each project is an island. Configuration, skills, and memory are project-local by default. This hub creates a shared layer: global skills available everywhere, plugins that inject context at session start, a registry that tracks all projects, and templates for bootstrapping new ones.

## Features

- **Global skills**: `/alfred` (life scheduler), `/mentor`, `/gen-image`, `/story`, `/token-optimize`
- **Plugins**: `haint-core` (session hooks, context injection), `godot-dev` (Godot workflows)
- **Project registry** with drift detection
- **Bootstrap script** for new projects
- **Memory system** for cross-project context

---

**Note**: All agent rules and configs are per-project. This hub only contains shared scripts, templates, and plugins.

## Structure

```
~/Projects/agent/
├── bootstrap-project.sh    # Bootstrap new project + auto-register in hub
├── ag-sync-rules.sh        # Sync shared rules to child projects + update registry
├── ag-registry-audit.sh    # Full drift check: registry vs actual state
├── registry.json           # Reverse index of all child projects
├── shell-aliases.sh        # Shell shortcuts (source in ~/.zshrc)
├── .claude/scripts/
│   └── registry-check.sh   # SessionStart hook: lightweight drift alert
├── plugins/
│   ├── haint-core/         # Core plugin: hooks (SessionStart, PreToolUse, Notification)
│   └── godot-dev/          # Godot plugin: gdformat, GDScript workflows
└── templates/
    ├── memory-bank/        # Templates for new project Memory Banks
    │   └── stories/        # Story template + index
    ├── agents/             # Sub-agent templates (code-reviewer, security-reviewer)
    ├── .env.example
    └── .gitignore-secrets
```

## Per-Project Structure

Every project has this structure (created by `bootstrap`):

```
project/
├── .memory-bank/           # Project knowledge (brief, product, context, task, arch, tech)
│   └── stories/            # Dev stories for devlogs (not auto-loaded)
├── .claude/
│   ├── CLAUDE.md           # Project context, values, memory bank, security
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
| Memory Bank context | `SessionStart` hook output | Once per session |
| Project-specific workflows | `skills/<name>/SKILL.md` | On invocation only |

### Skills (`.claude/skills/<name>/SKILL.md`)

Skills use YAML frontmatter for invocation control:

- All skills are invocable by Claude when relevant or by user with `/name`
- Supporting files (templates, references) live alongside SKILL.md in the same directory

### Hooks (`settings.json`)

| Hook | Purpose |
|------|---------|
| `SessionStart` | Inject git status + Memory Bank context |
| `PreToolUse` (Bash) | Block dangerous commands, scan for secrets in staged files |
| `Stop` (project-specific) | Auto-format on save (e.g., gdformat for Godot) |

### Project Registry

The hub maintains a reverse index (`registry.json`) of all child projects — which plugins, rules, skills, and MCPs each project uses.

| Component | Role |
|-----------|------|
| `registry.json` | Source of truth: project metadata, resources used |
| `ag-registry-audit.sh` | Full audit: compares registry against filesystem + installed_plugins.json |
| `.claude/scripts/registry-check.sh` | SessionStart hook: silent when clean, alerts on drift |
| `bootstrap-project.sh` | Auto-registers new projects on bootstrap |
| `ag-sync-rules.sh` | Updates registry rules after syncing |

**Drift detection**: hybrid pull model — hub SessionStart detects drift automatically, scripts that modify children update the registry as a side effect.

## Quick Commands

```bash
ag-help          # Show all commands
bootstrap <dir>  # Setup new project
ag-status        # Check agent setup across all projects
mbk / mbc / mbt  # Edit Memory Bank / context.md / task.md
cdc <project>    # Switch to project directory
```

MIT License
