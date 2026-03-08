---
name: ship
description: "Review, verify, update Memory Bank, and commit — one command to ship changes."
argument-hint: "[commit-message]"
disable-model-invocation: true
allowed-tools: Bash(git *), Bash(bun *), Bash(npm *), Bash(cargo *), Bash(pytest *), Bash(make *), Read, Grep, Glob, Write, Edit
---

# Ship

Pre-flight → Verify → Review → Update Memory Bank → Update Docs → Commit.

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
3. If no test runner found → skip to Step 2 (review will catch issues)

**STOP immediately if verification fails.** Report which specific tests/checks failed and the error output, then stop. Do not continue. The user needs to fix the failures before shipping.

## Step 2: Review

Always review the diff before committing — structured code review of all changes.

### Determine what to review

Review all uncommitted changes: `git diff` (unstaged) + `git diff --cached` (staged). If nothing there, review `git diff HEAD~1`.

### Assess diff size

- **Small** (<200 lines): review holistically
- **Large** (200+ lines): review file-by-file, prioritize logic-heavy files (.py, .ts, .gd, .rs) over config/generated files

### Review each change

For each changed file/hunk:

**Read context** — don't review the diff in isolation:
- Read the full function around changed lines
- If a function signature changed, grep for callers
- If a test changed, check what it's actually testing

**Check for:**

1. **Correctness** — Does it do what it claims? Off-by-one errors, null access, race conditions, error handling gaps
2. **Security** — Hardcoded secrets, injection vulnerabilities (SQL, command, XSS), path traversal, auth gaps
3. **Logic** — Dead code paths, unreachable conditions, inverted boolean logic, missing edge cases
4. **Style** — Follows existing patterns? Clear naming? Stale comments?
5. **Tests** — New behavior covered? Tests actually assert the right thing?

### Output review

```
## Review: [what was reviewed]

### Issues
- **Critical** [description] — `file:line`
- **Warning** [description] — `file:line`

### Good
- [positive observations]

### Summary
X files changed. [N critical / N warning / N nit]. [LGTM or needs fixes].
```

If nothing found: "LGTM — no issues found in [N files, M lines changed]."

**STOP if any Critical issues found.** Report them and stop. Warnings are reported but don't block shipping.

## Step 3: Update Memory Bank

If `.memory-bank/` exists in the project:

1. Read current `.memory-bank/context.md`
2. Review what changed this session via `git diff` and `git log`
3. Update `context.md` with current focus, recent changes, active workstreams
4. If architecture changed → also update `architecture.md`
5. If tech stack changed → also update `tech.md`
6. If tasks changed → also update `task.md`

**Skip this step** if the changes are trivial (typos, formatting-only, config tweaks that don't affect context).

## Step 4: Update Docs

Check if code changes affect any project documentation:

1. Scan for docs that reference changed code — README, API docs, guides, templates, storyboards, style guides, etc.
2. If changes alter behavior, API, architecture, or workflows that are documented → update those docs
3. If no docs are affected → skip this step

Include doc updates in the main code commit (not a separate commit).

## Step 5: Commit

1. Stage all relevant code changes (exclude `.memory-bank/`)
2. Create commit with conventional commit message, or use `$ARGUMENTS` if provided
3. If Memory Bank was updated in step 3:
   - Stage `.memory-bank/` files
   - Create a separate commit: `docs: update memory bank`
4. Show the result: commit hash(es), files changed, summary

## Rules

- Follow the project's existing commit message conventions — check `git log --oneline -5`
- Never commit files that contain secrets (`.env`, credentials)
- Never push to remote — only local commits
- If `$ARGUMENTS` is empty, generate a commit message using conventional commit format (`type(scope): description`) — check `git log --oneline -5` for the project's existing style and match it
- Review is READ-ONLY — do not modify files during review. Fixes happen before `/ship`, not during.
- Always read surrounding context during review, not just the diff lines
- Be specific: cite file:line for every review issue
- Don't flag style nits on code that wasn't changed in this diff
