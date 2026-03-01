---
name: fix-issue
description: Fix a GitHub issue end-to-end — investigate, implement, test, commit, and open PR.
disable-model-invocation: true
---

# Fix Issue Workflow

Fix a GitHub issue from investigation to PR.

## Usage

```
/fix-issue <issue-number>
```

## Workflow

### 1. Understand the issue

```bash
gh issue view <issue-number>
```

Read the issue title, description, labels, and any linked PRs or discussions. Identify:
- What is broken or missing?
- What is the expected behavior?
- Are there reproduction steps?

### 2. Investigate the codebase

- Use Grep, Glob, and Read to find relevant code
- Trace the execution path related to the issue
- Identify root cause (for bugs) or insertion points (for features)
- Check for existing tests covering this area

### 3. Plan the fix

Before writing code:
- Determine the minimal set of changes needed
- Identify files to modify
- Consider edge cases and potential regressions
- If the fix is non-trivial, outline the approach and confirm with the user

### 4. Implement

- Make the fix with minimal, focused changes
- Follow existing code patterns and conventions
- Do not refactor surrounding code unless directly related to the fix

### 5. Test

- Run existing tests to verify no regressions
- Add or update tests for the fix if the project has a test suite
- Manually verify the fix addresses the issue

### 6. Commit and PR

- Stage only the relevant files
- Write a commit message referencing the issue: `fix: <description> (#<issue-number>)`
- Create a PR with:
  - Title: concise description of the fix
  - Body: what was wrong, what was changed, how to test
  - Reference: `Closes #<issue-number>`

## Notes

- If the issue is unclear or lacks reproduction steps, ask the user for clarification before implementing
- If multiple approaches exist, present options with trade-offs and let the user decide
- If the fix requires breaking changes, flag this explicitly
