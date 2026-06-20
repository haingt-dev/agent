# haingt-brain — Architecture Document

> Last updated: 2026-06-13 (pre-compact-snapshot.py audit — see §0aa)
> Version: v4.1.0 (+ 2026-06-12 audit patches + 2026-06-13 pre-compact fixes)
> Status: Production (single-user, daily use)
> Origin: Applied concepts from DeepLearning.AI "Building Memory-Aware Agents" course
> Maintenance: before trusting any section, verify against `hooks/hooks.json` + `ls src/haingt_brain/` — the 2026-06-12 audit found 14 drift points in the 04-02 version.

## 0aa. Changelog — 2026-06-13 (pre-compact-snapshot.py — last unaudited hook)

The one file the 2026-06-12 audit deferred is now audited + fixed (regression suite `plugins/haint-core/scripts/test_pre_compact_snapshot.py`, 12/12; brain pytest still 98/98). It runs on every PreCompact, writing a 9-section `type=session` snapshot direct to brain.db.

- **Underscore-project corruption (root cause of the `Learning-English`→`Learning_English` scope migration the 2026-06-12 cleanup had to run)**: project scope was derived from the transcript dir name, which Claude Code mangles `_`→`-` (`Learning_English` → `-home-haint-Projects-Learning-English`). Snapshots for `Learning_English`/`Idea_Vault` saved under the wrong (hyphenated) scope. Fixed: resolve cwd from the hook payload's `cwd` field (canonical, underscores intact); a filesystem-probing fallback recovers the real dir when `cwd` is absent.
- **Dedup-cache miss after compact → next session's memories silently not re-injected**: `_reset_prompt_cache` rebuilt the cwd from the mangled project name, so `md5(cwd)[:8]` didn't match prompt-context.py's key (computed from the real `Path.cwd()`). For underscore projects the unlink missed; the surviving cache made prompt-context believe the prior session's memories were still in context and skip re-injection. Now keyed off the real cwd (verified `md5(/home/haint/Projects/agent)[:8] == bf884550` == the live cache file). Cache reset also now fires on every compaction path, including the empty-transcript early-exits.
- **Mid-sentence fragments (9/10 sampled snapshots)**: signal context was a raw ±40-char window then a mid-word `text[:limit-3]` cut — fragmented at both ends. Replaced with sentence-aware extraction (`_sentence_window` snaps to sentence boundaries within a bounded scan radius) + word-boundary `_truncate`; intent / current-work / next-step now take the first whole sentence. Per-line budget raised (60→120–180), snapshot cap 2500→3200 and cut at a section boundary instead of mid-line.
- **Double-save guard**: two compacts seconds apart (observed pair 29s apart) double-saved the same state, and snapshots are dedup-invisible to the cosine pool (no embedding). Added a content-hash guard (sha256 of the snapshot body minus the volatile header timestamp line, stored in `metadata.content_hash`) that skips an identical save within 10 min. Embeddings intentionally NOT added — these are TTL-14d working memory found via FTS5 + SessionStart; an embedding round-trip would add latency and a failure mode to the compaction path for marginal recall value.
- **Input hygiene**: primary intent and the user-messages section were polluted by `<system-reminder>` / `<command-*>` wrapper blocks; `_clean_user_text` strips them per content-item so intent reflects the real first request.

## 0a. Changelog — 2026-06-12 audit phase 2 (server + hooks hardening)

Phase-2 audit (3 more dimensions: deep server code, injection eval, transcript usage) findings fixed same day:

- **CRITICAL — decay time bomb defused**: `consolidate_all` now defaults to `SAFE_STRATEGIES` ({merge, sessions, cluster}); the MCP `brain_session('consolidate')` path would have run decay and deleted 526/1628 memories (32%, measured dry-run). Compounding decay bug fixed (decay window capped at days-since-last-decay-run via `brain_meta.last_importance_decay`).
- **FTS5 sanitization**: `sanitize_fts_query` quotes tokens — 'judge.py', 'chimera-protocol', 'C++' used to raise OperationalError, silently degrade to vector-only, then get blanked by the noise gate. Vector fallback now marks `fts_hit=NULL` (unknown) and the noise gate exempts NULL hits + min_candidates pools. graph.py shares the sanitizer + dedups edges (~40% were duplicates).
- **vn_normalize**: mixed-case guard + VN syllable-structure validator + denylist — 'DDoS'→'Đó', 'uwsgi'→'ưsgi', 'Kuwait'→'Kưait' corruptions fixed; legit Telex ('nguwowif'→'người') unaffected.
- **Transaction safety**: brain_save/brain_update wrap writes in try→rollback (failed saves used to leave dangling transactions that ghost-committed later); relations validated before any INSERT.
- **Session attribution**: `brain_session('save')` passes `project` through (233/234 sessions had self-perpetuated 'digital-identity'); recent-sessions query NULL-safe.
- **Hook injection quality** (prompt-context.py): LLM gate rebalanced with life-domain ALLOW examples (was 97.8% skip-biased — blocked career/schedule/Upwork/vaccine prompts); ≤4-word skip exempts path/code tokens; tool search inverted to vector-primary with cosine floor 0.35 (calibrated: true matches 0.435+, noise ≤0.312; old FTS-first path produced 91%-never-followed suggestions) + once-per-session suggestion set + flattened/word-clipped content + tool access telemetry; memory FTS leg uses full-prompt content words (was first-5-words of first-100-chars); judge runs for small pools (≥2); injected memories carry '(Nd ago)' age labels.
- **SessionStart** (brain-context.py): semantic dedup across sections via dedup_pool; decisions over-fetch 6→3; `compact` source emits hot-tier only (one 7-week session had accumulated 77 near-identical full blocks).
- **Misc**: `_load_env` always parses .env (exported OPENAI_API_KEY used to silently disable the judge); importance backfill one-shot via brain_meta flag (ran on every connect forever); dry-run consolidation no longer makes paid LLM calls; weekly cron runner TTL-purges pre-compact snapshots >14d (they are vector-less and dedup-invisible by design); index_tools word-boundary clip.
- **Deferred** (known, low-priority): hybrid_search filters still apply after top-20 candidate selection (affects narrow filtered recalls); anaphoric continuation prompts ("Chốt B…") still retrieve without the referent (needs assistant-tail blending); hook-side judge spend not counted against the daily budget. *(pre-compact-snapshot.py internals — resolved 2026-06-13, see §0aa.)*

## 0. Changelog — 2026-06-12 full-system audit

Changes shipped (sections below may not reflect them yet — this block wins on conflict):

- **Retrieval**: hybrid_search now EXCLUDES memories that are the target of a `supersedes` relation; results carry `fts_hit`/`vec_hit` (dual-source hit = empirically 100% precision tier, exposed as `dual_hit` in brain_recall). Near-duplicate pool dedup (cosine ≥ 0.92) runs before the judge in both brain_recall and prompt-context.py.
- **Judge** (`judge.py`): candidates scored ≤ `JUDGE_DROP_MAX` (default 3) are DROPPED, not just demoted — empty recall beats confident noise. Noise gate in recall.py: on judge fallback, a pool with zero FTS hits returns []. API timeout now `JUDGE_TIMEOUT_S` (default 6s, was 10s ×2 → 11-15s outliers). Judge cache stores post-drop order.
- **Injection telemetry**: prompt-context.py bumps access_count/last_accessed for every memory it actually injects — access_count finally measures the main consumption path. TYPE_PRIORITY: preference promoted to tier 0, entity demoted to tier 1 (stalest type in audit).
- **Hooks**: `entity-extract.py` REMOVED from Stop (57% of its entities were paraphrase dups/stale facts; it resurrected retired project names). `stop-saveable.py` (suggest-only) stays. SessionStart `brain-context.py`: hot-tier/Preferences duplication fixed (was 45% wasted payload), truncation 120 → 200 chars at word boundary.
- **Consolidation**: trigger moved out of the never-called `brain_session("start")` path (it had not run for 71 days; counter could never reach the gate). Now: `scripts/run_consolidation.py` (intended weekly cron Sunday 23:30 — cron entry pending owner approval; first run executed supervised 2026-06-12) runs `merge` (threshold 0.95 — 0.88 merged formulaic-but-distinct phase logs) + `sessions` (idempotency guard added: weeks already digested are skipped — root fix for the 2026-05 digest-loop class) + `cluster`. **`decay`/`patterns` strategies deferred**: compute_decay prunes a never-recalled 0.8-importance memory in ~60 days, and last_accessed was systematically under-recorded until injection telemetry landed. Re-evaluate ~4 weeks after 2026-06-12, retune the curve first.
- **Toolbox**: rebuilt — 129 capabilities. Gmail/Calendar seeds renamed to live claude.ai connector names (old `gmail_*`/`gcal_*` were dead), Google Drive added, Todoist/Readwise topped up.
- **Data cleanup**: 61 junk/stale entities deleted (echo-paraphrases, skill-invocation stubs, Wildtide resurrections), 3 seed entities corrected (ironcradle/godot/phase), 212 pre-compact session snapshots >14d purged (write-only data: 98% never recalled), project scopes migrated (`chimera-protocol`→`chimera`, `Learning-English`→`Learning_English`), 5 orphan vectors removed. DB: 1,856 → ~1,594 memories.
- **Corrections to the 04-02 text**: importance.py / judge.py / vn_normalize.py are IMPLEMENTED (§16 lists importance as future); hook system = 6 events / 8 scripts incl. stop-saveable + replay_skip_gate (§6 says 5); config lives natively in `~/.claude/`, NOT `~/Projects/agent/global/` (§12); brain.db IS backed up daily via workstation-setup bundle cron (§15 says no backup); DB scale is ~1.6K memories, not ~70 (§15); core-memory.md ≈ 1.0-1.4K tokens, not ~480 (§12); plugin runs from the marketplace SOURCE directory (`~/Projects/agent/plugins/haint-core`), the `~/.claude/plugins/cache/.../4.1.0` copy is stale debris.

## 1. System Overview

**haingt-brain** is a custom MCP server that gives Claude Code persistent semantic memory. It replaces Engram MCP (which had no delete, no semantic search, 9% save compliance).

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| MCP SDK | `mcp[cli]` (official Python SDK) |
| Transport | stdio |
| Database | SQLite + `sqlite-vec` (ANN) + FTS5 (full-text) |
| Embeddings | OpenAI `text-embedding-3-large` (3072 dims) |
| Search | Reciprocal Rank Fusion (FTS5 + vector) |
| DB Location | `~/.local/share/haingt-brain/brain.db` |
| Project Root | `~/Projects/agent/mcp/haingt-brain/` |

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   Claude Code CLI                       │
│  System prompt + CLAUDE.md + core-memory.md + skills    │
└──────┬──────────────────────────────────┬───────────────┘
       │                                  │
  Hook Layer                         MCP Protocol
  (deterministic)                    (agent-triggered)
       │                                  │
┌──────▼──────────────────┐    ┌──────────▼──────────────┐
│ 5 Hook Scripts           │    │ haingt-brain MCP Server  │
│                          │    │                          │
│ SessionStart             │    │ 7 Tools:                 │
│  └─ brain-context.py     │    │  brain_save              │
│     (read brain.db)      │    │  brain_recall            │
│                          │    │  brain_forget            │
│ UserPromptSubmit         │    │  brain_update            │
│  └─ prompt-context.py    │    │  brain_tools             │
│     (hybrid RRF query)   │    │  brain_session           │
│                          │    │  brain_graph             │
│ PostToolUse (Web*)       │    │                          │
│  └─ search-and-store.py  │    │ Embeddings (OpenAI)      │
│     (write brain.db)     │    │  └─ LRU cache (128)      │
│                          │    │                          │
│ PreCompact               │    │ Hybrid Search (RRF)      │
│  └─ pre-compact-         │    │  └─ FTS5 + sqlite-vec    │
│     snapshot.py           │    │                          │
│     (read transcript,    │    │ Auto-Consolidation       │
│      write brain.db)     │    │  └─ merge / decay /      │
│                          │    │     compress (7-day)     │
│ PreToolUse (Bash)        │    │                          │
│  └─ pre-tool-safety.sh   │    └──────────┬───────────────┘
└──────────────────────────┘               │
                                    ┌──────▼───────────────┐
       Direct SQLite R/W ──────────►│ brain.db (SQLite)    │
       (hooks bypass MCP)           │                      │
                                    │ memories        (PK) │
                                    │ memory_vectors  (vec)│
                                    │ memory_fts     (FTS5)│
                                    │ relations       (KG) │
                                    │ sessions        (LC) │
                                    │ brain_meta      (KV) │
                                    └──────────────────────┘
```

**Two access paths to brain.db:**
- **MCP tools** (via stdio): Claude calls brain_save/recall/etc → server.py → SQLite
- **Hook scripts** (direct SQLite): Python scripts import sqlite3, read/write brain.db directly — bypasses MCP stdio limitation

## 3. Database Schema

### memories
```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,              -- 12-char hex UUID
    content TEXT NOT NULL,            -- the actual memory text
    type TEXT NOT NULL,               -- enum: decision|discovery|pattern|entity|preference|session|tool
    tags TEXT DEFAULT '[]',           -- JSON array of strings
    project TEXT,                     -- NULL = global, otherwise project name
    metadata TEXT DEFAULT '{}',       -- arbitrary JSON (tool schemas, etc.)
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    access_count INTEGER DEFAULT 0,   -- incremented on each recall hit
    last_accessed TEXT                -- timestamp of last recall hit
);
```

### memory_vectors (sqlite-vec)
```sql
CREATE VIRTUAL TABLE memory_vectors USING vec0(
    memory_id TEXT PRIMARY KEY,
    embedding FLOAT[3072]             -- OpenAI text-embedding-3-large
);
```

### memory_fts (FTS5)
```sql
CREATE VIRTUAL TABLE memory_fts USING fts5(
    content, tags, project,
    memory_id UNINDEXED,
    tokenize='unicode61 remove_diacritics 2'  -- Vietnamese diacritic support
);
```

### relations (Knowledge Graph)
```sql
CREATE TABLE relations (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,       -- enum: causes|fixes|contradicts|relates_to|used_in|part_of|supersedes
    weight REAL DEFAULT 1.0,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (source_id, target_id, relation_type),
    FOREIGN KEY (source_id) REFERENCES memories(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES memories(id) ON DELETE CASCADE
);
```

### sessions
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,              -- 12-char hex UUID
    project TEXT,
    started_at TEXT DEFAULT (datetime('now')),
    ended_at TEXT,
    summary TEXT,
    memory_ids TEXT DEFAULT '[]'      -- JSON array of memory IDs created during session
);
```

### brain_meta
```sql
CREATE TABLE brain_meta (
    key TEXT PRIMARY KEY,             -- e.g., 'last_consolidation'
    value TEXT NOT NULL
);
```

### Indexes
```sql
idx_memories_type, idx_memories_project, idx_memories_created,
idx_relations_source, idx_relations_target, idx_sessions_project
```

## 4. MCP Tools (7)

### brain_save
Store a memory with automatic embedding.
```
Params: content (str), type (str), tags? (list), project? (str), metadata? (JSON str), relations? (JSON str)
Returns: {id, status, type, tags, project}
Flow: generate ID → embed content → INSERT memories + memory_vectors + memory_fts + relations → commit
```

### brain_recall
Search memories using hybrid semantic + keyword search. When `JUDGE_ENABLED=true`,
results are LLM-reranked for contextual relevance (+400-800ms, soft-fail to RRF
on any error). First result entry carries `_judge_status` field.
```
Params: query (str), type? (str), project? (str), k (int=5), time_range? (str, e.g. '-7 days')
Returns: [{id, content, type, tags, project, created_at, access_count, relevance, _judge_status?}]
Flow: embed query → FTS5 top-20 + vector top-20 → RRF combine → oversample (k*3, capped 10-20)
      → budget gate → LLM judge rerank (if enabled) → top-k → update access_count on final top-n
Env:  JUDGE_ENABLED, JUDGE_MODEL (default gpt-4o-mini), JUDGE_DAILY_BUDGET_USD (default 0.50),
      JUDGE_MIN_CANDIDATES (default 4), JUDGE_DEBUG
```

### brain_forget
Delete a memory and all associated data.
```
Params: memory_id (str)
Returns: {status, id, type, content_preview}
Flow: DELETE from memories + memory_vectors + memory_fts + relations → commit
```

### brain_update
Update content/tags/metadata while preserving ID, access_count, created_at, relations.
```
Params: memory_id (str), content? (str), tags? (list), metadata? (JSON str)
Returns: {id, status, type, content, access_count, created_at}
Flow: if content changed → re-embed + re-index FTS. UPDATE memories → commit
```

### brain_tools
Semantic Toolbox — find the right tool/skill by meaning.
```
Params: query (str), k (int=3)
Returns: [{tool_name/skill_name, mcp_server, category, content}]
Flow: hybrid_search with type='tool' filter → return top-k matches
```

### brain_session
Session lifecycle management.
```
Params: action (str: start|save|status|consolidate), project?, session_id?, summary?, decisions?, discoveries?, entities?
Actions:
  start  → create session, auto-consolidate if >7 days, return context (recent sessions, decisions, preferences, entities)
  save   → mark session ended, persist summary + auto-create memories from decisions/discoveries/entities lists
  status → return {total_memories, by_type, created_last_7_days, total_sessions, sessions_with_summary, importance_tiers?, judge_stats?}
  consolidate → run all 3 consolidation strategies, return report
```

### brain_graph
Traverse knowledge graph via BFS.
```
Params: entity (str: memory ID or search term), depth (int=2)
Returns: {root, nodes[], edges[], depth_searched}
Flow: if entity is not a valid ID → brain_recall to find starting node → BFS over relations table
```

## 5. Search: Reciprocal Rank Fusion

```sql
WITH fts_results AS (
    SELECT memory_id, rank, ROW_NUMBER() OVER (ORDER BY rank) AS fts_pos
    FROM memory_fts WHERE memory_fts MATCH :query
    LIMIT 20
),
vec_results AS (
    SELECT memory_id, distance, ROW_NUMBER() OVER (ORDER BY distance) AS vec_pos
    FROM memory_vectors WHERE embedding MATCH :embedding AND k = 20
),
scored AS (
    SELECT COALESCE(f.memory_id, v.memory_id) AS memory_id,
           COALESCE(1.0 / (60 + f.fts_pos), 0) +
           COALESCE(1.0 / (60 + v.vec_pos), 0) AS rrf_score
    FROM fts_results f FULL OUTER JOIN vec_results v ON f.memory_id = v.memory_id
)
SELECT m.*, s.rrf_score FROM scored s JOIN memories m ON m.id = s.memory_id
WHERE {type/project filters}
ORDER BY s.rrf_score DESC LIMIT :k
```

**Fallback**: If FTS5 fails (empty table, syntax error) → pure vector search.

**Access tracking**: Every recalled memory gets `access_count += 1` and `last_accessed = now()`.

## 6. Hook System (5 hooks)

### SessionStart → `session-start.sh` + `brain-context.py`
- **Trigger**: Every session start, resume, or post-compact
- **Output**: Git branch + recent commits + brain context
- **brain-context.py**: Direct SQLite read → recent decisions (3, 7 days), preferences (3), last session summary (1)
- **Memory Staleness Warnings**: Memories older than 2 days get an `(Nd ago)` suffix appended to their content in the injected context (e.g. `(5d ago)`). Gives Claude immediate recency signal without extra tokens.
- **Target**: ~300-500 tokens injected

### UserPromptSubmit → `prompt-context.py`
- **Trigger**: Every user message (>10 chars, not slash commands)
- **Input**: `{"prompt": "user's message"}`
- **Output**: `{"additionalContext": "Brain context: ...\n\nRelevant tools: ..."}` or empty
- **Architecture**: Embed once → search twice (general hybrid + tool vector)
- **Phase 1 — General memories**: Hybrid FTS5 + vector RRF, project-scoped, type-weighted
  - Over-fetch 8 → dedup filter (skip already-injected) → top 3
  - Token cap: `MAX_INJECTED_CHARS = 3000` (~750 tokens) across session
  - **FTS5 Pre-filter**: Before calling the OpenAI embedding API, runs a keyword FTS5 search. If ≥3 results hit → use FTS-only path (skips the embedding call). 80%+ prompts hit this path. Falls back to full hybrid RRF when <3 FTS5 results.
  - **General Memory Skip-if-Unchanged**: If the top-3 memory IDs are identical to the previous prompt's injected IDs → skip re-injection entirely. Saves ~500-750 tokens per unchanged prompt in stable-topic conversations.
- **Phase 2 — Semantic Toolbox**: Vector-only search for type='tool'
  - Fresh top-3 every prompt (no dedup — tools are per-prompt relevance)
  - Skip-if-unchanged: same tool names as last prompt → skip injection
  - Token cap: `MAX_TOOL_INJECTED_CHARS = 6000` safety net
- **Dedup cache**: `/tmp/brain-prompt-ctx-{md5(cwd)[:8]}.json`
  - Tracks: injected IDs, accumulated keywords, memory chars, tool state
  - TTL: 2 hours. Also reset by PreCompact (compact wipes system-reminders)
- **Multi-turn context**: Accumulates keywords from recent prompts → richer embedding queries
- **Performance**: ~150ms typical (FTS5 pre-filter path skips embedding API); ~250ms on vector fallback path

### PostToolUse → `post-tool-use.sh` + `search-and-store.py`
- **Trigger**: After WebSearch, WebFetch, or Context7 query-docs completes
- **Input**: `{"tool_name": "...", "tool_input": {...}, "tool_result": "..."}`
- **P1 Entropy filter**: Skip if content <80 chars or cosine sim ≥0.75 with existing memory
- **P2 Atomic decomposition**: LLM distills raw results into 1-3 self-contained facts (gpt-5.4-nano)
- **Action**: Parse result → write to brain.db as type=discovery, tags=[tool_type, "auto-captured"]
- **Embedding**: Attempted via brain venv Python (graceful fail → FTS-only is still useful)
- **Output**: Reminder to brain_save for deeper analysis

### PreCompact → `pre-compact.sh` + `pre-compact-snapshot.py`
- **Trigger**: Before context compaction
- **Input**: `{"transcript_path": "/path/to/transcript.jsonl"}`
- **Action**: Parse last 20 user+assistant messages → 9-section structured extraction → write to brain.db as type=session, format=structured-v2
- **9-Section Format** (aligned with Claude Code compact prompt structure):
  1. Primary Request & Intent
  2. Key Concepts & Technologies
  3. Files & Code Discussed
  4. Errors & Fixes Applied
  5. Problem Solving Approach
  6. User Messages Summary
  7. Pending Tasks
  8. Current Work State
  9. Immediate Next Step
- **Cache reset**: Deletes prompt-context dedup cache for this session (compact wipes system-reminders → dedup/caps must reset to allow re-injection)
- **No embedding**: FTS-only (hook must stay fast)
- **Why**: Prevents context loss on /compact — brain-context.py re-injects on next SessionStart. 9-section format mirrors Claude Code's own compact prompt, improving continuity signal quality.

### Stop → `entity-extract.py`
- **Trigger**: After Claude finishes a response (Stop hook)
- **Action**: Regex extraction of entities (tools, technologies, projects, people) from the assistant turn
- **LLM Distillation**: After regex extraction, the top 5 findings are passed to gpt-5.4-nano for refinement into atomic facts with confidence scores. Low-confidence extractions are discarded.
- **Output**: Writes type=entity memories directly to brain.db (direct SQLite, no MCP)

### PreToolUse (Bash) → `pre-tool-safety.sh`
- **Not brain-related** — safety validation only

## 7. Consolidation

Five strategies, all in `consolidate.py`:

### merge_duplicates (threshold=0.80)
- For each non-tool memory: sqlite-vec ANN search k=6 neighbors
- If cosine similarity ≥ 0.80 AND same type → merge
- Keep memory with higher access_count (or newer if tied), merge tags
- **Complexity**: O(n·k) where k=6

### decay_patterns (days_inactive=90)
- Delete type='pattern' memories not accessed in 90 days
- Only patterns decay — all other types are permanent

### consolidate_sessions (older_than_days=30)
- Group sessions >30 days old by (project, ISO week)
- Merge into weekly-digest memory (type=session)
- Original session records kept in sessions table (audit trail)

### decay_importance (Ebbinghaus)
- Apply exponential decay to all memory importance values (except preference, tool)
- Exempt: memories accessed within last 7 days
- Memories below 0.05 importance → auto-pruned
- Graph boost: hub memories (5+ connections) resist decay via `compute_graph_boost()`
- No positive feedback: access updates `last_accessed` but does NOT boost importance

### cluster_and_synthesize (P3 — recursive consolidation)
- Group memories by (project, type), find clusters of 3+ with cosine sim ≥ 0.65
- LLM synthesizes cluster into one abstract memory (via gpt-5.4-nano)
- Originals get `part_of` relation to synthesis, importance halved
- Only processes memories >7 days old. Max 3 clusters per run (LLM cost control)
- **Idempotence guard**: candidate query excludes anything already involved in a synthesis — both `target_id` (the synthesis itself) AND `source_id` (originals already folded in). Without this, each run reads its own output and re-synthesizes indefinitely.

### Auto-trigger
- `brain_session("start")` checks `brain_meta.last_consolidation`
- If >3 days since last run → `consolidate_all()` automatically
- `brain_session("save")` triggers `cluster_and_synthesize` if 4+ memories created AND the session was not previously ended (idempotence guard for re-saves). Uses tighter `min_cluster=4, sim_threshold=0.78` than the global default to avoid spurious abstractions from a small single-session sample.
- Timestamp recorded in `brain_meta` after each run

### Session-Count Gate
- Consolidation requires **both** conditions: >3 days since last consolidation AND ≥3 sessions since last consolidation run.
- Prevents over-consolidation in low-activity periods (e.g., a 4-day gap with only 1 session is not worth the LLM cost).
- Session count tracked in `brain_meta.sessions_since_consolidation`, reset to 0 after each run.

### Circuit Breaker
- Tracks consecutive consolidation failures in `brain_meta.consolidation_failures`.
- After 3 consecutive failures → auto-disable consolidation (sets `brain_meta.consolidation_disabled = 1`).
- Disabled state is surfaced in `brain_session("status")` output with a warning.
- Reset paths: successful consolidation run clears the counter; manual `brain_session("consolidate")` always runs regardless of disabled state and resets the circuit breaker on success.

### MEMORY.md Limit Enforcement
- After every consolidation run, `consolidate.py` checks the line count of each project's `MEMORY.md` (paths discovered via `brain_meta`).
- **Warning** at >200 lines: prints a notice recommending archival of stale entries.
- **Severe** at >250 lines: prints a strong warning with a suggestion to run `/reflect` for manual pruning.
- Does not auto-edit MEMORY.md — enforces the 200-line convention as a human-decision checkpoint.

### Consolidation File Lock
- PID-based file lock at `~/.local/share/haingt-brain/.consolidation_lock`.
- Lock file contains the PID of the owning process; stale locks (>1 hour) are automatically cleared.
- Prevents concurrent consolidation runs (e.g., two simultaneous `brain_session("start")` calls from different Claude Code windows).
- If lock is held: consolidation is skipped silently for the current session.

## 8. Memory Types

| Type | Purpose | Retention | Decay |
|------|---------|-----------|-------|
| `decision` | Choices with reasoning | Permanent | Never |
| `discovery` | Things learned | Permanent | Never |
| `pattern` | Recurring approaches | Strengthens on access | Deleted after 90 days inactive |
| `entity` | People, tools, concepts | Permanent | Never |
| `preference` | How Claude should behave | Permanent, highest priority | Never |
| `session` | Session summaries, snapshots | Last 50 full | >30 days → weekly digests |
| `tool` | MCP tool/skill metadata | Permanent | Managed by index_tools.py |

## 9. Relation Types (Knowledge Graph)

| Type | Meaning | Example |
|------|---------|---------|
| `causes` | A causes B | "high token usage" causes "slow sessions" |
| `fixes` | A solves B | "core-memory.md" fixes "token overload" |
| `contradicts` | A contradicts B | conflicting decisions |
| `relates_to` | A is related to B | general association |
| `used_in` | A is used in B | "sqlite-vec" used_in "haingt-brain" |
| `part_of` | A is part of B | "brain_save" part_of "haingt-brain" |
| `supersedes` | A replaces B | "haingt-brain" supersedes "engram" |

## 10. Semantic Toolbox

**Indexer**: `scripts/index_tools.py` · **Auto-sync**: `scripts/toolbox-sync.py` (SessionStart hook)

Indexes every capability Claude can invoke into brain as type="tool" memories with rich descriptions + Vietnamese trigger phrases. Claude finds the right tool by meaning via `brain_tools("user intent")` and the UserPromptSubmit hook's Phase-2 tool search.

**Current inventory**: ~182 capabilities
- 117 MCP tools (Google Calendar/Gmail/Drive, Todoist, Readwise, Context7, haingt-brain, civitai, st), scoped per server: global vs a project's `.mcp.json` (e.g. readwise → digital-identity, civitai + st → home-server)
- standard skills (user `~/.claude/skills` + project `.claude/skills`, protocol="skill")
- 14 native binary-bundled skills (curated `NATIVE_SKILLS`, protocol="native-skill" — no SKILL.md on disk)
- installed + enabled plugin skills (authoritative from `installed_plugins.json` + `enabledPlugins`, protocol="plugin-skill"; project-scoped plugins like godot-dev surface only in their projects)
- 3 CLI tools (`chub`)

**Scoping** (so brain_tools never suggests a tool unavailable in a project): a result surfaces only where available via `(project = ? OR project IS NULL)`. For tools, project=None means GLOBAL-ONLY, not all-projects — fixed in `search.py` (guarded by `memory_type=="tool"`) and `prompt-context.py`. Project-scoped skills/plugins/MCP servers never leak across projects.

**Reindex = atomic build-then-prune**: snapshot old tool-ids → build the full new set (random-uuid rows can't collide with the snapshot) → prune the old snapshot. Readers always see ≥ the full set (never a partial-empty toolbox); interruption-safe.

**Auto-sync**: the SessionStart hook `toolbox-sync.py` (wired in `~/.claude/settings.json`) fingerprints the skill/plugin/MCP-config surface + `index_tools.py`, then reindexes in the background only on change (flock-serialized, non-blocking). NOTE: hooks cannot enumerate live MCP *tool schemas* (CC limit — GH #6574/#26112), so project-scoped MCP servers' tools stay hand-curated in `MCP_TOOLS`.

**Manual reindex**: `cd ~/Projects/agent/mcp/haingt-brain && uv run python scripts/index_tools.py`

## 11. Data Flows

### Write (brain_save)
```
Claude → brain_save(content, type, ...) → server.py
  → tools/save.py
    → embeddings.embed_text(content)     [OpenAI API, cached]
    → db.serialize_embedding(vector)
    → INSERT memories
    → INSERT memory_vectors
    → INSERT memory_fts
    → INSERT relations (optional)
    → COMMIT
  → return {id, status}
```

### Read (brain_recall)
```
Claude → brain_recall(query, ...) → server.py
  → tools/recall.py
    → search.hybrid_search(query, ...)
      → embeddings.embed_text(query)     [OpenAI API, cached]
      → FTS5 MATCH (top 20)
      → sqlite-vec MATCH (top 20)
      → RRF combine + filter
      → UPDATE access_count
    → apply time_range filter
    → format results
  → return [{id, content, type, ...}]
```

### Auto-Capture (PostToolUse hook)
```
WebSearch/WebFetch completes
  → post-tool-use.sh receives JSON stdin
    → search-and-store.py
      → parse tool_result
      → sqlite3.connect(brain.db)        [direct, no MCP]
      → INSERT memories (type=discovery)
      → INSERT memory_fts
      → embed_text + INSERT memory_vectors [optional, graceful fail]
      → COMMIT
  → print reminder to Claude
```

### Context Injection (SessionStart)
```
Session starts
  → session-start.sh
    → brain-context.py
      → sqlite3.connect(brain.db)        [direct read]
      → SELECT recent decisions (7d, limit 3)
      → SELECT preferences (limit 3)
      → SELECT last session summary
    → print to stdout → Claude context
```

### Per-Prompt Injection (UserPromptSubmit)
```
User types message
  → prompt-context.py receives {"prompt": "..."}
    → load dedup cache (/tmp/brain-prompt-ctx-{hash}.json)
    → check token budgets (memory cap 3000, tool cap 6000)
    → embed prompt via OpenAI API (one call, reused for both phases)
    → Phase 1: General memories
      → hybrid FTS5 + vector RRF (project-scoped, type-weighted)
      → over-fetch 8 → dedup filter → top 3 → token cap
    → Phase 2: Semantic Toolbox
      → vector search type='tool' → top 3
      → skip if same tools as last prompt (skip-if-unchanged)
      → tool token cap
    → save cache (IDs, keywords, chars, tool state)
    → return {"additionalContext": "Brain context: ...\n\nRelevant tools: ..."}
  → Claude sees additionalContext in its input
```

### Conversation Snapshot (PreCompact)
```
Context approaching limit → /compact triggered
  → pre-compact.sh receives {"transcript_path": "..."}
    → pre-compact-snapshot.py
      → read transcript JSONL
      → 9-section structured extraction:
        primary request, key concepts, files/code,
        errors/fixes, problem solving, user messages,
        pending tasks, current work, next step
      → sqlite3.connect(brain.db)        [direct write]
      → INSERT memories (type=session, format=structured-v2)
      → INSERT memory_fts
      → COMMIT
      → reset prompt-context cache (dedup/caps/tool state)
  → print confirmation to Claude
  → compaction happens
  → next UserPromptSubmit re-injects fresh brain context + tools
```

## 12. File Manifest

### MCP Server (`~/Projects/agent/mcp/haingt-brain/`)
| File | Purpose |
|------|---------|
| `pyproject.toml` | Project config: mcp[cli], openai, sqlite-vec |
| `src/haingt_brain/server.py` | FastMCP entry point, 7 tool registrations, lazy DB connection |
| `src/haingt_brain/db.py` | SQLite schema, connect(), init_schema(), serialize_embedding() |
| `src/haingt_brain/embeddings.py` | OpenAI API wrapper, LRU cache (128), .env loader |
| `src/haingt_brain/search.py` | Hybrid RRF search, vector fallback, access tracking |
| `src/haingt_brain/consolidate.py` | merge_duplicates (ANN), decay_patterns, consolidate_sessions, brain_meta |
| `src/haingt_brain/tools/save.py` | brain_save implementation |
| `src/haingt_brain/tools/recall.py` | brain_recall implementation |
| `src/haingt_brain/tools/forget.py` | brain_forget implementation |
| `src/haingt_brain/tools/update.py` | brain_update implementation |
| `src/haingt_brain/tools/toolbox.py` | brain_tools (Semantic Toolbox) |
| `src/haingt_brain/tools/session.py` | brain_session (start/save/status + auto-consolidation) |
| `src/haingt_brain/tools/graph.py` | brain_graph (BFS knowledge graph traversal) |
| `scripts/index_tools.py` | Toolbox indexer (~182 caps): MCP + standard/native/plugin skills + CLI, project-scoped, atomic build-then-prune |
| `scripts/toolbox-sync.py` | SessionStart auto-sync: fingerprint surface → flock'd background reindex on change |

### Hook Scripts (`~/Projects/agent/plugins/haint-core/`)
| File | Purpose |
|------|---------|
| `hooks/hooks.json` | Hook configuration (6 events, matchers, timeouts) |
| `scripts/session-start.sh` | SessionStart: git + brain-context.py |
| `scripts/brain-context.py` | Direct SQLite read → decisions, preferences, last session |
| `scripts/prompt-context.py` | Per-prompt hybrid RRF + Semantic Toolbox, dedup, token caps |
| `scripts/post-tool-use.sh` | PostToolUse router → search-and-store.py |
| `scripts/search-and-store.py` | Auto-persist WebSearch/WebFetch/Context7 results — entropy filter + LLM distillation. Skips save entirely if no `OPENAI_API_KEY` or LLM call fails (better to lose auto-capture than store raw HTTP dumps). |
| `scripts/pre-compact.sh` | PreCompact router → pre-compact-snapshot.py |
| `scripts/pre-compact-snapshot.py` | 4-category structured extraction → brain.db + cache reset |
| `scripts/entity-extract.py` | Stop hook: regex entity extraction → brain.db type=entity |

### Configuration
| File | Purpose |
|------|---------|
| `~/.claude/core-memory.md` | Stable identity (~480 tokens), @imported by global CLAUDE.md |
| `~/Projects/agent/global/CLAUDE.md` | Brain protocol, memory boundary rules, core memory ref |
| `~/Projects/agent/global/settings.json` | `mcp__haingt-brain__*` permission wildcard |
| `~/.claude.json` | MCP server registration (via `claude mcp add`) |

## 13. Extending the System

### Add a new memory type
1. Update `CHECK` constraint in `db.py` → `type TEXT NOT NULL CHECK(type IN (...))`
2. If special retention logic needed → update `consolidate.py`
3. Test: `brain_save(content, type="newtype")`

### Add a new relation type
1. Update `CHECK` constraint in `db.py` → `relation_type TEXT NOT NULL CHECK(...)`
2. `brain_graph` already handles any relation type via BFS — no code change needed

### Add a new hook
1. Create script in `~/Projects/agent/plugins/haint-core/scripts/`
2. Register in `hooks.json` with `matcher`, `timeout`, `command`
3. For brain.db reads: `sqlite3.connect(DB_PATH)` directly
4. For brain.db writes: same pattern + optional embedding via `from haingt_brain.embeddings import embed_text`

### Index new tools
1. Standard skills (user/project `.claude/skills`) and installed plugins are auto-discovered — just add the SKILL.md / install the plugin. MCP tools, native skills, and CLI tools are hand-curated: add an entry to `MCP_TOOLS`, `NATIVE_SKILLS`, or `CLI_TOOLS` in `scripts/index_tools.py`.
2. Reindex runs automatically on the next session start (the `toolbox-sync.py` hook detects the change). Or trigger it now: `cd ~/Projects/agent/mcp/haingt-brain && uv run python scripts/index_tools.py`
3. Verify: `brain_tools("natural language query")`

## 14. Decision Log

| Decision | Rationale |
|----------|-----------|
| **Python over TypeScript** | Best ML ecosystem, first-class sqlite-vec bindings (pip install), official MCP SDK, no native addon compilation. Runtime perf irrelevant for 1-user system. |
| **OpenAI text-embedding-3-large over local MiniLM** | MTEB ~65 vs ~49 (33% better retrieval). Cost ~$0.78/month. Matryoshka dims allow future truncation 3072→1536. Fewer deps (no onnxruntime, numpy, 80MB model). |
| **RRF over weighted-average hybrid** | No weight tuning needed. Items appearing in both FTS5 and vector get exponential rank boost naturally. Proven in production search systems. |
| **Cosine threshold 0.80 (not 0.90)** | text-embedding-3-large produces lower cosine similarity than smaller models for same-meaning text. Near-duplicates measured at ~0.83. 0.90 missed obvious duplicates. |
| **FTS5 unicode61 + remove_diacritics=2** | Default tokenizer silently failed Vietnamese: "sap xep" didn't match "sắp xếp". remove_diacritics=2 handles compound diacritics (ắ, ối, ưu). Confirmed via testing. |
| **LRU cache (128) for embeddings** | Same query or content embedded multiple times per session (recall + save + consolidation). 128 entries covers typical session without memory pressure. |
| **Direct SQLite in hooks (no MCP)** | MCP uses stdio transport — hooks can't call MCP tools. But brain.db is just a file → Python scripts read/write directly. Same pattern as brain-context.py. |
| **Hybrid RRF in UserPromptSubmit hook** | Originally FTS5-only. Upgraded to embed-once + dual-phase search (general RRF + tool vector). One API call (~100ms) serves both phases. Needed for Semantic Toolbox and better recall quality. |
| **Over-fetch + post-filter dedup** | Dedup was filtering AFTER top-K cut → already-seen memories blocked new ones. Now: over-fetch 8, dedup, then top 3. Standard RAG pattern. |
| **Tool refresh per prompt (no dedup)** | Memories are cumulative context (dedup correct). Tools are per-prompt relevance — must refresh as topic shifts. Skip-if-unchanged prevents redundant system-reminders. |
| **Token caps (memory 3000, tool 6000)** | Prevents unbounded context growth in long sessions. Memory cap tracks cumulative injection. Tool cap is safety net (skip-if-unchanged is primary throttle). |
| **PreCompact resets prompt-context cache** | Compact wipes all system-reminders from context. Without cache reset, dedup thinks memories still injected → blocks re-injection of most relevant context. Session-scoped via md5(cwd) hash. |
| **No embedding in PreCompact snapshot** | Hook timeout 5s. Embedding adds 100-200ms. Snapshot content is conversation fragments, not search-optimized text. FTS5 indexing is sufficient for re-discovery. |
| **7 memory types as CHECK constraint** | Enforces data integrity at DB level. Types drive retention policy (patterns decay, others don't). Filtering by type is the most common search refinement. |
| **O(n·k) ANN for duplicate detection** | Original O(n²) pairwise loaded all embeddings into memory. ANN uses sqlite-vec's indexed search (k=6 neighbors per memory). Scales to 1000+ without performance cliff. |
| **Auto-consolidation in session_start** | Manual consolidation (brain_session("consolidate")) was never called — same compliance problem as Engram. 7-day auto-trigger ensures cleanup happens. |
| **Semantic Toolbox (brain_tools)** | At 13 skills, verbose descriptions = ~1,080 always-on tokens. At 200 skills: impossible. brain_tools routes by meaning, descriptions reduced to labels (~50 chars). |
| **Core memory over @imports** | @personality.md + @goals.md = ~4,537 tokens every session. core-memory.md = ~480 tokens. Deep context loaded on demand via file paths. |
| **PreCompact transcript snapshot** | /compact destroys context. transcript_path (JSONL) is available to hooks. Extract last 20 messages → save to brain → re-inject on SessionStart. Seamless continuity. |
| **9-section PreCompact format (structured-v2)** | 4-category format (structured-v1) was generic. Claude Code's own compact prompt uses 9 specific sections. Mirroring that structure produces higher-fidelity snapshots and better re-injection relevance. |
| **FTS5 pre-filter before embedding** | OpenAI embedding API adds ~100-150ms per prompt. Most prompts have clear keywords — FTS5 alone returns ≥3 good results. Pre-filter skips API on 80%+ of prompts, cuts latency ~40%. |
| **General memory skip-if-unchanged** | In focused work sessions, consecutive prompts pull the same top-3 memories. Re-injection wastes 500-750 tokens per prompt. ID comparison is O(1) and catches the common case. |
| **Session-count gate for consolidation** | Time-only gate (3 days) triggered on quiet weeks with 1-2 sessions — not worth LLM cost. Session count adds meaningful signal: need both time AND activity to justify consolidation run. |
| **Circuit breaker for consolidation** | Repeated API/DB errors during consolidation can silently degrade the system. 3-strike disable surfaces the problem and prevents runaway failure loops. Manual override via brain_session("consolidate") always works. |
| **PID-based file lock for consolidation** | Multiple Claude Code windows can run simultaneously, each starting a session. Without a lock, concurrent consolidation runs corrupt merge operations (both see same duplicates, both delete one copy). |
| **Staleness suffix in brain-context.py** | Injected memories had no recency signal — a 30-day-old decision looked identical to a 1-day-old one. `(Nd ago)` suffix gives Claude immediate signal to weight recent context higher, zero extra tokens. |
| **LLM distillation in entity-extract.py** | Regex extraction catches entities but not intent or confidence. gpt-5.4-nano post-processing refines top 5 into atomic facts with scores. Eliminates false-positive entities (e.g., common words matched by regex). |
| **Search-and-Store auto-capture** | Every un-saved WebSearch result = knowledge lost. PostToolUse hook auto-persists to brain. Future brain_recall finds past searches without re-searching. |
| **Per-prompt context injection** | SessionStart injects brain context once. UserPromptSubmit injects per message. More targeted — Claude sees relevant memories for each specific question. |

## 15. Known Limitations

| Limitation | Context | Impact |
|-----------|---------|--------|
| **No HTTP transport** | MCP uses stdio only. Hooks can't call MCP tools, must use direct SQLite. | Low — direct SQLite works. Would matter if multiple processes needed concurrent MCP access. |
| **Pre-compact snapshot has no embedding** | Saves to FTS only, not vector store. | Medium — snapshot is discoverable via keyword search but not semantic search. Acceptable tradeoff for hook speed. |
| **UserPromptSubmit embedding cost** | Each user message triggers one OpenAI embedding API call (~$0.001). | Low — cost is negligible. Falls back to FTS5-only if API unavailable. |
| **transcript_path format undocumented** | JSONL structure reverse-engineered from observation. Claude Code may change it. | Medium — pre-compact-snapshot.py could break on format change. Graceful fallback to text reminder. |
| **Single-process embedding cache** | LRU cache is in-memory per MCP server process. Hook scripts that import embeddings.py get a separate cache. | Low — hooks rarely embed (only search-and-store). MCP server handles most embedding. |
| **Consolidation runs synchronously** | consolidate_all() runs during brain_session("start"). If brain has 1000+ memories, this adds startup latency. | Low currently (~70 memories). Will matter at scale. |
| **No backup/export mechanism** | brain.db is a single file. No scheduled backup, no export to JSON/markdown. | Medium — data loss risk if disk fails. Should add periodic backup. |
| **Hook stdout JSON parsing fragile** | UserPromptSubmit expects specific JSON format. Any print() to stdout corrupts the JSON. | Low — scripts are careful. But debugging is hard (stderr not visible). |

## 16. Future Improvements

| Improvement | Signal (when to do it) | Effort |
|-------------|------------------------|--------|
| **Add embedding to pre-compact snapshots** | When brain_recall misses relevant conversation context that was captured by pre-compact | Small — add embed_text() call in pre-compact-snapshot.py |
| **Periodic brain.db backup** | First time any data loss concern arises, OR when brain >200 memories | Small — cron job: `cp brain.db brain.db.bak` |
| ~~**Stop hook for entity extraction**~~ | ✅ Implemented — `entity-extract.py` via Stop hook, regex-based extraction | Done |
| **HTTP/SSE transport** | When multiple processes need simultaneous MCP access, OR when hooks need to call brain_tools() | Large — add FastAPI/uvicorn alongside stdio, dual transport |
| **Weighted RRF (tunable k)** | When search quality noticeably degrades for specific query patterns | Small — make rrf_k configurable in brain_meta, expose via brain_session("config") |
| **Embedding dimension reduction** | When brain.db >100MB AND storage is a concern | Small — change DIMENSIONS to 1536 or 768, re-embed all (Matryoshka supports this) |
| **Tool log tracking** | When debugging tool failures becomes a recurring pain point | Medium — PostToolUse hook logs all tool calls to brain.db, not just WebSearch |
| **LLM-augmented docstrings for Toolbox** | When brain_tools returns wrong tool for clear queries AND manual descriptions aren't enough | Medium — use LLM to enrich tool descriptions before indexing (course L3 pattern) |
| **Async consolidation** | When consolidation takes >5s during brain_session("start") | Medium — move to background thread or separate cron process |
| **Cross-device sync** | When Hải works from multiple machines | Large — replicate brain.db via Syncthing or add cloud backend |
| **Memory importance scoring** | When brain has 500+ memories AND recall returns too many low-value results | Medium — add importance field, factor into RRF scoring |
| **Conversation memory table** | When pre-compact snapshots aren't sufficient AND full conversation replay is needed | Large — would require parsing transcript_path on every message, significant storage |

## 17. Belief Revision & Contradiction Handling

**Problem.** The store is similarity-retrieval over independent chunks. When a newer
memory corrects an older one ("Wednesday ate banana" → "couldn't buy banana, ate apple
instead"), both rows survive every dedup gate (similar but not identical), recall ranks
them with no recency signal (`ORDER BY rrf_score*(0.5+0.5*importance)` has no time term),
so both co-surface and the reader can't tell which is current.

The audit (1948 memories) split this into three problems, only one a true contradiction:
- **P1 — stale-but-unlinked:** ~35 memories self-declare `[SUPERSEDED]`/`RETIRED` in content
  but carry no `supersedes` edge, so `SUPERSEDED_FILTER` never hides them.
- **P2 — duplicate-spam:** the same fact saved many times (one decision saved 7×).
- **P3 — genuine belief-revision:** small; many are "true-then, state-changed" (finance
  versions, growth metrics) that should be KEPT and flagged, not hidden.

**Two edge semantics.** `supersedes` HIDES the target (`SUPERSEDED_FILTER`); `contradicts`
SURFACES both (read-time flag). A genuine revision defaults to `contradicts` and only
escalates to `supersedes` when explicit reversal language is present ("instead", "no longer",
"reversed", "RETIRED", "now corrected") — preserving history by default, hiding only when a
value is plainly wrong.

**Anti-series guard (the load-bearing safety).** Cosine cannot separate the classes —
duplicate-spam (0.90-0.99), formulaic phase-log series (0.89-0.94), and real corrections
(0.83-0.93) overlap, and gpt-5.4-nano was measured to OVER-CALL phase logs (`P-Combat-a` vs
`P-Combat-b`) as corrections. `contradiction.is_series_pair()` (regex on
`EXECUTED|GREEN|ADR-\d+|Tier \d|P-\d|LANDED|milestone` + dated-measurement series) runs BEFORE
the LLM and short-circuits such pairs to `unrelated`. Conservative — when in doubt it returns
True, protecting project history.

**Defense in depth (4 layers; `contradiction.py` is the shared engine):**

| Layer | Where | What | Default |
|-------|-------|------|---------|
| Read-time conflict-surface | `search.cluster_conflicts` + `recall.py` | Tags the newer of a same-subject divergent pair `_current`, the older `_superseded_candidate "Nd ago"`. Annotation only. First consumer of the `contradicts` edge. The live net for every unlinked pair. | ON |
| Write-time near-dup guard | `save.py` | Same-type cosine ≥ 0.92 → skip the insert (stops P2 at source). | ON (`BRAIN_NEAR_DUP_GUARD`) |
| Write-time auto-revision | `save.py` → `contradiction.classify_pair` | On an in-band sibling, create a `contradicts`/`supersedes` edge. | OFF (`BRAIN_AUTO_SUPERSEDE`) until re-audit |
| Batch supersede_pass | `consolidate.py` | Back-catalog cleaner. NOT in `SAFE_STRATEGIES`, NEVER deletes (vs `merge_duplicates` 0.95 which does), dry-run-first. | explicit `strategies={"supersede"}` |

**The brake.** `brain_unlink(source, target, relation_type)` removes a single edge (restoring
the target's importance for `supersedes`) — the reversible undo for any auto/batch link. It
ships and is tested before any auto-writer runs.

**Tools/scripts.** `scripts/backfill_supersede.py` (P1 — direction from passive/active marker
grammar, ANN-resolves id-less cases), `scripts/cleanup_p2_dupes.py` (label unify + reversible
dedup), `scripts/audit_contradictions.py` (the re-audit measuring residual
unlinked-contradiction; the gate for flipping `BRAIN_AUTO_SUPERSEDE` live).

**Env flags:** `BRAIN_NEAR_DUP_GUARD` (true), `BRAIN_NEAR_DUP_THRESHOLD` (0.92),
`BRAIN_AUTO_SUPERSEDE` (false), `BRAIN_SUPERSEDE_MIN_CONF` (0.85),
`BRAIN_SUPERSEDE_MAX_PER_RUN` (40), `BRAIN_CONTRADICTION_MODEL` (= `JUDGE_MODEL`).

**Decay interaction.** Decay is keyed on `days_since_access`, not creation, and is currently
disabled (the curve would prune 32% — pending retune). The contradiction bug *sabotages*
decay: serving both rows keeps the stale one "accessed" so it never sinks — which is why the
edge/flag must stop the serve first; decay is downstream. The read-time recency cue is a
LOCAL tie-break within a conflict cluster (not a global ORDER BY term), so it does not
double-count with decay's access axis once decay returns. Back-fill-demoted ids are logged to
`brain_meta.p1_backfill_affected_ids` for exclusion from the decay re-tune.
