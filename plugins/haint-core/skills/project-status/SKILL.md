---
name: project-status
description: "Show project status dashboard with git info, Memory Bank freshness, and TODOs. Use when user says 'project status', 'what's going on', 'project overview', 'codebase status', 'how stale is this project', or wants a quick health check of the current project."
model: sonnet
allowed-tools: Read, Glob, Grep, Bash(git *)
---

# Project Status Dashboard

Quick health check of the current project — git state, memory bank freshness, and open TODOs.

## Usage

```
/project-status          → full dashboard
```

## Step 1: Git Info

```bash
git log --oneline -5     # recent commits
git branch --show-current  # current branch
git status --short        # uncommitted changes
```

If not a git repo, show "Not a git repository" and skip git sections.

## Step 2: Memory Bank Freshness

If `.memory-bank/` exists:
- List all `.md` files with modification dates
- Flag files older than 7 days with a warning

If no `.memory-bank/`, skip this section.

## Step 3: Open TODOs

Find TODO/FIXME in recently modified files:
```bash
git diff --name-only HEAD~5 2>/dev/null
```
Then grep those files for TODO/FIXME. If fewer than 5 commits exist, scan all tracked files but limit to 20 results.

## Step 4: Output

```
## Project Status — [project name]

### Git
- Branch: `main`
- Last commit: abc1234 fix: resolve auth bug (2h ago)
- Uncommitted: 3 modified, 1 untracked

### Recent Commits
| Hash | Message | When |
|------|---------|------|
| abc1234 | fix: resolve auth bug | 2h ago |
| def5678 | feat: add login page | 1d ago |

### Memory Bank
| File | Last Updated | Status |
|------|-------------|--------|
| context.md | today | fresh |
| architecture.md | 12 days ago | stale |

### TODOs
| File | Line | Content |
|------|------|---------|
| src/auth.ts:42 | TODO: add rate limiting |
| src/api.ts:78 | FIXME: handle timeout |
```

If nothing noteworthy, keep it brief: "All clear — no stale files, no TODOs."

## Rules

- READ-ONLY — do NOT modify any files
- Keep it scannable — no walls of text
- If a section has nothing to report, omit it rather than showing empty tables
