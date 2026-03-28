# haint-core

Core Claude Code plugin: 6 hooks for brain-powered memory, safety, and context management.

## Hooks

| Hook | Script | Purpose |
|------|--------|---------|
| **SessionStart** | `session-start.sh` | Git branch + recent commits, loads `.memory-bank/brief.md`, injects brain context (decisions, preferences, last session) |
| **UserPromptSubmit** | `prompt-context.py` | Per-prompt brain injection: hybrid RRF search (general memories) + Semantic Toolbox (relevant tools). Dedup, token caps, skip-if-unchanged |
| **PreToolUse (Bash)** | `pre-tool-safety.sh` | Two-tier safety — `deny` catastrophic commands, `ask` for risky operations |
| **PostToolUse** | `post-tool-use.sh` → `search-and-store.py` | Auto-persist WebSearch/WebFetch/Context7 results to brain.db as discoveries |
| **PreCompact** | `pre-compact.sh` → `pre-compact-snapshot.py` | 4-category structured extraction before compaction + reset prompt-context cache |
| **Stop** | `entity-extract.py` | Regex entity extraction (projects, skills, technologies) from Claude responses |

## Key Mechanisms

### Prompt Context (UserPromptSubmit)
- **Embed once, search twice**: one OpenAI API call serves both general memory and tool search
- **Over-fetch + post-filter dedup**: search 8 → filter already-injected → top 3. Deduped slots filled by next-best results
- **Tool refresh**: fresh top-3 tools per prompt (no dedup), skip-if-unchanged to avoid redundant system-reminders
- **Token caps**: memory 3000 chars, tools 6000 chars — prevents context bloat in long sessions
- **Cache**: `/tmp/brain-prompt-ctx-{md5(cwd)[:8]}.json` — tracks IDs, keywords, chars, tool state. TTL 2h, reset on compact

### PreCompact Cache Reset
Compact wipes all system-reminders from context window. PreCompact resets the prompt-context dedup cache (session-scoped) so important memories and tools re-inject after compaction.

## Memory Architecture

Session context is layered:
1. **Global CLAUDE.md** — behavioral instructions + `@import` for identity/career context
2. **Project CLAUDE.md** — project-specific instructions
3. **brief.md** — project identity (loaded by SessionStart hook)
4. **Auto-memory (MEMORY.md)** — session learnings (managed by Claude Code)
5. **haingt-brain** — cross-project semantic memory (MCP server, 7 tools)

## Install

```bash
claude plugin marketplace add ~/Projects/agent
claude plugin install haint-core@haint-marketplace --scope user
```
