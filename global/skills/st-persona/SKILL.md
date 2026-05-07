---
name: st-persona
description: "Convert a SillyTavern character into a user persona — migrates visuals, lorebook link, avatar."
argument-hint: "<CharName> [--remove]"
allowed-tools: Bash, AskUserQuestion, Read, mcp__st__st_get_settings, mcp__st__st_save_settings_path, mcp__st__st_get_character
---

# ST Persona — Character → Persona Migration

Hai's flow: import char from Chub/Janitor → find interesting → decide "this is my persona" → convert.

ST has no built-in equivalent for `char_prompts` on the persona side, so visual baseline must move INTO `persona_description` text (LLM extracts during Mode 4). This skill automates the migration.

**Usage:**
```
/st-persona Parasite           # convert, KEEP original char file (default safe)
/st-persona Parasite --remove  # convert AND delete original char file
```

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
ST_SCRIPTS = /home/haint/Projects/home-server/scripts
```

---

## Phase 0: Parse + Validate

Extract from `$ARGUMENTS`:
- `CharName` = first non-flag token
- `remove_original` = `--remove` flag present

Validate:
- `$ST_DATA/characters/{CharName}.png` must exist (source character)
- `$ST_DATA/User Avatars/{CharName} (Persona).png` must NOT exist — if it does, ask user: overwrite, rename, or abort?

---

## Phase 1: Gather Source Data

**Read existing char_prompts via MCP** (path-based, may be empty/missing if /st-setup not yet run):

```python
import json

try:
    char_visual_pos = json.loads(mcp__st__st_get_settings(path=f"extension_settings.sd.character_prompts.{CharName}"))
except Exception:
    char_visual_pos = ''  # key absent

try:
    char_visual_neg = json.loads(mcp__st__st_get_settings(path=f"extension_settings.sd.character_negative_prompts.{CharName}"))
except Exception:
    char_visual_neg = ''

print(f"char_prompts found: {bool(char_visual_pos)}")
```

**Read char card via MCP** — replaces legacy PNG tEXt parse:

```python
resp = mcp__st__st_get_character(name=CharName)
card = json.loads(resp) if isinstance(resp, str) else resp
d = card.get('data', card)  # spec v3 nests under 'data', v2 flat
# Use d['name'], d['description'], d['personality'], d['scenario'], d.get('creator_notes', '')
```

**Branch logic:**
- If `char_visual_pos` exists → use it for visual block
- Else → LLM analyze card description and extract visual booru tags on the fly (positive only — negatives less critical for persona)

---

## Phase 2: Transform Card → Persona Description

Char card text ≠ persona description. Need to **transform**, not just copy:

| Aspect | Char card has | Persona needs |
|--------|---------------|---------------|
| **POV** | 3rd person ("she thinks X", "he reacts by Y") | 1st person OR neutral self-insert framing |
| **RP mechanics** | "Always speaks formal Japanese", "Never breaks character" | Removed — these direct LLM behavior, not persona identity |
| **Backstory** | Multi-paragraph history, lore, relationships | Trimmed to identity-defining basics |
| **Behavioral lock-ins** | "Submissive type, always defers" | Removed unless Hai genuinely wants persona to act this way |
| **Pronouns lock** | Card may assume "{{user}} is male" or vice versa | Verified compatible — flag conflicts |
| **Visual** | Often buried in prose | Explicit at top + Booru tag block |

**LLM transformation task:**

Given the raw char description, produce a **compact persona description** with this structure:

```
Name: {name}
Age: {age}
Gender: {gender}
Appearance: {1-3 sentences — visual identity, body, ethnicity, style}
Demeanor: {1-2 sentences — first-impression vibe, how others perceive {{user}}}
Social context: {1 sentence — role/position that shapes how NPCs treat {{user}}}
{Optional 1-2 lines of personality keywords if Hai wants persona to feel a certain way}

[Visual reference for image generation:
{char_visual_pos from char_prompts, or LLM-derived if not set}]
```

**Why "Demeanor" + "Social context" sections?**
When other {{char}} encounters this persona in a new chat, they need enough signal to react authentically. Without these, {{char}} treats {{user}} as a blank slate. Examples:

- *Naoko persona*: Demeanor = "sweet, oblivious, easily flustered". Social context = "Japanese housewife, late 30s, lives in suburban home". → A {{char}} like a sleazy stranger reads this as "easy target", a {{char}} like a kind neighbor reads "warm, caring lady". Both react authentically.
- *Demon Lord persona*: Demeanor = "imposing, speaks with authority, cold gaze". Social context = "ruler of the seven hells". → {{char}} reactions auto-calibrate (fear/reverence/defiance).

These traits SHAPE how {{char}} reacts but DON'T direct {{char}}'s behavior verbatim. Difference:
- ✅ "Demeanor: sweet and oblivious" → {{char}} chooses how to react
- ❌ "Other characters always find {{user}} attractive" → directing {{char}}'s response (RP-mechanic, drop)

**What to drop during transformation:**
- LLM directive language ("always X", "never Y", "responds with Z")
- Extended backstory (parents, occupation history, past trauma) unless identity-critical
- Combat/skill descriptions
- World-building paragraphs (those belong in lorebook)
- POV-locked phrases ({{user}} assumed male/female that conflicts)

**What to keep:**
- Name, age, gender, ethnicity
- Physical appearance (height, body, hair, eyes, distinctive features)
- 1-2 personality anchors if Hai wants persona to read a certain way (e.g., "sweet, oblivious")
- Current outfit/style if defining

**Show user with AskUserQuestion:**

Display side-by-side:
```
ORIGINAL CARD DESCRIPTION:
{first 500 chars of card description...}

PROPOSED PERSONA DESCRIPTION:
{transformed compact version}
```

Options:
- "Use proposed"
- "Use original verbatim"
- "Let me edit"

If "edit": ask user to paste their preferred version.

**Pronoun lock check:**
Scan card for hardcoded `{{user}}` gender assumptions ("{{user}}'s cock", "her boobs press against him", etc.). If found, flag to Hai: *"Card assumes {{user}} = {male/female}. Persona inherits this — OK or remove?"*

---

## Phase 3: Migrate (via MCP, no container restart)

`mcp__st__st_save_settings` routes through ST's save handler — no race with `saveSettingsDebounced`. Container stays up.

### File operations (PNG copy — still direct file ops)

```python
import shutil, os

CHARACTERS = "/home/haint/Projects/home-server/sillytavern/data/default-user/characters"
USER_AVATARS = "/home/haint/Projects/home-server/sillytavern/data/default-user/User Avatars"

src_png = f"{CHARACTERS}/{CharName}.png"
persona_avatar = f"{CharName} (Persona).png"
dst_png = f"{USER_AVATARS}/{persona_avatar}"

os.makedirs(USER_AVATARS, exist_ok=True)

# Copy avatar to User Avatars (direct file op — no API for this)
shutil.copy2(src_png, dst_png)

# Remove original IF --remove flag
if remove_original:
    os.remove(src_png)
    # Note: expressions folder characters/{CharName}/ stays — user may want to restore later
```

### Settings edits via path-based MCP writes

Each binding is one surgical call — no full-tree round trip needed.

```python
import json

# Lookup existing lorebook (small list at wrapper level)
world_names = json.loads(mcp__st__st_get_settings(path="world_names")) or []
linked_book = CharName if CharName in world_names else ''

persona_desc_obj = {
    'description': PERSONA_DESC,   # text built in Phase 2
    'position': 0,                 # 0 = before char defs
    'depth': 2,                    # @ depth 2
    'role': 0,                     # 0 = system role
    'lorebook': linked_book,       # auto-link if lorebook exists
    'title': '',
    'connections': []
}

# 1. Register persona name → avatar mapping
mcp__st__st_save_settings_path(path=f"power_user.personas.{persona_avatar}", value=CharName)

# 2. Persona description object
mcp__st__st_save_settings_path(path=f"power_user.persona_descriptions.{persona_avatar}", value=persona_desc_obj)

# 3. Cleanup char_prompts ONLY if --remove (char file deleted → no longer a {{char}})
if remove_original:
    # Setting to empty string blanks the entry without breaking the dict shape
    mcp__st__st_save_settings_path(path=f"extension_settings.sd.character_prompts.{CharName}", value="")
    mcp__st__st_save_settings_path(path=f"extension_settings.sd.character_negative_prompts.{CharName}", value="")
    print(f"Cleared char_prompts['{CharName}'] (char file deleted)")
else:
    print(f"Kept char_prompts['{CharName}'] (char file still usable as {{{{char}}}} in other chats)")
```

**Ask user with AskUserQuestion:** "Set this as active persona now?" → if yes:
```python
mcp__st__st_save_settings_path(path="user_avatar", value=persona_avatar)
```

No container restart needed.

---

## Phase 4: Report

```
=== Persona Migration: {CharName} → User Persona ===

✓ Avatar copied: characters/{CharName}.png → User Avatars/{CharName} (Persona).png
[✓ Original char file removed (--remove flag) | ⚠ Original kept — char_prompts intact for future {{char}} RP]
✓ Persona description: {len(PERSONA_DESC)} chars (visual block embedded)
[✓ Lorebook linked: {CharName}.json | ⊘ No lorebook found — create with /st-setup --lore first]
[✓ Removed char_prompts['{CharName}'] (--remove flag) | ⊘ Kept char_prompts (char still available for {{char}} use)]
[✓ Set as active persona | ⊘ Active persona unchanged]

Next:
- Reload ST (Ctrl+Shift+R)
- Top-right persona dropdown → select '{CharName}' if not auto-active
- Test image gen with Mode 4: persona visual tags should appear in prompt
```

---

## Edge Cases

| Case | Handling |
|------|----------|
| char_prompts not set yet | LLM derives visual tags from card description on the fly |
| Persona avatar already exists | Ask user: overwrite, rename (e.g., "(Persona 2)"), or abort |
| Lorebook doesn't exist | Skip lorebook link, suggest `/st-setup --lore` first |
| Expression folder exists | Keep — `characters/{CharName}/` survives even if char file removed (some forks render persona expressions) |
| User wants to revert | Manual: delete persona avatar, copy from char folder back. (Not implementing reverse — rare case, error-prone) |

---

## Related Skills

- `/st-setup <CharName>` → run first to establish char_prompts + (optional) lorebook before converting
- Recommended flow:
  ```
  /st-setup Parasite --all       # baseline + 28 expressions + lorebook
  [RP for a while, decide it's the persona]
  /st-persona Parasite --remove  # migrate, delete original
  ```
