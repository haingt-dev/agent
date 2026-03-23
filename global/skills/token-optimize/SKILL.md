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

## Key Limits & Benchmarks

| Check | Threshold |
|-------|-----------|
| Each CLAUDE.md (raw) | ≤ 200 lines |
| Each CLAUDE.md (expanded with @imports) | ≤ 500 lines |
| MEMORY.md | ≤ 200 lines (hard cutoff — content beyond line 200 is invisible) |
| MCP servers total (global + project) | ≤ 3 |
| User-controlled always-on | ≤ 12K tokens |
| All skill descriptions combined | ≤ 16,000 chars |
| Largest always-on file | ≤ 100 lines |
| .claudeignore | Required if project has build dirs |
| Additional directories | 0–2 entries |

Status thresholds for the Summary line:
- **HEALTHY**: ≤ 25K tokens always-on, 0 critical issues
- **NEEDS ATTENTION**: 25–35K tokens or 1+ warnings
- **CRITICAL**: > 35K tokens or 1+ critical issues

## Execution

Work through these 5 phases in order. Use Read, Glob, and Grep tools only — never modify files.

### Phase 1: Measure

Scan every context source. For each file: path, line count, char count, estimated tokens (chars / 3.5).

Categories: **always-on** (global CLAUDE.md, project CLAUDE.md, AGENTS.md, auto-memory MEMORY.md, memory-bank .md files, skill descriptions frontmatter, plugin skills), **on-demand** (.claude/rules/*.md, skill bodies), **settings** (settings.json, settings.local.json, .mcp.json, .claudeignore).

Critical: resolve all `@import` directives in CLAUDE.md files — grep for `^@` lines, read each target file, record expanded size. Use expanded size for all benchmarks. Show imports as indented sub-rows in the Context Breakdown table.

For MCP overhead, use the three-tier model (MCP_DEFERRED / MCP_LOADED / MCP_RUNTIME). Only MCP_DEFERRED (~50 tokens per tool name) counts toward baseline.

→ Full scanning procedure and @import resolution steps: `references/measurement-guide.md`

### Phase 2: Benchmark

Compare each measurement against the thresholds above. Assign PASS / WARN (>75% of threshold) / FAIL for each check.

→ Full threshold table with sources and rationale: `references/measurement-guide.md`

### Phase 3: Detect

Cross-reference measured data for waste patterns:

- **3a. Duplication** — same content in multiple always-on files (including @import overlap and cross-layer overlap)
- **3b. Stale content** — dates >30 days old in changelogs, "Done/Completed" markers, broken file references
- **3c. Redundant permissions** — global wildcards making project-level rules redundant
- **3d. Over-specified CLAUDE.md** — step-by-step workflows, file-specific instructions, setup docs, code templates that belong in skills or rules
- **3e. MCP overhead** — unused servers (no allow rules), duplicate server names, deferred tool count
- **3e2. Skill body waste** — skills >300 lines (recommend progressive disclosure refactoring), orchestrators that duplicate sub-skill content, hardcoded values that go stale
- **3f. Missing optimizations** — no .claudeignore despite build dirs, no rules/ dir despite large CLAUDE.md, stale additionalDirectories
- **3g. Cache-hostile patterns** — MCP configs or model switching that invalidates prompt cache mid-session

→ Full detection criteria and issue taxonomy (Critical/Warning/Info): `references/measurement-guide.md`

### Phase 4: Report

Present findings as a structured report printed directly to the conversation (never written to a file). Include: Summary with status, Context Breakdown table, Issues Found (Critical / Warnings / Info), Recommendations (prioritized, with savings estimates and effort level), Comparison (if previous snapshot exists), and Limitations.

→ Exact output format, comparison table structure, recommendation template, and example output: `references/report-template.md`

### Phase 5: Save Snapshot

After printing the report, write `token-audit.json` to the project's memory directory under `~/.claude/projects/` (path derived from working directory: replace `/` with `-`, strip leading `-`).

If a previous snapshot exists, read it first and include the delta in Phase 4's Comparison section.

→ Full JSON schema: `references/report-template.md`
