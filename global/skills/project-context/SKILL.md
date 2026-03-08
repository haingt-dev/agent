---
description: "Fetch cross-project context from the agent hub registry. List all projects or get a specific project's identity, goals, and current focus."
argument-hint: "[project-name]"
model: sonnet
disable-model-invocation: true
allowed-tools: Read, Glob
---

# /project-context

Cross-project context loader. Reads from the agent hub registry and target project files.

## Instructions

**Registry path**: `/home/haint/Projects/agent/registry.json`

### Determine mode from arguments

**No argument → List mode**
**Has argument → Fetch mode**

---

### List mode

1. Read `registry.json`
2. Output a table:

```
| Project | Type | Summary |
|---------|------|---------|
| ... | ... | ... |
```

Sort alphabetically. Include all projects.

---

### Fetch mode

1. Read `registry.json`
2. Fuzzy match the argument against project keys:
   - **Priority 1**: Case-insensitive exact match (e.g., "bookie" → "Bookie")
   - **Priority 2**: Case-insensitive prefix match (e.g., "wild" → "Wildtide")
   - **Priority 3**: Case-insensitive substring match (e.g., "chimera" → "chimera-protocol")
3. If no match: say "No project matched '`<arg>`'. Available:" then list project names.
4. If matched, read up to 3 files from the project path:
   - `{path}/.claude/CLAUDE.md` — project identity and conventions
   - `{path}/.memory-bank/brief.md` — goals and scope
   - `{path}/.memory-bank/context.md` — current focus and active work
5. For each file that exists, output its content under a section header (`## CLAUDE.md`, `## brief.md`, `## context.md`). Skip files that don't exist without error.
6. After the content, check if these additional files exist (use Glob):
   - `{path}/.memory-bank/architecture.md`
   - `{path}/.memory-bank/tech.md`
7. If any exist, add a footer:
   ```
   ---
   Also available: `{path}/.memory-bank/architecture.md`, `{path}/.memory-bank/tech.md`
   ```
   Only list files that actually exist.

## Output format

- Use the project's `summary` from registry as a subtitle after the project name
- Keep output clean — no unnecessary commentary
- If a project has no memory-bank files (e.g., agent hub), just show CLAUDE.md and note that memory-bank is sparse
