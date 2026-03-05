---
name: ship
description: "Verify, update Memory Bank, and commit — one command to ship changes. Use when user says 'ship it', 'commit this', 'done, ship', or wants to verify+commit their work."
argument-hint: "[commit-message]"
allowed-tools: Bash(git *), Bash(bun *), Bash(npm *), Bash(cargo *), Bash(pytest *), Bash(make *), Read, Grep, Glob, Write, Edit
---

# Ship

Verify → Update Memory Bank → Update Docs → Auto-capture Story → Commit. One command instead of many.

## Usage

```
/ship [commit message]
```

If no commit message provided, auto-generate one from the changes.

## Step 0: Pre-flight Check

Run `git status`. If there are no changes (nothing staged, no modifications, no untracked files), report "Nothing to ship" and stop.

## Step 1: Verify

Run the project's verification before committing.

**Detection order:**

1. Check `.claude/CLAUDE.md` or `AGENTS.md` for project-specific test/lint/build commands — use those first
2. Auto-detect by project type:
   - `package.json` with test script → `bun test` or `npm test`
   - `Cargo.toml` → `cargo test`
   - `pyproject.toml` → `pytest`
   - `project.godot` with GUT → run GUT tests
   - `Makefile` with test target → `make test`
3. If no test runner found → review `git diff` for bugs, security issues, logic errors

**STOP immediately if verification fails.** Report which specific tests/checks failed and the error output, then stop. Do not continue to step 2. The user needs to fix the failures before shipping.

## Step 2: Update Memory Bank

If `.memory-bank/` exists in the project:

1. Read current `.memory-bank/context.md`
2. Review what changed this session via `git diff` and `git log`
3. Update `context.md` with current focus, recent changes, active workstreams
4. If architecture changed → also update `architecture.md`
5. If tech stack changed → also update `tech.md`
6. If tasks changed → also update `task.md`

**Skip this step** if the changes are trivial (typos, formatting-only, config tweaks that don't affect context).

## Step 3: Update Docs

Check if code changes affect any project documentation:

1. Scan for docs that reference changed code — README, API docs, guides, templates, storyboards, style guides, etc.
2. If changes alter behavior, API, architecture, or workflows that are documented → update those docs
3. If no docs are affected → skip this step

Include doc updates in the main code commit (not a separate commit).

## Step 3.5: Auto-capture Story

<!-- Story trigger signals synced with: plugins/haint-core/skills/story/SKILL.md -->

If `.memory-bank/` exists, evaluate whether this session is worth capturing as a dev story. **No confirmation prompt** — decide autonomously.

### 1. Determine tier from scope of changes

| Tier | Signals | Action |
|---|---|---|
| **Trivial** | Typo, rename, config tweak, formatting | Skip silently |
| **Small** | Bug fix, minor feature, small refactor | Create **micro-story** |
| **Big** | New feature, architecture change, debugging odyssey, multi-file overhaul, creative workaround, performance win | Create **full story** |

### 2. Tier Big requires at least 1 trigger signal

- Debugging odyssey with non-obvious root cause
- Architecture decision that went against initial instinct
- Creative/unconventional workaround that worked
- Performance win with interesting approach
- Expectation flip (tried X, failed because Y)
- Tool/library gotcha or undocumented behavior

### 3. Create story by tier

**Micro-story (Small tier):**
- 1-3 sentences, natural tone, can be sarcastic/witty
- Examples: "Fix cái bug mà AI generate sai path. Ironic." / "Thêm 1 button, sửa 3 file. Frontend moment."
- Same file format as full story but minimal content
- Status: `micro`

**Full story (Big tier):**
- **Title**: concise, descriptive
- **Date**: today
- **Tags**: 2-4 tags
- **TL;DR**: 1-2 sentences
- **The Problem**: what we were trying to do
- **The Journey**: what happened, what we tried, what surprised us
- **The Insight**: the takeaway
- **Technical Details**: include if specifics are interesting
- Status: `draft`

### 4. Save

- Save to `.memory-bank/stories/YYYY-MM-DD-slug.md`
- Update `.memory-bank/stories/index.md` (create dir + index if needed)
- Show in ship output:
  - Micro → inline quote of the story
  - Full → `Story captured: [title]`
- Story file gets included in the memory bank commit in Step 4

## Step 4: Commit

1. Stage all relevant code changes (exclude `.memory-bank/`)
2. Create commit with conventional commit message, or use `$ARGUMENTS` if provided
3. If Memory Bank was updated in step 2:
   - Stage `.memory-bank/` files
   - Create a separate commit: `docs: update memory bank`
4. Show the result: commit hash(es), files changed, summary

## Rules

- Follow the project's existing commit message conventions — check `git log --oneline -5`
- Never commit files that contain secrets (`.env`, credentials)
- Never push to remote — only local commits
- If `$ARGUMENTS` is empty, generate a commit message using conventional commit format (`type(scope): description`) — check `git log --oneline -5` for the project's existing style and match it
