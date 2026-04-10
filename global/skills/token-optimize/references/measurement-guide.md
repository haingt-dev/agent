# Measurement Guide

This file contains detailed measurement steps for each phase of the token audit, including how to scan each context source, the `@import` resolution process, the full issue taxonomy, and the MCP overhead tiers. Read this during Phase 1–3 execution.

---

## Phase 1: Measure — Context Sources

For each file, record: path, line count, char count, estimated tokens (chars / 3.5).

### Always-on sources (loaded every session)

1. `~/.claude/CLAUDE.md` — Global instructions. Resolve `@import` directives (see below).
2. Project CLAUDE.md — Check both `.claude/CLAUDE.md` and root `CLAUDE.md`. Also resolve `@import` directives.
3. `AGENTS.md` — If exists at project root.
4. Auto-memory — Find the project's memory directory under `~/.claude/projects/` with the path derived from the working directory (replace `/` with `-`, strip leading `-`). Read `MEMORY.md`.
5. Memory bank — Glob `.memory-bank/*.md` at project root. These load if a startup hook reads them — check `.claude/settings.json` and `.claude/settings.local.json` for `SessionStart` hooks.
6. Brain files — Glob `~/.claude/brains/*.md`. For each: path, lines, chars, tokens. Note which project CLAUDE.md files @import each brain file (grep for `@~/.claude/brains/` across all CLAUDE.md files). These are always-on for every project that @imports them.
7. Skill descriptions — Glob `.claude/skills/*/SKILL.md`. Read only the YAML frontmatter (between `---` markers). Extract the `description` field and measure its length. Count total skills. Note: with brain_tools Semantic Toolbox, descriptions can be minimal labels (~20-50 chars) — verbose descriptions are waste.
8. Plugin skills — Check `enabledPlugins` in `~/.claude/settings.json`. Each enabled plugin contributes skill descriptions to always-on context. Scan plugin skill paths: `~/Projects/agent/plugins/*/skills/*/SKILL.md`.
9. Hook dynamic context (estimated) — Two layers: (a) SessionStart (brain-context.py): read script to check pattern. L0+L1 hard-cap = ~50 tok. Pre-L0/L1 pattern (injects recent decisions + preferences) = ~300-500 tok. (b) UserPromptSubmit (prompt-context.py): check for trivial-prompt gate and toolbox removal — see 3i.2 in Phase 3. Category: "dynamic (estimated)" — not statically measurable but impacts token budget per session/prompt.

### Resolving `@import` directives

CLAUDE.md files can contain `@path/to/file` directives that pull external files into context at session start. These expand recursively (max depth 5). The raw CLAUDE.md line count is misleading — the actual context cost is the expanded content.

For each CLAUDE.md file:
1. Grep for lines matching `^@` (import directives)
2. For each `@path` found, resolve the path (expand `~` to home dir) and Read the target file
3. Record: import path, target file lines, target file chars, estimated tokens
4. Report both raw CLAUDE.md size AND expanded size (raw + all imports)
5. Use the **expanded** size for all benchmarks — that's what Claude actually sees
6. In the Context Breakdown table, show each import as a sub-row indented under its parent CLAUDE.md
7. Watch for circular imports or missing files (broken `@path` references)

Example: an 87-line CLAUDE.md with 4 `@import` directives might expand to 330+ lines — the expanded number is what matters.

### On-demand sources (not always-on)

10. `.claude/rules/*.md` — Path-scoped rules. Load only when Claude touches files matching their path patterns. Measure but categorize as on-demand.
11. Skill bodies — Full SKILL.md content beyond frontmatter. Loaded only when a skill is invoked.

### Settings (affect context indirectly)

12. `~/.claude/settings.json` — Count: permission allow rules, deny rules, ask rules, MCP server wildcards (`mcp__*` patterns), additional directories, enabled plugins.
13. `.claude/settings.local.json` — Same analysis for project-local overrides.
14. `.mcp.json` — Count MCP server definitions at project level.
15. `.claudeignore` — Check if it exists. If the project has `node_modules/`, `dist/`, `build/`, or `target/` directories but no `.claudeignore`, flag it.

---

## Phase 2: Benchmark — Thresholds

Compare measurements against these official limits. For each check, assign a status:
- PASS: Within limit
- WARN: Approaching limit (>75% of threshold)
- FAIL: Exceeds limit

| Check | Threshold | Why |
|-------|-----------|-----|
| Each CLAUDE.md file (raw) | ≤ 200 lines | Official recommendation. Beyond this, rule adherence degrades — "if Claude keeps ignoring a rule, the file is probably too long." (code.claude.com/docs/en/memory) |
| Each CLAUDE.md file (expanded, with @imports) | ≤ 500 lines | After resolving `@path` imports, the expanded content is what Claude actually sees. Files with heavy @imports may appear small but load hundreds of lines. Report both raw and expanded. |
| MEMORY.md | ≤ 200 lines | Hard cutoff — only first 200 lines auto-load at session start. Content beyond line 200 is invisible unless explicitly read. (code.claude.com/docs/en/memory) |
| MCP deferred tokens (all servers) | ≤ 4K tokens | Count all deferred tools across servers × ~50 tok/tool. Server count alone is misleading — a server with 5 deferred tools costs ~250 tok, one with 50 costs ~2,500 tok. When tools are loaded via ToolSearch, full schemas add ~200-400 tok/tool on demand. (github.com/anthropics/claude-code/issues/3406) |
| Brain files total (`~/.claude/brains/`) | ≤ 100 lines | Brain files are always-on for every project that @imports them. Each is shared context — useful but accumulates. Keep single-concern (one brain file per domain). |
| User-controlled always-on | ≤ 12K tokens | Separate from the fixed system prompt. User-controlled context (CLAUDE.md + memory + skill descriptions + MCP definitions) should leave 150K+ working space. A baseline of 24% window usage is acceptable for short/medium sessions — the real problem is accumulation: each turn adds conversation history, tool results, and file reads on top. |
| All skill descriptions combined | ≤ 16,000 chars | Fallback budget for skill metadata. With brain_tools Semantic Toolbox handling routing, descriptions should be minimal labels (~20-50 chars). Verbose descriptions are doubly wasteful: always-on cost + redundant with brain index. (code.claude.com/docs/en/skills) |
| Largest always-on file | ≤ 100 lines | Files over 100 lines in always-on context likely contain content that should be in skills (on-demand ~100 tokens) or rules (path-scoped). |
| .claudeignore exists | Yes, if project has build dirs | Prevents Claude from reading large generated files (node_modules, lock files, bundles). A single package-lock.json can be 30-80K tokens. 50-70% savings documented. |
| Additional directories | 0-2 entries | Each adds scanning scope. Stale entries (old project paths, system dirs like /dev) waste context. |

---

## Phase 3: Issue Taxonomy

Issues are classified into three tiers:

| Tier | Symbol | Meaning |
|------|--------|---------|
| Critical | ❌ | Exceeds a hard limit or causes significant measurable waste (>5K tokens) |
| Warning | ⚠️ | Approaching a limit or has moderate waste potential (1-5K tokens) |
| Info | ℹ️ | Optimization opportunity with low immediate impact but worth noting |

### 3a. Duplication across layers

Read the content of all always-on files (including @import-expanded content). Look for the same information appearing in multiple places:
- Pipeline commands in both MEMORY.md and architecture docs
- Tool gotchas in both tech docs and MEMORY.md
- Project description in both CLAUDE.md and AGENTS.md and brief.md
- **@import overlap**: A file imported via `@path` in global CLAUDE.md that is ALSO loaded as project-level auto-memory. This is double-loading — the same content appears twice in context.
- **Cross-layer import overlap**: Profile files imported into CLAUDE.md that duplicate summaries already written inline in the same file or in MEMORY.md
- **Brain file ↔ CLAUDE.md overlap**: Content in `~/.claude/brains/*.md` that duplicates information in CLAUDE.md, MEMORY.md, or other always-on files. Brain files should contain only ecosystem/shared context not present elsewhere.

For each duplication found, note which files contain it and recommend keeping it in exactly one canonical location.

### 3b. Stale content

Scan always-on files for signs of outdated content:
- Date patterns (YYYY-MM-DD) older than 30 days in changelog/history sections
- "Done", "Completed", "Resolved", "Shipped" markers in task lists
- "Recent Changes" sections with entries all older than 2 weeks
- Version numbers that might be outdated
- References to files or directories that no longer exist (use Glob to verify)

### 3c. Redundant permissions

Parse the `allow` arrays in settings files. Check for redundancy:
- Global `Bash(*)` makes every `Bash(specific:*)` in project settings redundant
- Global `WebFetch` (no domain) makes every `WebFetch(domain:X)` redundant
- Global `Read` makes every `Read(path)` redundant
- Duplicate MCP server patterns (e.g., `mcp__server__*` in both global and local)

Count total redundant rules. Each is small individually, but 50+ redundant rules in one project has been observed.

### 3d. Over-specified CLAUDE.md

Scan CLAUDE.md content for patterns that indicate material belongs elsewhere:
- Step-by-step workflows (>10 sequential steps) → should be a skill (~100 tokens metadata vs thousands always-on)
- File-specific instructions ("when editing X, do Y") → should be `.claude/rules/` (path-scoped, loads on-demand)
- Setup/install instructions → one-time knowledge, shouldn't be always-on
- Long code examples or templates → should be in skill's bundled resources

Skills are 150x more efficient than CLAUDE.md for specialized instructions: ~100 tokens per skill metadata vs 15K+ if inlined into CLAUDE.md. (Source: Skills docs, ClaudeFast metrics)

Additionally, flag verbose skill descriptions (>80 chars average) when brain_tools Semantic Toolbox is available. With brain_tools handling routing via semantic search, skill descriptions only need to be labels (~20-50 chars). Verbose descriptions are doubly wasteful: always-on token cost + redundant with brain's enriched index (which includes 300 chars of body context for search).

### 3e. MCP overhead analysis

MCP costs fall into three distinct tiers:

| Tier | What | Counted in baseline? | How to measure |
|------|------|---------------------|----------------|
| **MCP_DEFERRED** | Tool names in `<available-deferred-tools>` list | YES — always present | ~50 tokens per tool (name only, no schema). Count tools per server from the deferred list. |
| **MCP_LOADED** | Full tool schemas loaded via ToolSearch | NO — on-demand | ~200-400 tokens per tool (name + parameter schema). Only present after explicit ToolSearch invocation. Report separately as "on-demand MCP cost." |
| **MCP_RUNTIME** | Tool call results (API responses) | NO — never count | Varies wildly (50 tokens to 5K+ per call). Not measurable statically. Mention in Limitations section only. |

For each MCP server found in settings:
- Count its tools in the deferred-tools list → multiply by ~50 tokens = **MCP_DEFERRED cost** (baseline number to report)
- Check if it has corresponding `mcp__servername__*` allow rules (suggests active use)
- Note servers with no allow rules (possibly unused — loaded but never permitted)
- Flag duplicate server names (e.g., `notebooklm` AND `notebooklm-mcp`)

In the Context Breakdown table, report MCP as: `MCP deferred ({N} tools × ~50 tok)`. Do NOT estimate loaded schema costs as baseline — they are on-demand.

### 3e2. Skill body analysis (on-demand but high-impact)

Scan skill bodies (full SKILL.md content) for waste patterns. These are on-demand, but large skills consume significant tokens when invoked:
- Skills > 300 lines or > 10K chars — flag as oversized, recommend progressive disclosure refactoring (see below)
- Orchestrator skills that duplicate content from sub-skills — should be thin orchestrators with skill references, not content duplication
- Hardcoded values that may go stale (style descriptions, API URLs, version numbers) — suggest reading from canonical source files instead

**Progressive disclosure refactoring** — validated pattern for oversized skills:

Skills use a three-level loading system: metadata (always loaded, ~100 tokens) → SKILL.md body (on trigger) → references/ (on demand). Content that isn't needed for every invocation should move to reference files, loaded only when a specific mode or step requires it.

**What to extract to references/:**
- Output format templates (proposal formats, report structures, result tables)
- Mode-specific detailed procedures (steps only needed when that mode is active)
- Domain reference tables (lookup data, function lists, examples)
- Few-shot examples, troubleshooting guides, edge case handling

**What stays in SKILL.md:**
- Mode routing and decision logic (always needed to determine what to do)
- Quick-reference lookup tables (project IDs, key constraints)
- Core rules and constraints
- Pointers to reference files with "when to read" conditions

**Pointer convention:**
```
> Read `references/X.md` — [what it contains]. Read when [condition]. Skip for [condition].
```

Each reference file starts with a header: what it contains + when to load it.

**Validated savings** (7 skills refactored, March 2026):

| Skill | Before | After | Reduction | Ref files | Token savings per invocation |
|-------|--------|-------|-----------|-----------|------------------------------|
| obsidian-bases | 498 | 120 | -76% | 5 | high (modes skip unneeded refs) |
| alfred | 581 | 321 | -45% | 4 | -4.1% avg (Mode 3 skips science engine) |
| vocab-audit | 338 | 130 | -62% | 3 | moderate (scan mode skips review/fix refs) |
| token-optimize | 262 | 95 | -64% | 2 | moderate |
| finance | 250 | 67 | -73% | 2 | high (each mode reads only its procedure) |
| write-video | 226 | 76 | -66% | 2 | moderate |
| inbox | 206 | 137 | -33% | 1 | low (only Readwise mode extracted) |

Target: SKILL.md under 500 lines (guideline), ideally under 200 for multi-mode skills. Skills under 150 lines with single modes rarely benefit from splitting.

### 3f. Missing optimizations

Check for optimization opportunities not yet used:
- No `.claudeignore` but project has `node_modules/`, `dist/`, `build/`, `target/`, `__pycache__/` directories
- No `.claude/rules/` directory despite CLAUDE.md > 100 lines
- Skills without `disable-model-invocation: true` that appear to be manual-only (invoked by user, not auto-triggered). Note: this flag blocks Claude's Skill tool invocation entirely — orchestrator skills that call sub-skills via Skill tool will break. Only safe for skills invoked exclusively by user slash commands.
- `additionalDirectories` with entries pointing to non-existent paths or system dirs
- No use of Tool Search env var despite many MCP tools

### 3g. Cache-hostile patterns

Prompt caching saves 80-90% on repeated context (cache reads = 0.1× input cost). But the cache invalidates when tools, MCP servers, or model change mid-session — causing a 5× cost spike as the full prefix is reprocessed. Flag:
- Multiple MCP server configs that might change between sessions
- Settings that suggest frequent model switching

### 3h. Brain file sprawl

Brain files (`~/.claude/brains/*.md`) are shared context imported by project CLAUDE.md files. Each is always-on for every project that @imports it. Check:
- Total brain files count. If >3 files or >200 lines total, flag as potential sprawl.
- Each brain file should be single-concern (one domain/ecosystem). Multi-concern brain files should be split or trimmed.
- Brain files that are @imported by only 1 project should probably be in that project's CLAUDE.md instead.

### 3i. Hook dynamic overhead

SessionStart hooks can inject context per-session (e.g., brain-context.py queries brain.db for session summary + hot memories). This context is dynamic and not statically measurable, but impacts per-session token budget.
- Read SessionStart hook scripts to estimate injected token count. With L0+L1 pattern: ~50 tokens (last session summary + top-2 hot memories ≤80 chars each). Flag if brain-context.py is still injecting recent decisions + preferences sections (pre-L0/L1 pattern: ~300-500 tok).
- Flag if hook scripts read large data (e.g., querying >5 brain records, reading full files, or injecting >200 estimated tokens).
- Note: this is an estimate for the report's Limitations section — it cannot be precisely measured without running the hook.

### 3i.2. Per-prompt injection (UserPromptSubmit hook)

prompt-context.py fires on every user prompt and injects brain memories + optionally tool descriptions. Separate from SessionStart overhead.

Check prompt-context.py for:
- **CRITICAL**: `sections.append("Relevant tools:` present in `main()` → Semantic Toolbox still auto-injecting. Expected config: toolbox removed from hook, on-demand via explicit `brain_tools()` MCP calls only. Waste: ~400-600 tok/prompt.
- **WARNING**: No trivial-prompt gate before Phase 1 — look for word-count check (`len(prompt_words) <= 4 and "?" not in stripped`). Without it, filler prompts ("ok", "tiếp tục") trigger full FTS5+vector search.
- **INFO**: Confirm `MAX_INJECTED_CHARS` cap (3000 chars ~750 tok) and skip-if-unchanged logic are both present — these are the main guards against token runaway in long sessions.
