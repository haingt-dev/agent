---
name: ship
description: Verify, update Memory Bank, and commit — one command to ship changes
disable-model-invocation: true
---

# Ship

Verify → Update Memory Bank → Update Docs → Commit. One command instead of many.

## Usage

```
/ship [commit message]
```

If no commit message provided, auto-generate one from the changes.

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

**STOP immediately if verification fails.** Report the failure, do not continue to step 2.

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
- If `$ARGUMENTS` is empty, generate a commit message based on the changes
