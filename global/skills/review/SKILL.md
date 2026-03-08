---
name: review
description: "Review staged changes or recent commits for bugs, security issues, and style."
argument-hint: "[HEAD~N|branch|hash]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git diff *), Bash(git log *), Bash(git show *), Bash(git rev-parse *)
---

# Review — Pre-commit Code Review

Review staged changes (or recent commits) for correctness, security, and style.

## Usage

```
/review                    → review staged changes (or HEAD~1 if nothing staged)
/review HEAD~3             → review last 3 commits
/review feature-branch     → review changes vs current branch
```

## Step 1: Determine What to Review

Parse `$ARGUMENTS`:
- No args → `git diff --cached` (staged). If nothing staged → `git diff HEAD~1`
- `HEAD~N` → `git diff HEAD~N..HEAD`
- Branch name → `git diff <branch>..HEAD`
- Commit hash → `git show <hash>`

If there's nothing to review (empty diff), say so and stop.

## Step 2: Assess Diff Size

```bash
git diff --cached --stat  # or appropriate variant
```

- **Small** (<200 lines): review holistically
- **Large** (200+ lines): review file-by-file, prioritize logic-heavy files (.py, .ts, .gd, .rs) over config/generated files

## Step 3: Review Each Change

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

## Step 4: Output Review

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

## Rules

- READ-ONLY — do NOT modify any files
- Always read surrounding context, not just the diff lines
- Be specific: cite file:line for every issue
- Don't flag style nits on code that wasn't changed in this diff
- If reviewing a large diff, mention files you skipped and why
