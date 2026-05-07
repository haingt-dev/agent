---
name: st-audit
description: "Audit current SillyTavern config — explain settings, surface non-defaults, recommend changes for a goal. Read-only."
argument-hint: "[<setting-key> | goal \"<text>\"]"
allowed-tools: Bash, Read, mcp__st__st_get_settings, mcp__st__st_save_settings_path
---

# ST Audit — Discover & Explain Current Config

Read-only audit of SillyTavern configuration. Surfaces what's currently configured, why each knob matters, and what to change for a given goal. **Does NOT modify anything** — feeds context into conversation so user decides next move.

**Why this exists:** ST has 100KB+ settings.json + 10+ extensions, each with sub-config. Most users don't know which knobs are load-bearing vs cargo-cult. This skill closes the discovery gap.

**Usage:**
```
/st-audit                          # full sweep, grouped by domain
/st-audit <setting-key>            # explain one setting (current value + what it does + safe range)
/st-audit goal "<natural language>" # goal-driven: list relevant settings + recommendations
```

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
SETTINGS = $ST_DATA/settings.json   # fallback only; prefer mcp__st__st_get_settings
PLAYBOOK = /home/haint/Projects/home-server/sillytavern/PROMPT-PLAYBOOK.md
```

## Knowledge Source Order

1. `PROMPT-PLAYBOOK.md` — 33 verified gotchas, the canonical local knowledge base. Always cite gotcha number when relevant.
2. **Live settings via `mcp__st__st_get_settings()`** — current state (ground truth). Works while ST runs (no file-lock risk). Falls back to `Read SETTINGS` if MCP unavailable (ST container down).
3. ST source defaults (read from `/home/node/app/public/scripts/extensions/<name>/index.js` via `podman exec` if needed).
4. Built-in skill knowledge below (curated facts about load-bearing knobs).

If knowledge sources conflict → live settings wins for "current value", playbook wins for "why it matters".

---

## Mode 1: Full Sweep (`/st-audit` no args)

Read each domain via path-based MCP calls (full-tree read returns 70KB+, exceeds Claude's MCP token cap). Each call returns a JSON string of the subtree at that path.

```python
import json

# Per-domain reads (compose a full audit without ever loading the full tree)
sd          = json.loads(mcp__st__st_get_settings(path="extension_settings.sd"))
memory      = json.loads(mcp__st__st_get_settings(path="extension_settings.memory"))
conn_mgr    = json.loads(mcp__st__st_get_settings(path="extension_settings.connectionManager"))
power_user  = json.loads(mcp__st__st_get_settings(path="power_user"))
ext_all     = json.loads(mcp__st__st_get_settings(path="extension_settings"))

# Disabled extensions are stored per-extension as <extension>.disabled (true/false),
# not aggregated at a single key. Walk extension_settings for {disabled: true} entries.
disabled_exts = [k for k, v in ext_all.items() if isinstance(v, dict) and v.get("disabled") is True]
```

Produce a grouped report. Skip categories where everything is at default — focus attention on non-defaults.

### Categories to audit

**[1] Image Generation** (`extension_settings.sd`)
- `source` — Forge URL backend
- `sampler` (expect `Euler` for NoobAI, NOT `Euler a`)
- `scheduler` (expect `karras`)
- `steps`, `scale` (CFG)
- `prompt_prefix` (must start with quality tags)
- `prompts['4']` — Mode 4 template length + first line
- `character_prompts` — count entries + list keys
- `character_negative_prompts` — count entries

**[2] Memory / Summary** (`extension_settings.memory`)
- `source` (`main` = uses primary LLM, `extras` = separate)
- `prompt_builder` (`0`=DEFAULT/generateQuietPrompt, `1`=RAW_BLOCKING, `2`=RAW_NON_BLOCKING)
- `SkipWIAN` (true = exclude WIAN from summary prompt)
- `promptInterval` (`0` = manual-only, N = auto every N messages)
- `position`, `depth`, `role` (where summary injects)
- `promptWords` (max summary length)

**[3] Connection Profiles** (`extension_settings.connectionManager.profiles`)
- List each profile: name, preset, model, api
- Active profile (`extension_settings.connectionManager.selectedProfile`)

**[4] RP Behavior** (`power_user.*`)
- `instruct.preset_name` + `instruct.enabled`
- `context.preset` (context template)
- `max_context`, `response_length`
- `prefer_character_prompt` / `prefer_character_jailbreak`
- `user_avatar` (active persona)

**[5] Extensions State**
- Walk `extension_settings.<name>.disabled` — list every extension with `disabled: true`
- Highlight notable ones: `LALib` (slash command lib), `GuidedGenerations-Extension`, `memory`

**[6] Quick Replies** (`quickReplyApi.config.setList`)
- Per set: name, button count, auto-execute hooks

**[7] Persona** (`power_user.personas`, `power_user.persona_descriptions`)
- Active persona + linked lorebook
- Total persona count

### Output format

```
## ST Config Audit — [date]

### 🟢 Image Gen
- sampler: Euler ✓ (correct for NoobAI epsilon-pred)
- scheduler: karras ✓
- steps: 30 ✓ (>=28 required, gotcha 5.X)
- scale: 5 ✓ (CFG 4-5 for NoobAI)
- prompt_prefix: "masterpiece, best quality..." ✓
- Mode 4 template: 2144 chars (v8.2 — 5 hard rules only)
- char_prompts: 4 entries [Naoko, Parasite, Helena Lin, Klee]

### 🟡 Memory/Summary
- source: main ✓ (uses primary LLM)
- prompt_builder: 1 (RAW_BLOCKING) ✓ (gotcha 5.33)
- SkipWIAN: true ✓
- promptInterval: 0 ✓ (manual-only, gotcha 5.33)
- position: ?, depth: ?, role: ?

### 🔴 Extensions
- DISABLED: GuidedGenerations-Extension (diagnostic state, can re-enable)
- ENABLED: LALib ✓ (required for /dom workaround)

### Connection Profiles
| Name | Preset | Model | API |
|------|--------|-------|-----|
| ...  | ...    | ...   | ... |

Active: DeepSeek daily

### Findings
- Non-default values: N
- Settings flagged: M
- Suggested next checks: [...]
```

Use `🟢` (looks correct), `🟡` (notable but intentional), `🔴` (worth attention).

---

## Mode 2: Single Setting (`/st-audit <key>`)

Parse `<key>` — accept dot-path (`sd.sampler`) or last segment (`prompt_builder` matches `extension_settings.memory.prompt_builder`).

If ambiguous (multiple matches) → list candidates, ask user to disambiguate.

### Output

```
## Setting: extension_settings.memory.prompt_builder

**Current value**: 1 (RAW_BLOCKING)

**What it does**: Controls which generation path the Summarize extension uses.
- 0 (DEFAULT) → generateQuietPrompt → routes through prompt manager → injects WIAN, persona, char defs into summary prompt
- 1 (RAW_BLOCKING) → generateRaw → bypasses prompt manager → clean summary prompt only ✓ recommended
- 2 (RAW_NON_BLOCKING) → generateRaw async → faster but less reliable for long chats

**Why current value matters**: Setting 0 caused WIAN contamination in Magnum's summary output (gotcha 5.33). Switched to 1 to route through generateRaw.

**Depends on / affects**:
- Pairs with `SkipWIAN: true` (redundant safety — RAW_BLOCKING already bypasses WIAN)
- If you switch back to 0, restore SkipWIAN check

**Source**: PROMPT-PLAYBOOK.md gotcha 5.33; ST source `/home/node/app/public/scripts/extensions/memory/index.js:507`

**Safe to change**: Only if changing summary architecture. Current value is load-bearing.
```

---

## Mode 3: Goal-Driven (`/st-audit goal "<text>"`)

Parse natural language goal. Match against known goal categories:

| Goal pattern | Relevant settings |
|-------------|-------------------|
| "image gen quality" / "ảnh đẹp hơn" | sd.sampler, scheduler, steps, scale, prompt_prefix, char_prompts, Mode 4 template |
| "summary clean" / "summary không bị bẩn" | memory.prompt_builder, SkipWIAN, promptInterval, source |
| "RP voice" / "ít interrupt" / "tone" | instruct preset, context preset, char card PHI, AN, model temperature |
| "model switching" / "profile" | connectionManager.profiles, selectedProfile, /profile slash command |
| "function calling" / "tool calling" | enableFunctionCalling, model api support, prompts |
| "context window" / "token budget" | max_context, response_length, summary depth, lorebook entry budgets |
| "persona setup" / "user persona" | power_user.personas, persona_descriptions, user_avatar, linked lorebook |
| "lorebook" / "world info" | worlds/*.json, character lorebook linkage, depth, position, scanDepth |

For each match, output:
1. Current state of relevant settings (live read)
2. Common recommendations (with rationale + gotcha refs)
3. Risks of changing each
4. Suggested order of changes (start with lowest-risk)

### Output

```
## Goal: "summary không bị bẩn"

Matched category: Memory/Summary

### Current state
- prompt_builder: 1 (RAW_BLOCKING) ✓
- SkipWIAN: true ✓
- promptInterval: 0 (manual-only) ✓
- source: main ✓

### Status
**Already optimized.** All 4 load-bearing settings match recommended values from gotcha 5.33.

### If still seeing problems
- Check active model — DeepSeek tends to write prose-style continuations even with RAW_BLOCKING (RP-tuned). Switch to Magnum profile via QR `[📝 Summary]` button.
- Check chat metadata — old `extra.memory` entries from prior bad summaries can contaminate next regen. Inspect `chats/<char>/<chat>.jsonl`.

### Reference
PROMPT-PLAYBOOK.md gotcha 5.33; section 8.1 (Summary Workflow)
```

---

## Built-in Knowledge (curated facts)

Embedded so skill works without re-reading PROMPT-PLAYBOOK every invocation. Update this list when new gotchas added.

**Image gen knobs**
- NoobAI XL = epsilon-prediction → Euler/Karras/CFG5/steps≥28. NOT Euler a.
- vpred models broken on ai-dock Forge image (gotcha 5.X) — stick with epsilon checkpoints.
- prompt_prefix MUST start with `masterpiece, best quality, newest, absurdres, highres,`
- Mode 4 (Last Message) template = `prompts['4']`. Current: v8.2, 2144 chars, 5 hard rules. Magnum picks tags from booru training.
- char_prompts key = char filename WITHOUT `.png` (gotcha: `getCharaFilename()` strips ext)

**Memory/Summary**
- prompt_builder=1 (RAW_BLOCKING) bypasses prompt manager → clean summary prompt
- promptInterval=0 → manual only (recommended). Auto-trigger contaminates context unpredictably.
- DeepSeek RP-tuned → ignores "STOP. END OF ROLEPLAY" directive. Switch to Magnum for clean summary.
- Bad prior summary in `extra.memory` chat metadata → contaminates next regen. Clear it before retry.

**STscript / Slash commands**
- `is_send_press` lock → `/summarize` via QR pipe silent fails (gotcha 5.33)
- LALib `/dom action=click "#memory_force_summarize"` bypasses lock via native DOM event
- Profile switch via `/profile timeout=5000 <name>` — needs delay before next command

**Extensions**
- Third-party extensions live in `data/default-user/extensions/`, NOT `public/extensions/third-party/` (legacy path)
- LALib provides `/dom`, `/regex`, `/runc`, `/db`, `/fetch`, etc.
- GuidedGenerations adds Quick Reply hooks on GENERATION_AFTER_COMMANDS

**Persona vs Character**
- char_prompts has NO persona equivalent → visual tags must embed in `persona_descriptions[avatar].description` text
- Active persona = `power_user.user_avatar` (filename of avatar PNG)
- Persona-bound lorebook = `power_user.persona_descriptions[avatar].lorebook`

---

## Implementation Steps

For any mode:

1. **Read live state**:
   ```python
   import json
   with open("/home/haint/Projects/home-server/sillytavern/data/default-user/settings.json") as f:
       s = json.load(f)
   ```

2. **Read PROMPT-PLAYBOOK.md** (skim relevant sections only — file is ~700 lines):
   - Mode 1 full sweep → read sections 1-3 + 8 + 8.1 + 10 (gotcha index)
   - Mode 2 single setting → grep playbook for the setting key
   - Mode 3 goal → match goal to playbook section, read that section

3. **Cross-reference current value vs recommended**:
   - Match → 🟢
   - Different but documented choice → 🟡
   - Different and undocumented → 🔴 (flag for user attention)

4. **Output report** (markdown table or structured sections, scannable)

5. **NEVER modify settings.json** — this skill is read-only by design.

---

## Edge Cases

| Case | Handling |
|------|----------|
| settings.json not found | ST data not at expected path. Check container running, paths correct. |
| ST container running while reading | Safe — read-only. But warn that values may change if user edits via UI mid-audit. |
| Setting key ambiguous in mode 2 | List candidates, ask user to pick. |
| Goal text doesn't match any category | Show available categories, ask user to rephrase or pick closest. |
| PROMPT-PLAYBOOK.md missing | Skill still works using built-in knowledge above; note playbook unavailable. |

---

## Why This Skill, Not MCP Server

- Pain is **discovery** (cognitive overload), not **control** (mechanical access)
- Skill = read knowledge + explain. MCP server = expose ST operations to external agent. Different layers.
- Skill 1-2h to build. MCP server 5-10h. Phase 1 capacity wins.
- Skill outputs feed Claude Code conversation → user decides changes → applies via existing skills (`/st-setup`, `/st-persona`, `/st-arc-save`) or direct edits with confirmation.

When to revisit MCP server: only if specific pain emerges that direct-file + skills can't cover.
