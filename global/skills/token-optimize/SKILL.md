---
name: token-optimize
description: >-
  Audit Claude Code token consumption across project and global context.
  Measures all context sources, benchmarks against official limits, detects
  duplication and waste patterns, produces actionable recommendations with
  quantified savings. Use this skill whenever the user mentions token costs,
  context size, wants to optimize their Claude Code setup, or complains about
  expensive sessions. Triggers: "token optimize", "audit tokens", "context
  audit", "optimize context", "reduce tokens", "token usage".
---

# Token Optimize

Audit Claude Code token consumption and produce an evidence-based optimization report. This skill is read-only — it measures and recommends but never modifies files.

## Why This Matters

Claude Code's context window (200K tokens) fills fast. The built-in system prompt (instructions, tool schemas, environment info) consumes a fixed overhead before you type anything — this is uncontrollable. On top of that, user-controlled context layers stack: CLAUDE.md, memory files, skill descriptions, and MCP tool definitions. Performance degrades noticeably in the last 20% of the window — so the goal isn't just cost savings, it's quality preservation.

Two types of token cost matter:
- **Baseline** (static): Always-on files + MCP tool definitions. Fixed per session. This is what this audit measures.
- **Runtime** (dynamic): Tool call results (Todoist returning 50 tasks, Gmail listing threads), file reads, conversation history. These accumulate per-turn and can dwarf baseline costs in long sessions. This audit does NOT measure runtime costs — note this in the report so users don't get a false sense of security from a low baseline number.

The good news: most baseline waste is controllable. Community data shows 40-80% reduction is achievable with systematic optimization. Runtime costs are best managed with `/compact`, `/clear`, and subagent delegation.

## Execution

Work through these 5 phases in order. Use Read, Glob, and Grep tools only — never modify files.

### Phase 1: Measure

Scan every context source. For each file, record: path, line count, char count, estimated tokens (chars / 3.5).

Categorize each source:

**Always-on** (loaded every session automatically):

1. `~/.claude/CLAUDE.md` — Global instructions. **Important: resolve `@import` directives** (see below).
2. Project CLAUDE.md — Check both `.claude/CLAUDE.md` and root `CLAUDE.md`. Also resolve `@import` directives.
3. `AGENTS.md` — If exists at project root
4. Auto-memory — Find the project's memory directory under `~/.claude/projects/` and read `MEMORY.md`. The project hash is derived from the working directory path (replace `/` with `-`, strip leading `-`).
5. Memory bank — Glob `.memory-bank/*.md` at project root. These load if a startup hook reads them (check `.claude/settings.json` and `.claude/settings.local.json` for `SessionStart` hooks).
6. Skill descriptions — Glob `.claude/skills/*/SKILL.md`. Read only the YAML frontmatter (between `---` markers). Extract the `description` field and measure its length. Count total skills.
7. Plugin skills — Check `enabledPlugins` in `~/.claude/settings.json`. For each enabled plugin, note it contributes skill descriptions to the always-on context.

**Resolving `@import` directives in CLAUDE.md files:**

CLAUDE.md files can contain `@path/to/file` directives that pull external files into context at session start. These are expanded recursively (max depth 5). The raw CLAUDE.md line count is misleading — the ACTUAL context cost is the expanded content.

For each CLAUDE.md file:
1. Grep for lines matching `^@` (import directives)
2. For each `@path` found, resolve the path (expand `~` to home dir) and Read the target file
3. Record: import path, target file lines, target file chars, estimated tokens
4. Report both raw CLAUDE.md size AND expanded size (raw + all imports)
5. Use the **expanded** size for all benchmarks and thresholds — that's what Claude actually sees
6. In the Context Breakdown table, show each import as a sub-row indented under its parent CLAUDE.md
7. Watch for circular imports or missing files (broken `@path` references)

Example: a 87-line CLAUDE.md with 4 `@import` directives might expand to 330+ lines — the expanded number is what matters for benchmarking.

**On-demand** (loaded only when needed):

8. `.claude/rules/*.md` — Path-scoped rules. These only load when Claude touches files matching their path patterns. Measure but categorize as on-demand.
9. Skill bodies — The full SKILL.md content beyond frontmatter. Loaded only when a skill is invoked.

**Settings** (affect context indirectly):

10. `~/.claude/settings.json` — Count: permission allow rules, deny rules, ask rules, MCP server wildcards (`mcp__*` patterns), additional directories, enabled plugins
11. `.claude/settings.local.json` — Same analysis for project-local overrides
12. `.mcp.json` — Count MCP server definitions at project level
13. `.claudeignore` — Check if it exists. If the project has `node_modules/`, `dist/`, `build/`, or `target/` directories but no `.claudeignore`, flag it.

### Phase 2: Benchmark

Compare measurements against these official limits. For each check, assign a status:
- PASS: Within limit
- WARN: Approaching limit (>75% of threshold)
- FAIL: Exceeds limit

**Benchmarks with sources:**

| Check | Threshold | Why |
|-------|-----------|-----|
| Each CLAUDE.md file (raw) | ≤ 200 lines | Official recommendation. Beyond this, rule adherence degrades — "if Claude keeps ignoring a rule, the file is probably too long." (code.claude.com/docs/en/memory) |
| Each CLAUDE.md file (expanded, with @imports) | ≤ 500 lines | After resolving `@path` imports, the expanded content is what Claude actually sees. Files with heavy @imports may appear small but load hundreds of lines. Report both raw and expanded. |
| MEMORY.md | ≤ 200 lines | Hard cutoff — only first 200 lines auto-load at session start. Content beyond line 200 is invisible unless explicitly read. (code.claude.com/docs/en/memory) |
| MCP servers (global + project) | ≤ 3 total | Each server adds tools to the deferred list (~50 tok/tool baseline). When tools are loaded via ToolSearch, full schemas add ~200-400 tok/tool. 13 servers documented at 82K tokens loaded (41% of window). (github.com/anthropics/claude-code/issues/3406) |
| User-controlled always-on | ≤ 12K tokens | Separate from the fixed system prompt. User-controlled context (CLAUDE.md + memory + skill descriptions + MCP definitions) should leave 150K+ working space. A baseline of 24% window usage is acceptable for short/medium sessions — the real problem is accumulation: each turn adds conversation history, tool results, and file reads on top. |
| All skill descriptions combined | ≤ 16,000 chars | Fallback budget for skill metadata. Beyond this, descriptions compete for context space. (code.claude.com/docs/en/skills) |
| Largest always-on file | ≤ 100 lines | Files over 100 lines in always-on context likely contain content that should be in skills (on-demand ~100 tokens) or rules (path-scoped). |
| .claudeignore exists | Yes, if project has build dirs | Prevents Claude from reading large generated files (node_modules, lock files, bundles). A single package-lock.json can be 30-80K tokens. 50-70% savings documented. |
| Additional directories | 0-2 entries | Each adds scanning scope. Stale entries (old project paths, system dirs like /dev) waste context. |

### Phase 3: Detect

Cross-reference the measured data for specific waste patterns:

**3a. Duplication across layers**

Read the content of all always-on files (including @import-expanded content). Look for the same information appearing in multiple places — for example:
- Pipeline commands in both MEMORY.md and architecture docs
- Tool gotchas in both tech docs and MEMORY.md
- Project description in both CLAUDE.md and AGENTS.md and brief.md
- **@import overlap**: A file imported via `@path` in global CLAUDE.md that is ALSO loaded as project-level auto-memory (e.g., a memory file imported globally AND loaded by the project's MEMORY.md system). This is double-loading — the same content appears twice in context.
- **Cross-layer import overlap**: Profile files imported into CLAUDE.md that duplicate summaries already written inline in the same file or in MEMORY.md

For each duplication found, note which files contain it and recommend keeping it in exactly one canonical location.

**3b. Stale content**

Scan always-on files for signs of outdated content:
- Date patterns (YYYY-MM-DD) older than 30 days in changelog/history sections
- "Done", "Completed", "Resolved", "Shipped" markers in task lists
- "Recent Changes" sections with entries all older than 2 weeks
- Version numbers that might be outdated
- References to files or directories that no longer exist (use Glob to verify)

**3c. Redundant permissions**

Parse the `allow` arrays in settings files. Check for redundancy:
- Global `Bash(*)` makes every `Bash(specific:*)` in project settings redundant
- Global `WebFetch` (no domain) makes every `WebFetch(domain:X)` redundant
- Global `Read` makes every `Read(path)` redundant
- Duplicate MCP server patterns (e.g., `mcp__server__*` in both global and local)

Count total redundant rules. Each is small individually, but 50+ redundant rules in one project has been observed.

**3d. Over-specified CLAUDE.md**

Scan CLAUDE.md content for patterns that indicate material belongs elsewhere:
- Step-by-step workflows (>10 sequential steps) → should be a skill (~100 tokens metadata vs thousands always-on)
- File-specific instructions ("when editing X, do Y") → should be `.claude/rules/` (path-scoped, loads on-demand)
- Setup/install instructions → one-time knowledge, shouldn't be always-on
- Long code examples or templates → should be in skill's bundled resources

Skills are 150x more efficient than CLAUDE.md for specialized instructions: ~100 tokens per skill metadata vs 15K+ if inlined into CLAUDE.md. (Source: Skills docs, ClaudeFast metrics)

**3e. MCP overhead analysis**

MCP costs fall into three distinct tiers. Use these exact definitions for reproducible measurements:

| Tier | What | Counted in baseline? | How to measure |
|------|------|---------------------|----------------|
| **MCP_DEFERRED** | Tool names in `<available-deferred-tools>` list | YES — always present | ~50 tokens per tool (name only, no schema). Count tools per server from the deferred list. |
| **MCP_LOADED** | Full tool schemas loaded via ToolSearch | NO — on-demand | ~200-400 tokens per tool (name + parameter schema). Only present after explicit ToolSearch invocation. Report separately as "on-demand MCP cost." |
| **MCP_RUNTIME** | Tool call results (API responses) | NO — never count | Varies wildly (50 tokens to 5K+ per call). Not measurable statically. Mention in Limitations section only. |

For each MCP server found in settings:
- Count its tools in the deferred-tools list → multiply by ~50 tokens = **MCP_DEFERRED cost** (this is the baseline number to report)
- Check if it has corresponding `mcp__servername__*` allow rules (suggests active use)
- Note servers with no allow rules (possibly unused — loaded but never permitted)
- Flag duplicate server names (e.g., `notebooklm` AND `notebooklm-mcp`)

In the Context Breakdown table, report MCP as: `MCP deferred ({N} tools × ~50 tok)`. Do NOT estimate loaded schema costs as baseline — they are on-demand.

**3e2. Skill body analysis (on-demand but high-impact)**

Scan skill bodies (full SKILL.md content) for waste patterns. These are on-demand, but large skills consume significant tokens when invoked:
- Skills > 300 lines or > 10K chars — flag as oversized, suggest splitting or externalizing examples into `references/` files
- Orchestrator skills that duplicate content from sub-skills (e.g., a "produce" skill that re-describes steps already in "extract", "write", "generate" skills) — should be thin orchestrators with skill references, not content duplication
- Hardcoded values that may go stale (style descriptions, API URLs, version numbers) — suggest reading from canonical source files instead

**3f. Missing optimizations**

Check for optimization opportunities not yet used:
- No `.claudeignore` but project has `node_modules/`, `dist/`, `build/`, `target/`, `__pycache__/` directories
- No `.claude/rules/` directory despite CLAUDE.md > 100 lines
- Skills without `disable-model-invocation: true` that appear to be manual-only (invoked by user, not auto-triggered). Note: this flag blocks Claude's Skill tool invocation entirely — orchestrator skills that call sub-skills via Skill tool will break. Only safe for skills invoked exclusively by user slash commands.
- `additionalDirectories` with entries pointing to non-existent paths or system dirs
- No use of Tool Search env var despite many MCP tools

**3g. Cache-hostile patterns**

Prompt caching saves 80-90% on repeated context (cache reads = 0.1× input cost). But the cache invalidates when tools, MCP servers, or model change mid-session — causing a 5× cost spike as the full prefix is reprocessed. Flag:
- Multiple MCP server configs that might change between sessions
- Settings that suggest frequent model switching

### Phase 4: Report

Present findings as a structured report. Print this directly — don't write to a file.

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
| ... | | | | | |
| **Total always-on** | | | **{n}** | | |

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
{If token-audit.json exists from a previous run, show the delta}

## Limitations
This audit measures BASELINE costs (static context loaded per session). It does NOT measure:
- Runtime token accumulation from tool call results (MCP responses, file reads)
- Conversation history growth across turns
- Skill body loading when skills are invoked mid-session

For long sessions, runtime costs typically dwarf baseline. Mitigations: `/compact` regularly, `/clear` between unrelated tasks, delegate heavy exploration to subagents.
```

### Phase 5: Save Snapshot

After printing the report, save a machine-readable snapshot for future comparison.

Determine the project memory directory — it's under `~/.claude/projects/` with the path derived from the working directory. Write `token-audit.json` there:

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
    "skill_descriptions": {N},
    "mcp_deferred": {N}
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
