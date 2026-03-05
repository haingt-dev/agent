# haint-core

Core Claude Code plugin: hooks (Memory Bank, git safety, notifications) + auto-trigger skills (tempo, quest).

Manual-only skills (ship, fix-issue, review, story, track, reschedule-quest, skills-dashboard, project-status) moved to `~/.claude/skills/` with `disable-model-invocation: true` for token savings.

## Hooks

- **SessionStart**: Shows git branch + recent commits, auto-loads all `.memory-bank/*.md` files
- **PreToolUse (Bash)**: Two-tier safety — `deny` for catastrophic commands (`rm -rf /`, `rm -rf ~`), `ask` (permission dialog) for risky operations (`git push --force`, `git reset --hard`, `git clean -fd`, sensitive file commits)
- **Notification**: Desktop notification via `notify-send` when Claude needs attention

## Plugin Skills (auto-trigger OK)

- **tempo**: Daily dashboard — Todoist quests + Google Calendar events + evaluation. Usage: `/tempo [today|tomorrow|weekly]`
- **quest**: Add or update Todoist tasks with smart classification into quest system. Usage: `/quest thêm/sửa ...`

## User-Level Skills (`~/.claude/skills/`, disable-model-invocation)

- **ship**: `/ship [commit message]`
- **fix-issue**: `/fix-issue <issue-number>`
- **review**: `/review [HEAD~N|branch|hash]`
- **story**: `/story`
- **track**: `/track [start|stop|today]`
- **reschedule-quest**: `/reschedule-quest [task]`
- **skills-dashboard**: `/skills-dashboard [skill-name]`
- **project-status**: `/project-status`

## Install

```bash
claude plugin marketplace add ~/Projects/agent
claude plugin install haint-core@haint-marketplace --scope user
```
