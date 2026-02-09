# Agent Global Configuration Hub

Centralized "hub and spoke" configuration for AI coding agents (Kilo Code, Antigravity).

## Structure

```
~/.agent_global/
├── rules/
│   ├── global_rules.md    # Shared rules across all projects
│   └── auto-commit.md     # Git commit protocol
├── skills/                 # Shared skills (canvas-design, mcp-builder, etc.)
└── README.md
```

## How It Works

- **Rules & Skills** are stored here and symlinked into each project's `.agent/rules/` and `.agent/skills/` (or `.kilocode/rules/`).
- **MCP Configuration** lives in VS Code's global storage: `~/.config/Code/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json`
- **Project Memory Bank** (`memory-bank/`) stays LOCAL in each project — never symlinked.

## Connected Projects

| Project | Path |
|---------|------|
| Idea_Vault | `~/Dropbox/Apps/Obsidian/Idea_Vault` |
| chimera-protocol | `~/Projects/chimera-protocol` |
| media-server | `~/Projects/media-server` |
| systems-migration-main | `~/Projects/systems-migration-main` |

## Adding a New Project

```bash
PROJ=/path/to/project
mkdir -p "$PROJ/.agent/rules"
ln -s ~/.agent_global/rules/global_rules.md "$PROJ/.agent/rules/global_rules.md"
ln -s ~/.agent_global/rules/auto-commit.md "$PROJ/.agent/rules/auto-commit.md"
# Keep memory-bank/ local — do NOT symlink it
```
