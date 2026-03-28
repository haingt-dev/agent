# Report Template

This file contains the exact output format for Phase 4, the snapshot schema for Phase 5, and status classification rules. Read this when generating the final report and saving the JSON snapshot.

---

## Phase 4: Report Format

Print this directly to the conversation — do not write to a file.

```
# Token Audit Report — {project_name}
Date: {today}

## Summary
- Always-on baseline: {total}K tokens (target: ≤30K)
- Status: {HEALTHY | NEEDS ATTENTION | CRITICAL}
  - HEALTHY: ≤25K tokens, 0 critical issues
  - NEEDS ATTENTION: 25-35K tokens or 1+ warnings
  - CRITICAL: >35K tokens or 1+ critical issues
- Issues: {n_critical} critical, {n_warn} warnings, {n_info} info

## Context Breakdown
| Source | Lines | Chars | ~Tokens | Category | Status |
|--------|-------|-------|---------|----------|--------|
| {path} | {n} | {n} | {n} | always-on | ✅/⚠️/❌ |
|   ↳ @core-memory.md | {n} | {n} | {n} | @import | |
|   ↳ @brains/{name}.md | {n} | {n} | {n} | @import | |
| ... | | | | | |
| **Total always-on** | | | **{n}** | | |
| Hook dynamic (est.) | — | — | ~{n} | dynamic | ℹ️ |

## Issues Found

### ❌ Critical
{Each issue with: what's wrong, why it matters (cite source), estimated token waste}

### ⚠️ Warnings
{Same format}

### ℹ️ Info
{Same format}

## Recommendations
{Prioritized list. Each item:}
1. **{Action}** — {Why, with evidence}. Saves ~{N}K tokens. Effort: {quick|medium|significant}.

## Comparison
{If token-audit.json exists from a previous run, show the delta table here}

## Limitations
This audit measures BASELINE costs (static context loaded per session). It does NOT measure:
- Runtime token accumulation from tool call results (MCP responses, file reads)
- Conversation history growth across turns
- Skill body loading when skills are invoked mid-session
- Hook-injected dynamic context (SessionStart brain context injection is estimated at ~300-500 tokens but varies by brain.db content)

For long sessions, runtime costs typically dwarf baseline. Mitigations: `/compact` regularly, `/clear` between unrelated tasks, delegate heavy exploration to subagents.
```

### Comparison table format

When a previous `token-audit.json` exists, include a delta table in the Comparison section:

```
## Comparison (vs {previous_date})
| Source | Previous | Current | Delta |
|--------|----------|---------|-------|
| global_claude_md | {N} tok | {N} tok | {+/-N} |
| memory_md | {N} tok | {N} tok | {+/-N} |
| ... | | | |
| **Total** | **{N}** | **{N}** | **{+/-N}** |
```

### Recommendation structure

Each recommendation must include:
- **Action** (imperative verb: Remove, Move, Split, Add, Trim)
- **Why**, with evidence (cite the specific duplication, benchmark exceeded, or waste pattern found)
- **Estimated savings** in tokens or percentage
- **Effort level**: quick (< 15 min), medium (< 1 hour), significant (> 1 hour)

Example:
> 1. **Move deployment workflow to a skill** — 47-line step-by-step procedure in CLAUDE.md is always-on. As a skill, it loads only when invoked (~100 tokens metadata vs ~1,400 tokens always-on). Saves ~1.3K tokens. Effort: quick.

---

## Phase 5: Snapshot Schema

Determine the project memory directory — it's under `~/.claude/projects/` with the path derived from the working directory (replace `/` with `-`, strip leading `-`). Write `token-audit.json` there.

```json
{
  "date": "{YYYY-MM-DD}",
  "project": "{project_name}",
  "total_always_on_tokens": {N},
  "breakdown": {
    "global_claude_md_raw": {N},
    "global_claude_md_expanded": {N},
    "global_claude_md_imports": ["path1", "path2"],
    "project_claude_md_raw": {N},
    "project_claude_md_expanded": {N},
    "project_claude_md_imports": ["path1"],
    "agents_md": {N},
    "memory_md": {N},
    "memory_bank": {N},
    "brain_files": {N},
    "brain_files_count": {N},
    "core_memory": {N},
    "skill_descriptions": {N},
    "mcp_deferred": {N},
    "mcp_deferred_tool_count": {N},
    "hook_dynamic_estimate": {N}
  },
  "issues": {
    "critical": {N},
    "warning": {N},
    "info": {N}
  },
  "status": "{HEALTHY|NEEDS_ATTENTION|CRITICAL}"
}
```

If a previous `token-audit.json` exists, read it first and include the comparison in Phase 4's report showing what changed since the last audit.
