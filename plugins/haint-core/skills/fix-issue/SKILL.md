---
name: fix-issue
description: Fix a GitHub issue end-to-end — investigate, reproduce, implement, test, commit, and open PR. Use when the user provides a GitHub issue number or URL, or asks to fix a bug referencing an issue tracker.
argument-hint: "[issue-number-or-url]"
---

# Fix Issue Workflow

Fix a GitHub issue from investigation to PR.

## Usage

```
/fix-issue <issue-number-or-url>
```

## Workflow

### 1. Understand the issue

```bash
gh issue view <issue-number>
```

Read the full issue including comments. Extract:
- **Symptom**: What the user observes happening (or not happening)
- **Expected behavior**: What should happen instead
- **Reproduction steps**: If provided. If not, note this — you'll need to figure them out.
- **Environment context**: Versions, OS, configuration that might matter

If the issue is vague (e.g., "X doesn't work sometimes"), don't guess at the fix. Read the code first, form a hypothesis about what could cause the described behavior, then confirm it.

### 2. Reproduce the bug

Before touching any code, confirm the bug exists:
- If there are reproduction steps, follow them
- If not, write a minimal script or test that demonstrates the failure
- If you can't reproduce it, tell the user what you tried and ask for more context

This step prevents fixing the wrong thing. A bug you can't reproduce is a bug you can't verify you fixed.

### 3. Investigate the codebase

Start from the symptom and trace backward to the root cause:

1. **Find the entry point** — where does the failing behavior start? (API endpoint, CLI command, function call from the reproduction)
2. **Trace the execution path** — follow the code through the relevant functions, noting where assumptions are made
3. **Identify the root cause** — the actual line(s) where wrong behavior originates, not just where the symptom surfaces
4. **Check for related callers** — search for other code that calls the buggy function. Changes here might break them.

```
# Find who else uses the function you're about to change
Grep for the function name across the codebase
```

5. **Check existing test coverage** — are there tests for this area? Do they pass currently? A test that should catch this bug but doesn't might itself be wrong.

### 4. Plan the fix

**Quick fixes** (single file, obvious root cause, clear reproduction, existing tests cover it): just fix it.

**Non-trivial fixes** — outline the approach first when any of these apply:
- Changes span 3+ files
- The fix could change behavior for other callers of the same code
- Multiple valid approaches exist with different trade-offs
- The root cause is ambiguous (could be A or B)
- The fix involves a public API or data format change

For non-trivial fixes, briefly describe: what you'll change, why this approach over alternatives, and what could break.

### 5. Implement

- Fix the root cause, not the symptom
- Follow existing code patterns and conventions
- Don't refactor surrounding code unless directly related to the fix
- If you find other bugs nearby, note them but don't fix them in this PR (unless trivially related)

### 6. Test the fix

**Verify the fix works:**
- Run your reproduction from step 2 again — it should now pass
- Run the full test suite (or relevant subset) to catch regressions

**Add test coverage when:**
- The bug had no test covering it (most common case — that's why the bug existed)
- Existing tests passed despite the bug (the tests were insufficient)

Test the specific scenario that was broken, plus edge cases you identified during investigation. Match the existing test style and framework.

### 7. Check blast radius

Before committing, verify your changes don't break dependent code:
- If you changed a shared utility/library function, check all callers still work
- If you changed a data format, check consumers
- If you changed an API, check clients
- Run linting if the project has it configured

### 8. Commit and PR

- Stage only the relevant files
- Commit message: `fix: <description> (#<issue-number>)`
- Create a PR:
  - Title: concise description of the fix
  - Body: root cause, what was changed, how to verify
  - Reference: `Closes #<issue-number>`
