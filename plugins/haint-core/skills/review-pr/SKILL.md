---
name: review-pr
description: Review a pull request for correctness, edge cases, and code quality.
---

# Review PR Workflow

Thorough code review of a pull request.

## Usage

```
/review-pr <pr-number>
```

## Workflow

### 1. Gather context

```bash
gh pr view <pr-number>
gh pr diff <pr-number>
```

Understand:
- What does the PR claim to do? (title, description)
- What issue does it close?
- How large is the diff?

### 2. Review the diff

For each changed file, check:

**Correctness**
- Does the code do what the PR description says?
- Are there off-by-one errors, null/undefined access, or race conditions?
- Are error cases handled?

**Edge cases**
- What happens with empty input, large input, concurrent access?
- Are boundary conditions covered?
- What if dependencies fail?

**Security**
- Injection vulnerabilities (SQL, command, XSS)
- Secrets or credentials in code
- Auth/authz gaps
- Unsafe deserialization

**Code quality**
- Does it follow existing patterns in the codebase?
- Is the naming clear and consistent?
- Are there unnecessary complexity or premature abstractions?
- Is there dead code or debug artifacts?

**Tests**
- Are new/changed behaviors covered by tests?
- Do existing tests still make sense?
- Are test assertions specific enough?

### 3. Summarize findings

Output a structured review:

```markdown
## PR Review: #<number> — <title>

### Summary
<1-2 sentence overview of the changes>

### Issues Found
- **[Critical]** <description> — file:line
- **[Warning]** <description> — file:line
- **[Nit]** <description> — file:line

### Questions
- <anything unclear that needs author clarification>

### Verdict
<APPROVE / REQUEST_CHANGES / NEEDS_DISCUSSION>
```

### 4. Post review (optional)

If the user confirms, post the review as a GitHub PR comment:

```bash
gh pr review <pr-number> --comment --body "<review>"
```

## Notes

- Read the full diff before commenting — avoid premature feedback
- Distinguish severity: Critical (must fix), Warning (should fix), Nit (optional)
- If the PR is too large to review effectively, say so and suggest splitting
- Check CI status: `gh pr checks <pr-number>`
