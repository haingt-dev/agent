# Agent Global Hub

Cross-project tools and templates for multi-agent development (Claude, Kilo Code, Antigravity).

**Note**: All agent rules and configs are per-project. This hub only contains shared scripts, templates, and plugins.

## Structure

```
~/agent/  (symlinked as ~/.agent_global/)
├── bootstrap-project.sh    # Bootstrap new project with full agent structure
├── shell-aliases.sh        # Shell shortcuts (source in ~/.zshrc)
├── hooks/                  # Git hooks (post-commit Memory Bank reminder)
├── plugins/
│   ├── haint-core/         # Core plugin: hooks, skills (fix-issue, review-pr, story)
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
├── AGENTS.md               # Shared context (all agents read this)
├── .memory-bank/           # Project knowledge (brief, product, context, task, arch, tech)
│   └── stories/            # Dev stories for devlogs (not auto-loaded)
├── .claude/
│   ├── CLAUDE.md           # Claude-specific config
│   ├── settings.json       # Project-specific hooks (if any)
│   └── skills/<name>/      # Skills (SKILL.md + supporting files)
├── .kilocode/rules/        # Kilo Code rules
├── .antigravity/rules.md   # Antigravity workspace rules
├── .agent/skills/          # Antigravity skills
└── .mcp.json               # Project-level MCP servers (where needed)
```

## Architecture

### Token Optimization

Rules are minimized to reduce per-turn token cost:

| What | Where | Token cost |
|------|-------|------------|
| Enforcement (security, dangerous commands) | `settings.json` hooks | **0** (runs as shell) |
| Core directives (no dirty state, reversibility) | `AGENTS.md` Values | Once per session |
| Memory Bank context | `SessionStart` hook output | Once per session |
| Project-specific workflows | `skills/<name>/SKILL.md` | On invocation only |

### Skills (`.claude/skills/<name>/SKILL.md`)

Skills use YAML frontmatter for invocation control:

- **Auto-invocable** (default): Claude calls when relevant (e.g., `create-note`, `write-gdd`)
- **Manual-only** (`disable-model-invocation: true`): User triggers with `/name` (e.g., `/story`, `/review-pr`)
- Supporting files (templates, references) live alongside SKILL.md in the same directory

### Hooks (`settings.json`)

| Hook | Purpose |
|------|---------|
| `SessionStart` | Inject git status + Memory Bank context |
| `PreToolUse` (Bash) | Block dangerous commands, scan for secrets in staged files |
| `Stop` (project-specific) | Auto-format on save (e.g., gdformat for Godot) |

## Quick Commands

```bash
ag-help          # Show all commands
bootstrap <dir>  # Setup new project
ag-status        # Check agent setup across all projects
mbk / mbc / mbt  # Edit Memory Bank / context.md / task.md
cdc <project>    # Switch to project directory
```
