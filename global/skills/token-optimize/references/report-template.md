# Report Template

This file contains the exact output format for Phase 4, the snapshot schema for Phase 5, and status classification rules. Read this when generating the final report and saving the JSON snapshot.

---

## Phase 4: Report Format

Print this directly to the conversation — do not write to a file.

```
# Token Audit Report — {project_name}
Date: {today}

## Summary
- Model context: {200K | 1M} (detect from model ID suffix: [1m] = 1M, else 200K)
- Always-on baseline: {total}K tokens ({pct}% of context window)
- Status: {HEALTHY | NEEDS ATTENTION | CRITICAL}
  - HEALTHY: ≤ 2.5% of window, 0 critical issues
  - NEEDS ATTENTION: 2.5-5% of window or 1+ warnings
  - CRITICAL: > 5% of window or 1+ critical issues
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

## Controllability

Group always-on costs by who controls them and what action is possible:

| Category | Tokens | % of baseline | Actionable? |
|----------|--------|--------------|-------------|
| User-authored (CLAUDE.md expanded, MEMORY.md, brain files, skill metadata) | {N} | {pct}% | Yes — edit directly |
| MCP structural (deferred tool names + server instructions) | {N} | {pct}% | Partial — add/remove servers |
| Dynamic (hook-injected, SessionStart) | {N} | {pct}% | Yes — modify hook scripts |
| **Total** | **{N}** | | |

Key insight: if MCP structural > 50% of baseline, cutting user-authored content has diminishing returns. Focus on MCP server scoping (move non-essential servers from global to per-project .mcp.json) or runtime discipline (/compact, subagents) instead.

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

## Brain Impact
{Only include if previous snapshot exists. Shows whether brain system is effectively reducing context cost.}

| Metric | Value |
|--------|-------|
| Import compression | {old_expanded - new_expanded} tok saved (what @imports changed between snapshots) |
| MEMORY.md headroom | {N} lines used / 200 cap — {200 - N} lines free (brain absorbs overflow via brain_save) |
| Brain verdict | {EFFECTIVE / NEUTRAL / UNDERUTILIZED — see criteria below} |

Brain verdict criteria:
- **EFFECTIVE**: imports compressed between snapshots (e.g., full profile → core-memory) AND MEMORY.md well under cap (<50% used)
- **NEUTRAL**: no import changes, MEMORY.md stable
- **UNDERUTILIZED**: MEMORY.md near cap (>75%) despite brain available — content should migrate to brain_save

If no previous snapshot exists: "First audit — run again after next optimization cycle to track brain impact."

## Limitations
This audit measures BASELINE costs (static context loaded per session). It does NOT measure:
- Runtime token accumulation from tool call results (MCP responses, file reads)
- Conversation history growth across turns
- Skill body loading when skills are invoked mid-session
- Hook-injected dynamic context (SessionStart brain context injection is estimated at ~300-500 tokens but varies by brain.db content)
- MCP server instruction text is estimated (may be truncated in context) — actual size may vary ±500 tok

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
  "context_window": 200000,
  "baseline_pct": 5.9,
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
    "mcp_instructions": {N},
    "hook_dynamic_estimate": {N}
  },
  "controllability": {
    "user_authored": {N},
    "mcp_structural": {N},
    "dynamic": {N}
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
