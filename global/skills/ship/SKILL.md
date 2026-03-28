---
name: ship
description: "Lint, test, review, update Memory Bank, and commit — one command to ship changes."
argument-hint: "[commit-message]"
disable-model-invocation: false
allowed-tools: Bash(git *), Bash(bun *), Bash(npm *), Bash(cargo *), Bash(pytest *), Bash(make *), Bash(gdformat *), Bash(gdlint *), Bash(ruff *), Read, Grep, Glob, Write, Edit
---

# Ship

Pre-flight → Lint/Format → Test → Review → Memory Bank → Docs → Commit.

## Usage

```
/ship [commit message]
```

If no commit message provided, auto-generate one from the changes.

## Failure Behavior

When any step fails, output a structured block and STOP:

```
## Blocked: Step N (Step Name)
- tool: N errors in file.ext
  - L45: specific error message
  - L78: specific error message
- Fix these issues, then run /ship again.
```

Ship is stateless — always restarts from Step 1. No resume, no auto-fix loops.

## Step 1: Pre-flight

Run `git status`. If there are no changes (nothing staged, no modifications, no untracked files), report "Nothing to ship" and stop.

**Safety checks:**
- Detached HEAD (`git symbolic-ref HEAD`) → warn and stop: "Detached HEAD — checkout a branch first."
- Ongoing rebase/merge (check for `.git/MERGE_HEAD`, `.git/rebase-merge/`, `.git/rebase-apply/`) → warn and stop: "Rebase/merge in progress — resolve it first."

**Commit message validation** (if `$ARGUMENTS` provided):
- Validate against conventional commits: `^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?: .+`
- If invalid, show format guide and stop:
  ```
  Invalid commit message format. Expected:
    type(scope): description
  Types: feat fix docs style refactor perf test build ci chore revert
  Examples:
    feat(auth): add JWT token validation
    fix: handle null response from API
  ```

## Step 2: Lint & Format

Auto-detect and run linters/formatters. Fast gate — fail before slow tests.

**Detection order** (check `.claude/CLAUDE.md` or `AGENTS.md` first for project-specific commands):

| Marker             | Commands                                         |
|---------------------|--------------------------------------------------|
| `project.godot`     | `gdformat --check .` then `gdlint .`             |
| `package.json` (lint/format scripts) | `bun run lint` / `bun run format --check` |
| `Cargo.toml`        | `cargo fmt --check` then `cargo clippy -- -D warnings` |
| `pyproject.toml`    | `ruff check .` then `ruff format --check .`      |
| `Makefile` (lint target) | `make lint`                                 |

**Rules:**
- Command not found (exit 127) → skip that tool, not an error
- Non-zero from available tool → STOP with actionable output
- Run all applicable linters for the project type before stopping (collect all errors)

## Step 3: Test

Run the project's test suite.

**Detection order** (check `.claude/CLAUDE.md` or `AGENTS.md` first for project-specific commands):

1. `package.json` with test script → `bun test` or `npm test`
2. `Cargo.toml` → `cargo test`
3. `pyproject.toml` → `pytest`
4. `project.godot` with GUT → look for CLI runner (`gut_cmdln.gd`, test Makefile target, or `test.sh`). No runner found → warn "No GUT CLI runner found", skip.
5. `Makefile` with test target → `make test`
6. No test runner found → warn "No test runner detected", skip to Step 4.

**STOP immediately if tests fail.** Do not continue.

## Step 4: Review

Structured code review of all changes. **READ-ONLY — do not modify files. Fixes happen before `/ship`, not during.**

### Determine what to review

Review all uncommitted changes: `git diff` (unstaged) + `git diff --cached` (staged). If nothing there, review `git diff HEAD~1`.

### Assess diff size

- **Small** (<200 lines): review holistically
- **Large** (200+ lines): review file-by-file, prioritize logic-heavy files (.py, .ts, .gd, .rs) over config/generated files

### Review each change

Read context — don't review the diff in isolation:
- Read the full function around changed lines
- If a function signature changed, grep for callers
- If a test changed, check what it's actually testing

**Checklist** (ordered by AI reliability, best → weakest):

1. **Consistency** — naming conventions, import style, pattern drift from codebase norms, stale comments referencing old behavior
2. **Duplication** — copy-paste code, extractable utilities (grep codebase for similar patterns)
3. **Dead code** — unreachable branches, unused imports/variables, commented-out blocks
4. **Security** — hardcoded secrets, injection (SQL, command, XSS), path traversal, auth gaps. Never commit `.env` or credential files.
5. **Correctness (surface)** — off-by-one, null access, missing error handling, wrong return types
6. **Tests** — new behavior covered? Assertions check the right thing? Edge cases?

Be specific: cite `file:line` for every issue. Don't flag style nits on code that wasn't changed in this diff.

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

**STOP if any Critical issues found.** Warnings are reported but don't block.

## Step 5: Memory Bank

If `.memory-bank/` exists in the project:

**Stale check first:** Run `git status .memory-bank/`. If uncommitted changes exist from a previous session, commit them as `docs: update memory bank` before proceeding.

Then:
1. Read current `.memory-bank/context.md`
2. Review what changed this session via `git diff` and `git log`
3. Update `context.md` with current focus, recent changes, active workstreams
4. If architecture changed → also update `architecture.md`
5. If tech stack changed → also update `tech.md`
6. If tasks changed → also update `task.md`

**Skip this step** if the changes are trivial (typos, formatting-only, config tweaks that don't affect context).

## Step 6: Docs

Check if code changes affect project documentation.

**What counts as docs:**
- **Yes**: README, CHANGELOG, API docs, guides, storyboards, style guides
- **No**: inline comments, docstrings, type annotations (these are code, handled in the commit itself)

Process:
1. Scan for docs that reference changed code
2. If changes alter behavior, API, architecture, or workflows that are documented → update those docs
3. If no docs are affected → skip

Include doc updates in the main code commit (not a separate commit).

## Step 7: Commit

1. Check `git log --oneline -5` for existing commit style
2. Stage all relevant code changes (exclude `.memory-bank/`)
3. Never commit files containing secrets (`.env`, credentials)
4. Never push to remote — only local commits
5. Create commit:
   - Use `$ARGUMENTS` if provided (already validated in Step 1)
   - Otherwise generate conventional commit message (`type(scope): description`) matching project style
6. If Memory Bank was updated in Step 5:
   - Stage `.memory-bank/` files
   - Create a separate commit: `docs: update memory bank`

**Verify success:**
- Run `git log --oneline -1` — confirm hash and message
- Run `git diff --cached` — confirm empty (nothing left staged)

**Output structured summary:**

```
## Shipped
- Commit: `abc1234` feat(auth): add JWT support
- Files: 5 changed (+120, -30)
- Memory Bank: updated / skipped
- Review: LGTM / N warnings
```
