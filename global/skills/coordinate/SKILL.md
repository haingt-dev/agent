---
name: coordinate
description: "Parallel agent orchestrator — spawn workers, collect results, verify. Use for multi-task goals (3+ workstreams)."
argument-hint: "[goal description]"
model: sonnet
allowed-tools: >
  Read, Glob, Grep, Edit,
  Bash(git *), Bash(ls *), Bash(find *), Bash(cat *),
  Bash(cargo *), Bash(pytest *), Bash(bun *), Bash(npm *), Bash(make *),
  AskUserQuestion,
  mcp__haingt-brain__brain_recall,
  mcp__haingt-brain__brain_save,
  Agent
---

# Coordinate — Parallel Agent Orchestrator

Keep the main context clean. Spawn workers, collect results, verify.

**Why this exists**: Sequential implementation consumes the entire context window. Coordinator stays at bird's-eye view — workers do dirty work in isolated worktrees. Based on Claude Code's verified coordinator architecture.

## Usage

```
/coordinate implement user auth, email notifications, and rate limiting
/coordinate refactor these 5 modules to use the new API
/coordinate [any goal with 2-6 independent workstreams]
```

## Coordinator Rules (HARD)

- **NO file creation/editing** — coordinator never uses Write/Bash(echo) to implement
- Edit is only allowed for **conflict merging** (two workers touched the same file)
- **Plan → Approve → Spawn → Collect → Verify** — never skip steps, never reorder
- **Verification is NOT optional** — skill does not complete without Phase 4
- **Partial failure is a result, not a blocker** — record failures, verify what succeeded

---

## Phase 1: Research

### Step 1.1: Brain Recall

```
brain_recall(
  query="coordinate orchestrate parallel agents pattern",
  type="pattern",
  project=[cwd basename under ~/Projects/],
  time_range="-90 days",
  k=5
)
```

If results found: note relevant constraints (file conflict hotspots, past failures).

### Step 1.2: Understand the Goal

Parse `$ARGUMENTS`. If empty → `AskUserQuestion`: "What goal do you want to coordinate?"

Read the project:
- `git status` — warn if dirty (uncommitted changes before workers start)
- Detect project type and test runner:

| Marker | Test command |
|--------|-------------|
| `Cargo.toml` | `cargo test` |
| `pyproject.toml` | `pytest` |
| `package.json` (test script) | `bun test` or `npm test` |
| `project.godot` + GUT runner | GUT CLI command |
| `Makefile` (test target) | `make test` |
| None | warn "No test runner detected" — verification will be manual |

Store as `TEST_COMMAND` for Phase 4.

- Read `AGENTS.md` or `.claude/CLAUDE.md` if present — project conventions
- `git log --oneline -5` — recent context

---

## Phase 2: Synthesis (Decompose)

### Step 2.1: Decompose the Goal

Break into **2–6 independent tasks**. Independence criteria:
- Tasks touch **different files** (no shared writes)
- Tasks can succeed/fail in any order
- Tasks do **not** depend on each other's output

If dependencies exist → propose **multi-wave plan** (Wave 1 workers → coordinator collects → Wave 2 workers), with explicit wave boundaries.

Per task determine:
- **Title**: short label
- **Scope**: which files/dirs this task owns
- **Complexity**: `high` (new system, complex logic) → sonnet | `low` (research, simple edits) → haiku
- **Risk**: does this touch shared utilities or config?

Prefer **one task per distinct user-requested feature** — don't collapse multiple requested items into one task unless they share >80% of their file scope.

### Step 2.2: Approval Gate

```
## Coordination Plan: [Goal]

### Tasks (parallel)
| # | Title | Scope | Model | Risk |
|---|-------|-------|-------|------|
| 1 | [title] | [files/dirs] | sonnet | low/med/high |
...

### Verification
`[TEST_COMMAND]`

### Potential Conflicts
[Files appearing in 2+ tasks — coordinator merges manually]
```

Use `AskUserQuestion`:
- **Approve all** — spawn as planned
- **Approve with changes** — edit plan, regenerate
- **Cancel** — abort

**DO NOT proceed until approved.**

---

## Phase 3: Implementation

### Step 3.1: Spawn Workers (All in Same Turn)

Read `~/.claude/skills/coordinate/references/worker-prompt-template.md` first — it defines the worker prompt structure.

Spawn **all agents in the same turn** (one message, multiple Agent calls). Never batch across turns — that defeats context isolation.

Per agent call:
```
Agent(
  description: "[3-5 word task summary]",
  prompt: [fully self-contained worker prompt per template],
  model: "sonnet" | "haiku",   // per task complexity
  isolation: "worktree"         // git worktree isolation — no cross-agent file conflicts
)
```

Model selection:
- New systems, complex logic, refactors → sonnet
- Research, read-only, simple single-file edits, docs → haiku

### Step 3.2: Collect Results

As agents complete, read their output. Each worker must end with:

```
## Result
[What was done — 2-5 sentences]

## Files Changed
- /absolute/path/to/file (created|modified|deleted)

## Status
SUCCESS | PARTIAL | FAILED

## Notes
[Caveats, skipped items, blockers]
```

If a worker returns without this block → treat as PARTIAL.

### Step 3.3: Verification Nudge

After collecting **3 or more** worker results, check: have any tests run yet?

If NO:
```
⚠ Tests not run. Verification required before proceeding.
```

### Step 3.4: Conflict Detection

Compare file lists across all Results. If any file appears in 2+ workers' "Files Changed":
1. Read both versions
2. Merge using coordinator's Edit tool (the one exception to the no-edit rule)
3. Note the merge in the final report

---

## Phase 4: Verification (MANDATORY)

**The skill does not complete without this phase.**

### Step 4.1: Run Tests

```bash
[TEST_COMMAND]
```

Capture exit code and output.

### Step 4.2: Evaluate

| Outcome | Action |
|---------|--------|
| All tests pass | Mark SUCCESS, proceed to brain save |
| Some tests fail | Identify failing tests, check if in workers' scope |
| No runner found | Read changed files for syntax errors, import issues, obvious regressions |
| Worker(s) FAILED | Verify successful tasks independently; report `N/M tasks succeeded` |

---

## Phase 5: Brain Save + Report

```
brain_save(
  content: "Coordinate [project]: [goal summary]. N tasks, M succeeded. Waves: Y/N. Test: passed|failed|skipped. [1-line insight]"
  type: "pattern"
  tags: ["coordinate", "orchestration", "[project]"]
  project: [cwd basename]
  metadata: {"source": "coordinate", "task_count": N, "success_count": M, "waves": bool, "test": "passed|failed|skipped"}
)
```

Final report:

```
## Coordination Complete: [Goal]

### Results
| Task | Status | Files Changed |
|------|--------|---------------|
| [title] | SUCCESS/PARTIAL/FAILED | N files |

### Verification
[TEST_COMMAND output — pass/fail summary]

### Conflicts Resolved
[List merged files, or "None"]

### Failed Tasks
[title — reason — recommended follow-up]

### Pattern Saved
brain: "[summary]"
```
