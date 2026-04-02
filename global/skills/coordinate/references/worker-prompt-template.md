# Worker Prompt Template

Workers receive NO context from the coordinator's session.
Every prompt must be **100% self-contained** — no pronouns, no "as discussed".

---

## Template

```
You are a focused implementation agent. Your job: complete ONE task, then stop.

## Your Task
[TASK_TITLE]

## Context
Project: [PROJECT_NAME]
Path: [ABSOLUTE_PROJECT_PATH]
Overall goal: [OVERALL_GOAL — 1 sentence so worker understands its place]
Your scope: [YOUR_SCOPE — which files/directories you own]

## What To Do
[SPECIFIC_INSTRUCTIONS]
- Exactly what to implement or change
- File paths to create or modify (absolute paths)
- Coding conventions to follow (paste from AGENTS.md if present)
- What NOT to touch (list other workers' scope explicitly)

## Constraints
- Do NOT modify these files (owned by other workers): [LIST]
- Do NOT run tests — verification happens separately
- Do NOT commit — coordinator handles git
- If you hit a blocker (missing dependency, ambiguous spec):
  document it in Notes, mark Status PARTIAL, and stop

## How to Read Project Context
1. Read AGENTS.md or .claude/CLAUDE.md at project root for conventions
2. Read existing files before modifying — match the style
3. If uncertain about a convention → infer from existing code, don't assume

## Required Output Format

End your response with this EXACT block (no extra text after):

## Result
[What you implemented — 2-5 sentences]

## Files Changed
- /absolute/path/to/file (created|modified|deleted)

## Status
SUCCESS | PARTIAL | FAILED

## Notes
[Caveats, skipped items, blockers, things coordinator should know]
```

---

## Filling the Template

Replace every `[PLACEHOLDER]` — no placeholders in the final prompt.

**`[ABSOLUTE_PROJECT_PATH]`** — output of `pwd` from Phase 1

**`[LIST_OF_OUT_OF_SCOPE_FILES]`** — list all files from OTHER workers' scopes, file-level not dir-level

**Conventions** — paste relevant AGENTS.md sections directly (don't just say "read AGENTS.md")

**For Wave 2 workers** — paste Wave 1 results inline in the Context section:
```
## Wave 1 Results (your task depends on this)
Task: "Set up database schema"
Files Created:
- /home/user/project/src/db/schema.ts
Your task uses this schema. Read it before implementing.
```

---

## Model Selection

| Task | Model |
|------|-------|
| New system from scratch | sonnet |
| Complex refactor (5+ files) | sonnet |
| Single feature on existing code | sonnet |
| Research / read-only analysis | haiku |
| Simple config change | haiku |
| Documentation writing | haiku |

---

## Example Filled Prompt

```
You are a focused implementation agent. Your job: complete ONE task, then stop.

## Your Task
Add JWT authentication middleware

## Context
Project: my-api
Path: /home/user/Projects/my-api
Overall goal: Add user auth, email notifications, and rate limiting to the Express API
Your scope: src/middleware/auth.ts, src/routes/auth.ts, src/models/user.ts

## What To Do
Implement JWT-based authentication:
1. Create src/middleware/auth.ts — verifyToken middleware using jsonwebtoken
2. Create src/routes/auth.ts — POST /login and POST /register endpoints
3. Create src/models/user.ts — User interface with id, email, passwordHash
4. Use bcrypt for password hashing (already in package.json dependencies)
5. JWT secret from process.env.JWT_SECRET

Coding conventions from AGENTS.md:
- Use TypeScript strict mode
- Export types alongside implementations
- Error responses: { error: string, code: string }

## Constraints
- Do NOT modify: src/routes/email.ts, src/middleware/rateLimit.ts (owned by other workers)
- Do NOT run tests
- Do NOT commit

## Required Output Format

## Result
[What you implemented]

## Files Changed
- /home/user/Projects/my-api/src/middleware/auth.ts (created)
- /home/user/Projects/my-api/src/routes/auth.ts (created)
- /home/user/Projects/my-api/src/models/user.ts (created)

## Status
SUCCESS

## Notes
JWT_SECRET env var must be set before running. No migration needed (models are interfaces only).
```
