# haint-core

Core Claude Code plugin: hooks (session context, git safety, notifications).

## Hooks

- **SessionStart**: Shows git branch + recent commits, loads `.memory-bank/brief.md` (project identity)
- **PreToolUse (Bash)**: Two-tier safety — `deny` for catastrophic commands (`rm -rf /`, `rm -rf ~`), `ask` (permission dialog) for risky operations (`git push --force`, `git reset --hard`, `git clean -fd`, sensitive file commits)
- **Notification**: Desktop notification via `notify-send` when Claude needs attention

## Memory Architecture

Session context is layered:
1. **Global CLAUDE.md** — behavioral instructions + `@import` for identity/career context
2. **Project CLAUDE.md** — project-specific instructions
3. **brief.md** — project identity (loaded by this plugin's SessionStart hook)
4. **Auto-memory (MEMORY.md)** — session learnings (managed by Claude Code)
5. **Engram** — cross-project dynamic memory (MCP plugin)

## Install

```bash
claude plugin marketplace add ~/Projects/agent
claude plugin install haint-core@haint-marketplace --scope user
```
