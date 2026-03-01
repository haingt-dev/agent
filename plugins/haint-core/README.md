# haint-core

Core Claude Code plugin: Memory Bank auto-load, git safety checks.

## Hooks

- **SessionStart**: Shows git branch + recent commits, auto-loads all `.memory-bank/*.md` files
- **PreToolUse (Bash)**: Blocks dangerous commands (`rm -rf /`, `git push --force`, `git reset --hard`, `git clean -fd`) and sensitive file commits (`.env`, `.key`, `.pem`, credentials, secrets)

## Install

```bash
claude plugin marketplace add ~/agent
claude plugin install haint-core@agent --scope user
```
