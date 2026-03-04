# haint-core

Core Claude Code plugin: Memory Bank auto-load, git safety checks, notifications, workflow skills.

## Hooks

- **SessionStart**: Shows git branch + recent commits, auto-loads all `.memory-bank/*.md` files
- **PreToolUse (Bash)**: Blocks dangerous commands (`rm -rf /`, `git push --force`, `git reset --hard`, `git clean -fd`) and sensitive file commits (`.env`, `.key`, `.pem`, credentials, secrets)
- **Notification**: Desktop notification via `notify-send` when Claude needs attention

## Skills

- **ship**: Verify, update Memory Bank, and commit — one command to ship changes. Usage: `/ship [commit message]`
- **fix-issue**: Fix a GitHub issue end-to-end — investigate, implement, test, commit, PR. Usage: `/fix-issue <issue-number>`
- **review-pr**: Review a pull request for correctness, edge cases, code quality. Usage: `/review-pr <pr-number>`
- **story**: Capture interesting dev stories (debugging journeys, architecture decisions, creative workarounds) for future devlogs/blog posts. Auto-suggests when detecting notable moments.

## Install

```bash
claude plugin marketplace add ~/Projects/agent
claude plugin install haint-core@haint-marketplace --scope user
```
