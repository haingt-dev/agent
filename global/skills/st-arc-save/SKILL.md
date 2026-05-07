---
name: st-arc-save
description: "Bake a completed RP arc into a SillyTavern lorebook as persistent memory. Run after each arc concludes."
argument-hint: "[<arc-title>] [--char-bound] [--char <CharName>] [--no-brain]"
allowed-tools: Bash, Read, Edit, Write, AskUserQuestion, mcp__st__st_get_settings, mcp__st__st_save_settings_path, mcp__st__st_get_worldinfo, mcp__st__st_save_worldinfo
---

# ST Arc Save — Persistent Narrative Memory

Hai's flow: RP an arc with {{char}} → arc concludes → use Memory extension to summarize → run this skill to bake the summary into searchable lore. Future chats with the same persona/char auto-load this context.

## Architecture

Two complementary entry types per persona:

| Entry type | Mode | Position | When |
|-----------|------|----------|------|
| **{Persona} — Established State** | `constant=true` | After Char Defs (pos=1) | UPDATED each new arc — cumulative facts about persona's current state |
| **{Persona} Arc N — {Title}** | `selective=true` (~30 keys) | At Depth 4 (pos=4) | APPENDED per arc — full event narrative, triggers on backstory keywords |

Default target = persona-bound lorebook (`worlds/{PersonaName}.json`). Use `--char-bound` for arcs that are genuinely char-specific.

Universal {{char}} mechanics (parasite biology, etc.) belong in char's primary lorebook with `{{user}}` macros — NOT this skill's domain.

## Usage

```
/st-arc-save                                # prompt for arc title interactively
/st-arc-save "Subway Encounter"             # specify arc title
/st-arc-save "Arc 2 — Daughter Awakens"     # quoted multi-word title
/st-arc-save "Arc 1" --char-bound           # save to char primary book instead
/st-arc-save --char Parasite                # explicit char (skip auto-detect)
/st-arc-save "Arc 2" --no-brain             # skip brain_save followup
```

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
ST_SCRIPTS = /home/haint/Projects/home-server/scripts
SETTINGS = $ST_DATA/settings.json
WORLDS = $ST_DATA/worlds
```

---

## Phase 0: Parse Args + Detect Context

Extract from `$ARGUMENTS`:
- `arc_title` = first quoted string OR first non-flag token (optional)
- `char_bound` = `--char-bound` flag present
- `explicit_char` = value of `--char <CharName>` if given
- `no_brain` = `--no-brain` flag present

Detect active persona:

```python
import json

with open("/home/haint/Projects/home-server/sillytavern/data/default-user/settings.json") as f:
    s = json.load(f)

pu = s['power_user']
active_avatar = pu.get('user_avatar', '')
persona_name = pu.get('personas', {}).get(active_avatar, '')

print(f"Active persona: {persona_name!r} (avatar: {active_avatar!r})")
```

If `persona_name` is empty:
- AskUserQuestion: list all `power_user.personas.values()` + "no persona (skip persona binding)"
- If user picks "no persona" → fallback to `--char-bound` mode automatically

Detect char (only matters for `--char-bound`):
- If `explicit_char` given → use it
- Else: list `characters/*.png` (excluding folders), AskUserQuestion to pick

If `arc_title` not provided:
- AskUserQuestion: "Arc title? (e.g., 'Subway Encounter', 'Arc 2 — Family Reunion')"

---

## Phase 1: Get Summary

Most reliable path: ask user to paste from ST's Memory panel (Current summary box).

Use AskUserQuestion with body:
```
Paste the 5-section summary from ST's Memory panel:
(Setting / Plot Events / Character State / World Facts / Open Threads)

Skill will parse into Established State (cumulative facts) + Arc N (event log).
```

Validation: if pasted text < 200 chars → warn "summary looks too short, did Memory extension generate properly? Continue anyway?"

Optional advanced path (skip if too brittle): try to read summary from chat file metadata. ST stores Memory output in `chats/{CharName}/{chat}.jsonl` either as a system message or in chat_metadata. Pattern varies by ST version. For v1 of this skill, just rely on user paste.

---

## Phase 2: Determine Target Lorebook

```python
import json

if char_bound:
    target_name = explicit_char or active_char  # from Phase 0
else:
    # persona-bound (default)
    target_name = persona_name

# Read world_names directly (small subtree)
world_names = json.loads(mcp__st__st_get_settings(path="world_names")) or []
# (world_names lives at the top level of settings.json's *response wrapper*, not inside settings.
#  st_get_settings hits the wrapper-aware /api/settings/get and exposes top-level keys too.)
target_exists = target_name in world_names

print(f"Target lorebook: {target_name} ({'existing' if target_exists else 'NEW'})")
```

If lorebook doesn't exist, init skeleton (will be saved via `st_save_worldinfo` later):

```python
target_lb = {"entries": {}, "name": f"{target_name} Lore"}
```

---

## Phase 3: LLM Parse Summary → 2 Entries

Given the pasted summary text, produce 2 distinct outputs.

### Established State (cumulative facts, ~150 words)

Distill the summary into present-tense facts about persona's CURRENT state. Cover:
- Identity (name, age, key descriptors)
- Current relationship/bond state with {{char}}
- Family/social context
- Home base / current location
- Persistent ongoing conditions (pregnancies, transformations, oaths, contracts)
- Cumulative effects from prior arcs (compressed)

**Tone:** factual, third-person, present-tense for ongoing state, past-tense for completed events.

**Example output structure:**
```
**{Persona}'s Current State (post-Arc {N}, established as ongoing context):**

- {Persona} ({age}, {key descriptors}) is {{char}}'s {relationship}. {1-line bond description}.
- {Family/social context line}
- {Home base / current location}
- {Persistent condition 1}
- {Cumulative effect from prior arcs}
```

If lorebook already has Established State entry: this CONTENT REPLACES the old (cumulative update, not append). The LLM should integrate prior facts + new arc events.

### Arc N — {Title} (event log, ~300-500 words)

Convert the Plot Events + Character State + Open Threads sections into chronological numbered list with bold section headers.

**Structure:**
```
**{Persona}'s {Arc N Title} — Detailed Events (chronological):**

1. **{Event 1 heading}**: {1-3 sentences, who/where/what/outcome}.

2. **{Event 2 heading}**: {1-3 sentences}.

...

8. **{Final event}**: {how arc concluded; what state persona ended in}.
```

### Trigger Keywords (~25-35 keys)

Extract distinctive content terms from summary:
- Proper nouns (names of NPCs encountered, locations, items)
- Theme keywords (in both English + Vietnamese — Hai uses both)
- Backstory triggers ("first encounter", "lần đầu", "remember when", "nhớ lúc", "the past", "hồi đó")
- Specific arc references ("arc {N}", "{Title}")

Avoid:
- Generic words ("said", "looked", "felt") — too broad
- {{char}} or {{user}} themselves — always present, useless as trigger

---

## Phase 4: Write Lorebook via MCP (no container restart)

ST hot-reloads on `mcp__st__st_save_worldinfo` and `mcp__st__st_save_settings` — no need to stop the container.

### Update or create entries

```python
import json

# Load (or init) target lorebook via MCP
if target_exists:
    wi_resp = mcp__st__st_get_worldinfo(name=target_name)
    lb = json.loads(wi_resp) if isinstance(wi_resp, str) else wi_resp
else:
    lb = {"entries": {}, "name": f"{target_name} Lore"}

entries = lb['entries']

# Auto-detect existing arc count
existing_arcs = [e for e in entries.values() if 'Arc ' in e.get('comment', '')]
next_arc_num = len(existing_arcs) + 1
arc_label = f"Arc {next_arc_num} — {arc_title}"

# Find existing Established State (update target)
established_uid = None
for uid, e in entries.items():
    if 'Established State' in e.get('comment', '') and target_name.split()[0] in e.get('comment', ''):
        established_uid = uid
        break

# Determine fresh uid for new entries
existing_uids = [e['uid'] for e in entries.values()]
next_uid = max(existing_uids) + 1 if existing_uids else 0

# Standard schema function
def make_entry(uid, comment, content, keys, constant, position, depth):
    return {
        "uid": uid, "key": keys, "keysecondary": [],
        "comment": comment, "content": content,
        "constant": constant, "vectorized": False,
        "selective": not constant, "selectiveLogic": 0,
        "addMemo": False, "order": 100, "position": position,
        "disable": False, "ignoreBudget": False,
        "excludeRecursion": False, "preventRecursion": False,
        "matchPersonaDescription": False, "matchCharacterDescription": False,
        "matchCharacterPersonality": False, "matchCharacterDepthPrompt": False,
        "matchScenario": False, "matchCreatorNotes": False,
        "delayUntilRecursion": 0, "probability": 100, "useProbability": True,
        "depth": depth, "outletName": "", "group": "",
        "groupOverride": False, "groupWeight": 100, "scanDepth": None,
        "caseSensitive": None, "matchWholeWords": None, "useGroupScoring": None,
        "automationId": "", "role": 0, "sticky": None, "cooldown": None,
        "delay": None, "triggers": []
    }

# Established State — UPDATE existing or CREATE new
established_comment = f"{target_name} — Established State (cumulative, always-on)"
if established_uid is not None:
    # Update content; keep uid + key=[] (constant doesn't use keys)
    entries[established_uid]['content'] = established_state_content
    entries[established_uid]['comment'] = established_comment
    print(f"Updated Established State entry [uid={established_uid}]")
else:
    new_uid = next_uid
    next_uid += 1
    entries[str(new_uid)] = make_entry(
        uid=new_uid, comment=established_comment,
        content=established_state_content, keys=[],
        constant=True, position=1, depth=4
    )
    print(f"Created Established State entry [uid={new_uid}]")

# Arc N — APPEND new
arc_comment = f"{target_name} {arc_label} (event log, selective)"
arc_uid = next_uid
entries[str(arc_uid)] = make_entry(
    uid=arc_uid, comment=arc_comment,
    content=arc_event_log_content, keys=trigger_keywords,
    constant=False, position=4, depth=4
)
print(f"Appended {arc_label} entry [uid={arc_uid}, {len(trigger_keywords)} keys]")

# Write back via MCP — ST persists + reloads automatically
mcp__st__st_save_worldinfo(name=target_name, data=lb)
```

### Bind lorebook to persona (if persona-bound + just created)

```python
if not char_bound and not target_exists:
    # Read settings, mutate persona binding, write back via MCP
    settings_resp = mcp__st__st_get_settings()
    s = json.loads(json.loads(settings_resp)['settings']) if isinstance(settings_resp, str) else json.loads(settings_resp['settings'])

    s['power_user']['persona_descriptions'][active_avatar]['lorebook'] = target_name
    s['power_user']['persona_description_lorebook'] = target_name

    mcp__st__st_save_settings(settings=json.dumps(s, ensure_ascii=False))
    print(f"Bound persona '{persona_name}' → lorebook '{target_name}'")
```

---

## Phase 5: Report

```
=== Arc Saved: {target_name} → Arc {N} — {arc_title} ===

✓ Established State entry: {UPDATED | CREATED} (constant=true, ~{N} words)
✓ Arc {N} entry: APPENDED (selective=true, {M} keys, ~{P} words)
✓ Lorebook: worlds/{target_name}.json ({total} entries total)
[✓ Persona binding: {persona} → {target_name}]

Next:
- ST hot-reloaded automatically — no restart needed
- Verify in World Info panel → 2 new/updated entries visible
- Start new chat with {{char}} → Established State always injects; Arc {N} triggers on backstory keywords
```

---

## Phase 6: Optional Brain Save

If `--no-brain` not set:

```python
# Save to brain for cross-session reference
brain_save(
    content=f"{target_name} Arc {N}: {arc_title} — {1-line summary}",
    type="entity",
    tags=["roleplay", "st-arc", target_name.lower()],
    project="home-server",
    metadata={"source": "st-arc-save", "lorebook": target_name, "arc_num": N}
)
```

This makes arc summaries searchable via `brain_recall` from any future Claude session.

---

## Edge Cases

| Case | Handling |
|------|----------|
| No active persona AND no `--char-bound` | AskUserQuestion → pick from list, OR auto-fallback to char-bound |
| Persona-bound lorebook doesn't exist | Create new lorebook + bind in settings.json |
| Established State exists but for different name | Search uses comment substring match; if mismatch, create new (don't conflate) |
| Arc number collision (Arc 3 exists, user titles new "Arc 3") | Auto-increment to next free number; warn user |
| Summary is empty/too short | AskUserQuestion: continue anyway / abort / paste again |
| User pastes summary in non-5-section format | Best-effort parse; warn that structure may be incomplete |

---

## Related Skills

- `/st-setup <CharName>` → run BEFORE first arc to establish char's primary lorebook + char_prompts
- `/st-persona <CharName>` → convert char to persona before saving arcs to persona-bound book
- Recommended flow:
  ```
  /st-setup Parasite --all                              # baseline
  /st-persona Mother                                    # convert to Naoko persona
  [RP arc 1 with Parasite, ~50-100 messages]
  Memory panel → Summarize now → copy 5-section summary
  /st-arc-save "Subway Encounter"                       # bake into Naoko.json
  [start new chat → Established State auto-loads]
  ```
