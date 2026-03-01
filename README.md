# Agent Global Hub

Cross-project tools and templates for multi-agent development (Claude, Kilo Code, Antigravity).

**Note**: All agent rules and configs are per-project. This hub only contains shared scripts and templates.

## Structure

```
~/agent/  (symlinked as ~/.agent_global/)
├── ag-sync-rules.sh        # Sync commit-protocol to all projects
├── bootstrap-project.sh    # Bootstrap new project with full agent structure
├── shell-aliases.sh        # Shell shortcuts (source in ~/.zshrc)
├── hooks/                  # Git hooks (post-commit Memory Bank reminder)
└── templates/
    ├── rules/
    │   └── commit-protocol.md  # Only shared rule (format guide)
    ├── memory-bank/            # Templates for new project Memory Banks
    ├── .env.example
    └── .gitignore-secrets
```

## Per-Project Structure

Every project has this structure (created by `bootstrap`):

```
project/
├── AGENTS.md               # Shared context (all agents read this)
├── .memory-bank/           # Project knowledge (brief, product, context, arch, tech)
├── .claude/
│   ├── CLAUDE.md           # Claude-specific config
│   ├── settings.json       # Hooks (SessionStart, PreToolUse, Stop)
│   ├── rules/*.md          # Claude rules (auto-loaded, currently: commit-protocol)
│   └── skills/<name>/      # Skills (SKILL.md + supporting files)
├── .kilocode/rules/*.md    # Kilo Code rules
├── .agents/rules/*.md      # Antigravity rules
└── .mcp.json               # Project-level MCP servers (where needed)
```

## Architecture

### Token Optimization

Rules are minimized to reduce per-turn token cost:

| What | Where | Token cost |
|------|-------|------------|
| Enforcement (security, dangerous commands) | `settings.json` hooks | **0** (runs as shell) |
| Core directives (no dirty state, reversibility) | `AGENTS.md` Values | Once per session |
| Commit format | `rules/commit-protocol.md` | Once per session |
| Memory Bank context | `SessionStart` hook output | Once per session |
| Project-specific workflows | `skills/<name>/SKILL.md` | On invocation only |

### Skills (`.claude/skills/<name>/SKILL.md`)

Skills use YAML frontmatter for invocation control:

- **Auto-invocable** (default): Claude calls when relevant (e.g., `create-note`, `write-gdd`)
- **Manual-only** (`disable-model-invocation: true`): User triggers with `/name` (e.g., `/test`, `/lint`)
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
ag-sync-rules    # Sync commit-protocol to all projects
ag-status        # Check agent setup across all projects
mbk / mbc        # Edit Memory Bank / context.md
cdc <project>    # Switch to project directory
```

## Updating Shared Rules

1. Edit template: `ag-rules` (opens `~/.agent_global/templates/rules/`)
2. Sync to all projects: `ag-sync-rules`
3. Sync to one project: `ag-sync-rules ProjectName`

Only `commit-protocol.md` is synced. All other enforcement is handled by hooks, and guidance lives in `AGENTS.md`.
