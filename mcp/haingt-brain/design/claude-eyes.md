# Design: Claude Eyes — Awareness System

> "AI can't see anything" — Po-Shen Loh
> "Người mù bị mất trí nhớ, tìm keyword hi vọng hit" — Hải's description of current Claude behavior

## Problem

Claude operates blind: each session starts with near-zero awareness. Every task begins with orientation — glob, grep, read, brain_recall — hoping to hit the right files. This wastes tokens and produces worse results than targeted search with prior awareness.

**Current pattern:** Task → blind search (5-10 attempts, ~8-10K tokens) → find target → do work
**Target pattern:** Task → glance at radar (~300-500 tokens) → targeted read (~2K tokens) → do work

**Constraint:** `Y + Z < X` where Y = awareness cost, Z = targeted search cost, X = blind search cost. If awareness data costs more tokens than it saves, it fails.

### Lazy-Eye Principle (design breakthrough)

Radar must NOT be always-on in context. An always-on 500-token radar carried across N exchanges = 500×N tokens of stale data. Like keeping eyes wide open while reading a book — you only needed to look around to find it.

**Model:** Generate eagerly (session start), consume lazily (Read on demand).
- SessionStart hook injects a **pointer** (~15 tokens): path + timestamp + instruction
- Claude reads `~/.claude/radar.md` via Read tool ONLY when it needs to orient
- Tool result gets naturally compressed after 2-3 turns
- Cost: 15 tokens × N exchanges (pointer) + 500 tokens × M reads (M = 1-3 per session)

**When to "open eyes":** navigating unfamiliar files, after a search miss, switching project context
**When to "close eyes":** pure chat, editing known files, continuous tool chains

## Research Findings (2026-04-10)

Community landscape — no unified system exists. Existing tools solve individual layers:

| Tool | What it does | Gap |
|------|-------------|-----|
| **CodeSight** | ~200 token wiki index + 300-400/article. Static generation | Not MCP-integrated, not git-aware, not lazy-load |
| **Code Index MCP** | Tree-sitter AST + 18 query tools | Pull-based only, no always-on awareness |
| **Claude Context (Zilliz)** | Semantic code search via embeddings | No project map, no structural outline |
| **Cursor** | Merkle tree + embeddings + semantic search | Pull-based, tightly coupled to IDE |
| **Sourcegraph Cody** | Hybrid dense-sparse retrieval + code graph | Enterprise, no push-based radar |
| **Aider** | Explicit user file control (/add, /drop) | Manual, no automation |
| **ctags** | 200+ languages, fast symbol index | Best Layer 2 tool — adopted for outline.sh |
| **ripgrep --json** | Structured cross-file search | Best for relational link extraction (Phase 2) |

**Key insight from research:** Everyone either does pull-based search OR generates large static files. Nobody does push-based lazy-load radar with a pointer injection pattern.

## Six Types of Blindness

| Type | Description | Current workaround | Waste |
|------|-------------|-------------------|-------|
| **Spatial** | Don't know what files/projects exist | glob, tree, ls | Medium |
| **Structural** | Don't know what's INSIDE files | Read entire file to find 10 lines | High |
| **Relational** | Don't know how files connect to each other | Manual gap audit, Hải reminds | High |
| **Temporal** | Don't know what changed recently, what's "hot" | git log, guess | Medium |
| **Self (Brain)** | Have memory but don't know what's stored | brain_recall with hopeful keywords | High |
| **System** | Don't know if tools/MCPs are healthy | Discover on failure | Low but painful |

## Architecture: 4-Layer LOD

Inspired by game rendering LOD (Level of Detail) — show less detail at distance, more detail up close. Each layer is progressively more expensive but more precise.

```
Layer 0 — Radar     (~300-500 tokens, lazy-load via pointer)  ✅ IMPLEMENTED
Layer 1 — Map       (~300 tokens/project, on demand)          (covered by radar Projects section)
Layer 2 — Outline   (~100-200 tokens/file, on demand)         ✅ IMPLEMENTED
Layer 3 — Content   (current Read tool, on demand)            (already existed)
```

### Layer 0: Radar (brain MCP tool, on-demand)

`brain_radar()` — Python MCP tool in haingt-brain server. Claude calls on demand, zero session-start cost. Covers spatial, temporal, self (brain), and relational blindness.

```
# Radar (auto: 2026-04-10 15:30)

## Projects
digital-identity | master | 3 modified | "update beliefs with Loh" (today)
Wildtide         | main   | clean      | "continuous wave refactor" (2d)
agent            | main   | clean      | "brain_graph tool" (1d)
Bookie           | main   | clean      | (5d)

## Hot (24h)
digital-identity: profile/beliefs.md, profile/roadmap.md, profile/goals.md

## Brain Topics
upwork(5) wildtide(8) identity(4) english(3) schedule(6) reflect(3) po-shen-loh(1)
Recent: po-shen-loh, parallel-channels, character-legibility

## MCP Health
brain: ok | todoist: ok | gcal: ok | readwise: ok

## Graph (top connections)
roadmap.md → goals.md, career.md, core-memory.md, brief.md
goals.md → roadmap.md, career.md
beliefs.md → identity.md
```

**Generation:** Bash script or brain MCP endpoint. Runs at session start (hook) or on-demand.

**Token budget:** Hard cap 500 tokens. If over → compress or drop lowest-value sections.

### Layer 1: Map (on demand, per project)

File tree with metadata. Called when Claude needs to navigate a specific project.

```
# Map: digital-identity

profile/           10 files, source of truth
  identity.md      shared, sat:4, updated:2026-04-10
  roadmap.md       shared, sat:-, updated:2026-04-10, 400 lines
  goals.md         shared, sat:7, updated:2026-04-10
  career.md        shared, sat:6, updated:2026-04-10
  beliefs.md       shared, sat:7, updated:2026-04-10
  ...
cv/                LaTeX CV, derived from career.md
scripts/           derive.sh, audit.sh
.claude/skills/    5 skills: alfred, learn, mentor, reflect, upwork
```

**Generation:** Script that reads directory tree + YAML frontmatter. ~300 tokens/project.

**Already partially exists:** CLAUDE.md project structure section. But static, not auto-generated, no file metadata.

### Layer 2: Outline (on demand, per file)

Internal structure of a single file. For markdown = heading tree. For code = function/class signatures. For config = key sections.

```
# Outline: profile/roadmap.md (400 lines)

L1-5:     frontmatter (updated: 2026-04-10)
L7-26:    ## Thesis + Compass Principle
L28-67:   ## Financial Reality
L68-78:   ## Operating Model (PROVE/EXECUTE/WANDER/BACKBURNER)
L80-98:   ## Goal-Based Approach (Big Tasks)
L100-117: ### PRIMARY: Wildtide (PROVE)
L118-128:   1. Upwork Trigger
L130-138:   2. Community Engagement — Trust Network
L140-148:   3. Micro-Products
L149-157: ### BACKBURNER
L159-181: ### Lighthouse Checkpoints + Conditional Logic
...
```

**Generation:** `brain_outline(filepath)` MCP tool — Python regex per file type. ~100-200 tokens/file.

**Key insight:** This layer is what eliminates "read 400 lines to edit 10." With outline, Claude reads L130-138 directly.

### Layer 3: Content (existing)

Current Read tool. No changes needed — but now used with precise offset+limit from Layer 2 instead of reading entire files.

## Relational Awareness (Obsidian Model)

The most novel part. Inspired by Obsidian's backlinks and graph view.

### How files reference each other

References detected by pattern:

| Pattern | Example | Type |
|---------|---------|------|
| Markdown links | `[roadmap](roadmap.md)` | Explicit |
| @-references | `@~/.claude/core-memory.md` | Explicit |
| "See X" / "ref X" | `(ref Po-Shen Loh)` | Explicit |
| YAML references | `source: career.md` | Explicit |
| Import/require | `from brain import recall` | Code |
| Shared topics | Both files discuss "Wildtide" | Implicit |
| Brain tags | Multiple memories tagged "upwork" | Implicit |

### Dependency direction

Not all references are equal. Some files are **sources of truth**, others **derive from** them:

```
roadmap.md (source) → goals.md (derives summary)
roadmap.md (source) → core-memory.md (derives compressed version)
roadmap.md (source) → brief.md (derives overview)
career.md (source) → cv/Profile.tex (derives formatted output)
profile/* (source) → derived/* (auto-generated)
```

### Cascade awareness

When Claude edits a source-of-truth file, radar should surface:

```
⚠ Editing roadmap.md — downstream files:
  goals.md (Roadmap section, L67-83)
  core-memory.md (Ecosystem line)
  brief.md (Roadmap section)
  mentor/SKILL.md (cross-reference rules)
```

This eliminates the manual gap audit from 2026-04-10 session (where Hải had to ask "còn gap nào không?").

### Implementation options

1. **Static graph file** — manually maintained `references.yml` mapping file relationships. Simple, but drifts.
2. **Auto-detected** — script scans markdown links, @-references, shared headings. More accurate, needs parsing.
3. **Brain-integrated** — brain_graph already exists. Extend to include file-to-file relationships, not just memory-to-memory.
4. **Hybrid** — auto-detect explicit refs + manual annotation for implicit deps. Best accuracy.

**Recommendation:** Start with (2) auto-detection of explicit refs. Add manual overrides for key implicit deps (roadmap→goals, roadmap→core-memory). Evolve toward (3) if brain_graph can handle it.

## Brain Self-Awareness

### Current state

`brain_session("start")` returns: recent sessions, preferences, recent decisions, active entities. This is useful but doesn't answer "what TOPICS does brain know about?"

`brain_recall(query)` is semantic search — but searching without knowing what's searchable is inefficient.

### Proposed: brain topic index

A compact summary of what's stored, organized by topic cluster:

```
Brain Index (142 memories):
  upwork: 5 (decisions:2, discoveries:2, preferences:1)
  wildtide: 8 (decisions:3, discoveries:4, entities:1)
  identity: 4 (discoveries:3, preferences:1)
  english: 3 (decisions:2, discoveries:1)
  schedule: 6 (patterns:4, decisions:2)
  reflect: 3 (sessions:3)
  po-shen-loh: 1 (discoveries:1)
  
  Last 7 days: po-shen-loh, parallel-channels, character-legibility, permission-seeking
  Stale (30+ days, 0 access): [list]
```

**Token cost:** ~50-80 tokens. Included in Layer 0 radar.

**Implementation:** `brain_index(days)` MCP tool — SQL with `json_each(memories.tags)`, grouped by tag + memory type. Returns topics with by_type breakdown, stale entries (30+ days, 0 access), recent tags.

**Search termination:** Knowing "upwork has 5 memories" means after finding 5, Claude knows to stop searching. No more "maybe there's one more I missed."

## Token Economics

### Cost model (updated post-refactor)

| Component | Tokens | Frequency |
|-----------|--------|-----------|
| Session start overhead | 0 | None — all tools on-demand |
| `brain_radar(project=X)` | ~80 | 1-3× per session |
| `brain_radar(scope="all")` | ~200-300 | Rare (digital-identity only) |
| `brain_outline(filepath)` | 100-200 | Per file before edit (~3-5x) |
| `brain_index()` | ~50-80 | 0-1× per session |

### Savings model

| Without eyes | With eyes | Savings |
|-------------|-----------|---------|
| 5-10 blind searches × ~1K = 5-10K | 1-2 targeted reads × ~1K = 1-2K | 3-8K/task |
| Read full file 400 lines = 4K | Read 20 lines with offset = 400 | 3.6K/file |
| Gap audit post-edit = 5-10K | Cascade warning = 50 | 5-10K/edit |
| brain_recall × 3 attempts = 3K | 1 targeted recall = 1K | 2K/search |

**Estimated net savings:** 15-30K tokens/session after Layer 0 cost.

### Hard rules

- Layer 0 MUST stay under 500 tokens. Exceeding = redesign, not expand.
- Layer 2 outlines are cached per session — don't regenerate for same file.
- If a layer's cost > its savings for a specific task → skip that layer.

## Implementation Status

### Phase 1: Radar + Outline — ✅ COMPLETE → REFACTORED (2026-04-10)

Originally bash scripts (generate-radar.sh + outline.sh + pointer injection). Refactored same session to brain MCP tools for: single DB access, zero session-start latency, on/off = don't call.

### Phase 2: File Reference Graph — ✅ COMPLETE (2026-04-10)

Integrated into `brain_radar()` as `file_graph` key. Auto-detects markdown links, @-references, ref/see patterns. Returns adjacency dict.

### Phase 3: Brain Index — ✅ COMPLETE (2026-04-10)

`brain_index(days)` MCP tool — topic breakdown by memory type + stale detection + recent tags.

### Workspace Scope — ✅ COMPLETE (2026-04-10)

`brain_radar(project, scope)` — 3-level scope:
- `project="Wildtide"` → single project (~80 tokens)
- `scope="ecosystem"` → 4 core projects (~150 tokens)
- `scope="all"` or no params → all 11 projects (~300 tokens)

Brain topics also filtered by project when `project` param given.

### Current Architecture

| Tool | File | Purpose |
|------|------|---------|
| `brain_radar(project, scope)` | `src/haingt_brain/tools/radar.py` | Projects, hot files, brain topics, file graph |
| `brain_outline(filepath)` | `src/haingt_brain/tools/outline.py` | File structure, 7 types |
| `brain_index(days)` | `src/haingt_brain/tools/index.py` | Topic breakdown by type |
| CLAUDE.md `### Eyes` | `~/.claude/CLAUDE.md` | Behavioral instruction |

**Removed:** `generate-radar.sh`, `outline.sh`, `~/.claude/radar.md`, session-start.sh radar block.

**Brain query:** `json_each(memories.tags)` with noise exclusion (10 tags). Project filtering via `memories.project = ?`.

## Eval Framework

After 5 sessions with Phase 1 deployed:

| Metric | Baseline | Target |
|--------|----------|--------|
| Blind searches per task | ~5-8 | < 2 |
| Token waste on orientation | ~8-10K/task | < 3K/task |
| Gap audit requests from Hải | frequent | rare |
| Radar reads per session | n/a | 1-3 |
| Outline reads per session | n/a | 2-5 |

**Decision gate:** If no improvement after 5 sessions → investigate root cause before Phase 2.

## Future

1. **workspace.yml** — per-project workspace config (e.g., workstation-setup + live configs at ~/.config/). Not built yet.
2. **Cascade warnings** — when editing source-of-truth file, surface downstream files. Data exists in file_graph, needs UI/workflow integration.
3. **Implicit relations** — auto-detect shared topics (expensive, fuzzy). Start manual, evolve.
4. **MCP health check** — add to radar if tool failures become frequent.
5. **Outline caching** — cache outline per session if same file requested multiple times.

## References

- Po-Shen Loh, "AI Will Create New Wealth, But Not Where You Think" (EO, 2026) — inspired the "AI can't see" observation
- Obsidian backlinks/graph view — model for relational awareness
- Game LOD rendering — metaphor for progressive detail loading
- Session 2026-04-10 gap audit — concrete example of relational blindness costing ~10K tokens
- CodeSight wiki mode — closest existing approach to radar concept
- Cursor/Cody/Zed context systems — pull-based semantic search (nobody does push-based lazy radar)
