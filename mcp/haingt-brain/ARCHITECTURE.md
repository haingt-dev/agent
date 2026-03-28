# haingt-brain — Architecture Document

> Last updated: 2026-03-27
> Status: Production (single-user, daily use)
> Origin: Applied concepts from DeepLearning.AI "Building Memory-Aware Agents" course

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
│     (FTS5 query)         │    │  brain_session           │
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
Search memories using hybrid semantic + keyword search.
```
Params: query (str), type? (str), project? (str), k (int=5), time_range? (str, e.g. '-7 days')
Returns: [{id, content, type, tags, project, created_at, access_count, relevance}]
Flow: embed query → FTS5 top-20 + vector top-20 → RRF combine → filter → update access_count
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
  status → return {total_memories, by_type, created_last_7_days, total_sessions, sessions_with_summary}
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
- **Output**: Git branch + recent commits + memory-bank brief + brain context
- **brain-context.py**: Direct SQLite read → recent decisions (3, 7 days), preferences (3), last session summary (1)
- **Target**: ~300-500 tokens injected

### UserPromptSubmit → `prompt-context.py`
- **Trigger**: Every user message (>10 chars, not slash commands)
- **Input**: `{"prompt": "user's message"}`
- **Output**: `{"additionalContext": "Brain context: [type] content..."}` or empty
- **Mechanism**: FTS5-only query (no embedding API), top 2 results, 200 chars each
- **Performance**: <50ms (no network call)

### PostToolUse → `post-tool-use.sh` + `search-and-store.py`
- **Trigger**: After WebSearch or WebFetch completes
- **Input**: `{"tool_name": "...", "tool_input": {...}, "tool_result": "..."}`
- **Action**: Parse result → write to brain.db as type=discovery, tags=[tool_type, "auto-captured"]
- **Embedding**: Attempted (graceful fail → FTS-only is still useful)
- **Output**: Reminder to brain_save for deeper analysis

### PreCompact → `pre-compact.sh` + `pre-compact-snapshot.py`
- **Trigger**: Before context compaction
- **Input**: `{"transcript_path": "/path/to/transcript.jsonl"}`
- **Action**: Parse last 20 user+assistant messages → build snapshot (max 2000 chars) → write to brain.db as type=session, tags=["pre-compact", "auto-snapshot"]
- **No embedding**: FTS-only (hook must stay fast)
- **Why**: Prevents context loss on /compact — brain-context.py re-injects on next SessionStart

### PreToolUse (Bash) → `pre-tool-safety.sh`
- **Not brain-related** — safety validation only

## 7. Consolidation

Three strategies, all in `consolidate.py`:

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

### Auto-trigger
- `brain_session("start")` checks `brain_meta.last_consolidation`
- If >7 days since last run → `consolidate_all()` automatically
- Timestamp recorded in `brain_meta` after each run

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

**Script**: `scripts/index_tools.py`

Indexes all available capabilities into brain as type="tool" memories with rich descriptions and Vietnamese trigger phrases. Claude finds the right tool by meaning via `brain_tools("user intent")`.

**Current inventory**: 62 capabilities
- 49 MCP tools: Google Calendar (9), Gmail (7), Todoist (17), Readwise (8), Context7 (2), haingt-brain (7)
- 13 Skills: alfred, research, token-optimize, gen-image, fix-issue, ship, story, finance, mentor, inbox, learn, reflect, upwork

**Re-index**: `cd ~/Projects/agent/mcp/haingt-brain && uv run python scripts/index_tools.py`

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
    → sqlite3.connect(brain.db)          [direct read]
    → FTS5 MATCH (words from prompt)
    → top 2 results (exclude type=tool)
    → return {"additionalContext": "Brain context: ..."}
  → Claude sees additionalContext in its input
```

### Conversation Snapshot (PreCompact)
```
Context approaching limit → /compact triggered
  → pre-compact.sh receives {"transcript_path": "..."}
    → pre-compact-snapshot.py
      → read transcript JSONL
      → extract last 20 user+assistant messages
      → build snapshot (max 2000 chars)
      → sqlite3.connect(brain.db)        [direct write]
      → INSERT memories (type=session, tags=pre-compact)
      → INSERT memory_fts
      → COMMIT
  → print confirmation to Claude
  → compaction happens
  → SessionStart fires again → brain-context.py re-injects
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
| `scripts/index_tools.py` | One-time indexer: 49 MCP tools + 13 skills → brain |

### Hook Scripts (`~/Projects/agent/plugins/haint-core/`)
| File | Purpose |
|------|---------|
| `hooks/hooks.json` | Hook configuration (5 events, matchers, timeouts) |
| `scripts/session-start.sh` | SessionStart: git + memory-bank + brain-context.py |
| `scripts/brain-context.py` | Direct SQLite read → decisions, preferences, last session |
| `scripts/prompt-context.py` | Per-prompt FTS5 query → additionalContext JSON |
| `scripts/post-tool-use.sh` | PostToolUse router → search-and-store.py |
| `scripts/search-and-store.py` | Auto-persist WebSearch/WebFetch results to brain.db |
| `scripts/pre-compact.sh` | PreCompact router → pre-compact-snapshot.py |
| `scripts/pre-compact-snapshot.py` | Read transcript → snapshot → brain.db |

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
1. Add entry to `MCP_TOOLS` or `SKILLS` list in `scripts/index_tools.py`
2. Run: `cd ~/Projects/agent/mcp/haingt-brain && uv run python scripts/index_tools.py`
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
| **FTS5-only in UserPromptSubmit hook** | Hook fires every user message. Embedding API call (~100ms) would add noticeable latency. FTS5 query: <5ms, good enough for broad recall. |
| **No embedding in PreCompact snapshot** | Hook timeout 5s. Embedding adds 100-200ms. Snapshot content is conversation fragments, not search-optimized text. FTS5 indexing is sufficient for re-discovery. |
| **7 memory types as CHECK constraint** | Enforces data integrity at DB level. Types drive retention policy (patterns decay, others don't). Filtering by type is the most common search refinement. |
| **O(n·k) ANN for duplicate detection** | Original O(n²) pairwise loaded all embeddings into memory. ANN uses sqlite-vec's indexed search (k=6 neighbors per memory). Scales to 1000+ without performance cliff. |
| **Auto-consolidation in session_start** | Manual consolidation (brain_session("consolidate")) was never called — same compliance problem as Engram. 7-day auto-trigger ensures cleanup happens. |
| **Semantic Toolbox (brain_tools)** | At 13 skills, verbose descriptions = ~1,080 always-on tokens. At 200 skills: impossible. brain_tools routes by meaning, descriptions reduced to labels (~50 chars). |
| **Core memory over @imports** | @personality.md + @goals.md = ~4,537 tokens every session. core-memory.md = ~480 tokens. Deep context loaded on demand via file paths. |
| **PreCompact transcript snapshot** | /compact destroys context. transcript_path (JSONL) is available to hooks. Extract last 20 messages → save to brain → re-inject on SessionStart. Seamless continuity. |
| **Search-and-Store auto-capture** | Every un-saved WebSearch result = knowledge lost. PostToolUse hook auto-persists to brain. Future brain_recall finds past searches without re-searching. |
| **Per-prompt context injection** | SessionStart injects brain context once. UserPromptSubmit injects per message. More targeted — Claude sees relevant memories for each specific question. |

## 15. Known Limitations

| Limitation | Context | Impact |
|-----------|---------|--------|
| **No HTTP transport** | MCP uses stdio only. Hooks can't call MCP tools, must use direct SQLite. | Low — direct SQLite works. Would matter if multiple processes needed concurrent MCP access. |
| **Pre-compact snapshot has no embedding** | Saves to FTS only, not vector store. | Medium — snapshot is discoverable via keyword search but not semantic search. Acceptable tradeoff for hook speed. |
| **UserPromptSubmit FTS5 is broad** | OR-matching top 5 words → may return low-relevance results. | Low — worst case: slightly irrelevant additionalContext. Claude ignores if not useful. |
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
| **Stop hook for entity extraction** | When Hải notices Claude forgetting key entities across sessions despite brain system | Medium — agent hook type (Haiku subagent), extracts entities from response, writes to brain |
| **HTTP/SSE transport** | When multiple processes need simultaneous MCP access, OR when hooks need to call brain_tools() | Large — add FastAPI/uvicorn alongside stdio, dual transport |
| **Weighted RRF (tunable k)** | When search quality noticeably degrades for specific query patterns | Small — make rrf_k configurable in brain_meta, expose via brain_session("config") |
| **Embedding dimension reduction** | When brain.db >100MB AND storage is a concern | Small — change DIMENSIONS to 1536 or 768, re-embed all (Matryoshka supports this) |
| **Tool log tracking** | When debugging tool failures becomes a recurring pain point | Medium — PostToolUse hook logs all tool calls to brain.db, not just WebSearch |
| **LLM-augmented docstrings for Toolbox** | When brain_tools returns wrong tool for clear queries AND manual descriptions aren't enough | Medium — use LLM to enrich tool descriptions before indexing (course L3 pattern) |
| **Async consolidation** | When consolidation takes >5s during brain_session("start") | Medium — move to background thread or separate cron process |
| **Cross-device sync** | When Hải works from multiple machines | Large — replicate brain.db via Syncthing or add cloud backend |
| **Memory importance scoring** | When brain has 500+ memories AND recall returns too many low-value results | Medium — add importance field, factor into RRF scoring |
| **Conversation memory table** | When pre-compact snapshots aren't sufficient AND full conversation replay is needed | Large — would require parsing transcript_path on every message, significant storage |
