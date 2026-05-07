---
name: st-setup
description: "Onboard a SillyTavern character — set SD visual baseline + audit. Optional: redistribute card fields, generate expressions, build lorebook."
argument-hint: "<CharName> [--adv] [--expr] [--lore] [--all] | --audit"
allowed-tools: Bash, AskUserQuestion, Read, mcp__st__st_get_settings, mcp__st__st_save_settings_path, mcp__st__st_get_character, mcp__st__st_list_characters, mcp__st__st_save_worldinfo
---

# ST Setup — Character Onboarding

One command to fully onboard a new SillyTavern character: extract visual baseline from card data, set char_prompts, audit SD settings, generate 28 expression sprites, create World Info lorebook.

**Usage:**
```
/st-setup Parasite            # baseline + audit only
/st-setup Parasite --adv      # + redistribute description into Advanced Definition fields (PNG patch)
/st-setup Parasite --expr     # + generate 28 expression sprites
/st-setup Parasite --lore     # + create World Info lorebook
/st-setup Parasite --all      # all features (--adv + --expr + --lore)
/st-setup --audit             # settings audit only, no char
```

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
ST_SCRIPTS = /home/haint/Projects/home-server/scripts
FORGE_URL = http://localhost:7860
```

## Critical Gotcha

ST's `getCharaFilename()` strips `.png` extension before key lookup in `character_prompts`. Key MUST be `"Parasite"` not `"Parasite.png"`. Source: `utils.js:1349` regex `/\.[^/.]+$/`.

---

## Phase 0: Parse Arguments

Extract from `$ARGUMENTS`:
- `CharName` = first non-flag token (e.g., `"Parasite"`)
- Flags: `--adv`, `--expr`, `--lore`, `--all` (enables `--adv` + `--expr` + `--lore`), `--audit`

Resolve flags:
- `adv = '--adv' in args or '--all' in args`
- `expr = '--expr' in args or '--all' in args`
- `lore = '--lore' in args or '--all' in args`

Validate:
- If `--audit` only: skip to Phase 2 audit step
- If CharName given: check `$ST_DATA/characters/{CharName}.png` exists. If not: list available chars from `$ST_DATA/characters/*.png` and ask user to pick.

---

## Phase 1: Read Card + Propose char_prompts

Read the character card via MCP — replaces legacy PNG tEXt binary parsing.

```python
import json

resp = mcp__st__st_get_character(name=char_name)  # accepts "Parasite" or "Parasite.png"
card = json.loads(resp) if isinstance(resp, str) else resp

# ST returns spec v3 fields at top level + nested 'data' for spec v2 compat
d = card.get('data', card)
print("NAME:", d.get('name', char_name))
print("DESCRIPTION:", d.get('description', '')[:2000])
print("PERSONALITY:", d.get('personality', '')[:500])
print("SCENARIO:", d.get('scenario', '')[:500])
```

**Fallback** (if MCP unavailable / ST container down): parse PNG tEXt chunks directly with the legacy approach. See git history of this file pre-2026-05-08 for the binary-parse snippet.

**LLM task — analyze card text and generate:**

From the character description + personality + scenario, produce:

**char_prompts_positive**: Visual booru tags ONLY. Include:
- Species/type (e.g., `pink_slug`, `1girl`, `monster`, `android`)
- Key visual features (colors, size, notable anatomy)
- Defining physical characteristics
- NO personality, behavior, or non-visual traits

**char_prompts_negative**: Tags that should NOT appear for this char:
- If creature: `humanoid, human_body`
- If female: `masculine, male`
- If small: `giant, large`

**Present to user with AskUserQuestion:**
```
Proposed SD baseline for {CharName}:

Positive: {proposed_positive}
Negative: {proposed_negative}

Use as-is, or paste your edits?
```

Options: `["Use as-is", "Let me edit"]`

If "Let me edit": ask user to paste corrected versions.

---

## Phase 1.5: Advanced Definition (`--adv` or `--all`)

**SKIP this phase if `--adv` not set.**

Goal: redistribute bloated `description` content into specialized character card fields, then patch the PNG tEXt chunk. Each field has ONE job — no overlap, no duplication.

### Field role boundaries

| Field | Purpose | Should contain |
|-------|---------|----------------|
| `description` | WHAT char IS | Visual, species/role, backstory, universal mechanics, core nature |
| `personality` | Demeanor distillation | 5-10 keyword adjectives/phrases |
| `scenario` | WHERE/WHEN this chat starts | Situational opener (2-3 sentences) |
| `mes_example` | HOW char speaks | 5-7 dialogue exchanges (1500-3000 chars) |
| `depth_prompt` | WHAT MUST HOLD per turn | 2-4 imperative behavioral anchors |

**Anti-overlap rule**: Every sentence pulled from description MUST land in exactly one new field. Every sentence kept in description MUST NOT have a more-specific home. No content lives in two places.

### Step A: Read full card state

```python
import struct, base64, json

PNG_PATH = f"{ST_DATA}/characters/{char_name}.png"
BACKUP_PATH = f"{PNG_PATH}.bak"

with open(PNG_PATH, 'rb') as f:
    png_data = f.read()

card = None
chunk_start = None
chunk_keyword = None
i = 8
while i < len(png_data) - 12:
    length = struct.unpack('>I', png_data[i:i+4])[0]
    chunk_type = png_data[i+4:i+8].decode('ascii', errors='ignore')
    chunk_data = png_data[i+8:i+8+length]
    if chunk_type == 'tEXt':
        keyword, _, text = chunk_data.partition(b'\x00')
        if keyword in (b'ccv3', b'chara'):
            card = json.loads(base64.b64decode(text).decode('utf-8'))
            chunk_start = i
            chunk_keyword = keyword
            break
    i += 8 + length + 4

d = card.get('data', card)  # V1 vs V3 format

# Audit current state
print(f"=== Current Advanced Definition state ===")
for field in ['description', 'personality', 'scenario', 'mes_example', 'first_mes', 'system_prompt']:
    val = d.get(field, '')
    state = f"{len(val)} chars" if val else "EMPTY"
    print(f"  {field}: {state}")
dp = d.get('extensions', {}).get('depth_prompt', {})
print(f"  depth_prompt: {len(dp.get('prompt',''))} chars, depth={dp.get('depth',0)}, role={dp.get('role','system')}")
```

### Step B: LLM redistribution pass

Read full `description` (no truncation — entire field). Produce FIVE outputs:

**1. trimmed_description** — original minus all redistributed content
- KEEP: visual, species/type, backstory, universal mechanics, core nature
- REMOVE: personality adjectives, scenario sentences, "{{char}} will/won't" rules, dialogue snippets
- Target reduction: 30-60% smaller

**2. personality** — 5-10 keyword adjectives/phrases extracted
- Format: comma-separated. Example: `"manipulative, predatory, tender-masked, ancient, evolved psychologist, calculating"`

**3. scenario** — review existing + merge any scenario lines pulled from description
- Format: 2-3 sentences. Skip update if existing scenario already strong.

**4. mes_example** — expand to 5-7 exchanges (1500-3000 chars)
- Source: existing weak examples + dialogue snippets pulled from description + LLM-generated additions in matching voice
- Format: `{{char}}: "..." \n{{char}}: "..."` (separate examples with blank lines or `<START>`)

**5. depth_prompt.prompt** — 2-4 imperative rules from "{{char}} will/won't" sentences
- Condense to imperative form. Example: `"Maintain telepathic voice. Never break 3rd-person narration. You are a predator wearing affection — calculation under sweetness."`
- Use `depth=2, role='system'`

### Step C: Present redistribution diff to user

Use AskUserQuestion with full preview. Show:

```
=== Redistribution proposal for {CharName} ===

DESCRIPTION
  before: {N} chars
  after:  {M} chars  [-{N-M}]

PULLED OUT
  → personality: "{full content}"
  → scenario:    {"{first 100 chars}..." | "(no change)"}
  → depth_prompt: "{full content}" (depth=2, role=system)
  → mes_example:  "{first 200 chars}..." ({total} chars, {N} exchanges)

KEPT IN DESCRIPTION
  - Visual: {1-line summary}
  - Backstory: {1-line summary}
  - Universal mechanics: {1-line summary}
  - Core nature: {1-line summary}
```

Options:
- `"Apply all (Recommended)"` — patch PNG with all 5 changes
- `"Edit before applying"` — ask user to paste manual edits per field
- `"Skip Advanced Def"` — abort Phase 1.5, continue to Phase 2

### Step D: Patch PNG tEXt chunk

**CRITICAL: ST MUST be stopped before patching PNG.** ST holds character cards in memory and will overwrite the file when the user opens the card or triggers any save event — silently reverting all patches.

```bash
cd /home/haint/Projects/home-server && ./scripts/down.sh sillytavern
```

Verify ST is down before proceeding:

```python
import subprocess
r = subprocess.run(['podman','ps','--format','{{.Names}}'], capture_output=True, text=True)
assert 'sillytavern' not in r.stdout, "ST still running — abort patch!"
```

```python
import struct, zlib, shutil

# Backup
shutil.copy2(PNG_PATH, BACKUP_PATH)
print(f"Backup: {BACKUP_PATH}")

# Update V2 path (card.data.X)
d['description'] = trimmed_description
d['personality'] = personality_content
d['scenario']    = scenario_content     # only if changed
d['mes_example'] = mes_example_content
if 'extensions' not in d:
    d['extensions'] = {}
d['extensions']['depth_prompt'] = {
    'prompt': depth_prompt_content,
    'depth': 2,
    'role': 'system'
}

# Re-encode + SYNC V1 top-level fields
# CRITICAL: V2 cards (chara_card_v2 / ccv3) keep mirror fields at root level (card.X).
# ST frontend reads from V1 top-level paths — failing to sync them = silent UI bug
# (UI shows old data even though card.data.X is patched correctly).
if 'data' in card:
    card['data'] = d
    # Sync V1 mirror fields with V2 data
    for field in ['description', 'personality', 'scenario', 'mes_example', 'first_mes']:
        if field in d:
            card[field] = d[field]
else:
    # V1-only card (rare, legacy)
    card = d

new_json = json.dumps(card, ensure_ascii=False, separators=(',', ':'))
new_b64 = base64.b64encode(new_json.encode('utf-8'))

# Rebuild tEXt chunk: length(4) + "tEXt"(4) + data + crc(4)
new_chunk_payload = chunk_keyword + b'\x00' + new_b64
new_length_bytes = struct.pack('>I', len(new_chunk_payload))
new_crc_bytes = struct.pack('>I', zlib.crc32(b'tEXt' + new_chunk_payload) & 0xFFFFFFFF)
new_chunk = new_length_bytes + b'tEXt' + new_chunk_payload + new_crc_bytes

# Replace old chunk
old_length = struct.unpack('>I', png_data[chunk_start:chunk_start+4])[0]
old_chunk_total_size = 4 + 4 + old_length + 4  # length + type + data + crc
new_png = png_data[:chunk_start] + new_chunk + png_data[chunk_start + old_chunk_total_size:]

with open(PNG_PATH, 'wb') as f:
    f.write(new_png)

print(f"✓ Patched {PNG_PATH}")
print(f"  Restore: cp {BACKUP_PATH} {PNG_PATH}")
```

**MANDATORY: Patch ST disk cache file** — PNG patch alone is invisible to UI.

ST's `endpoints/characters.js:182` `readCharacterData()` reads from cache first (memoryCache → diskCache → parse PNG only on miss). UI feeds from cache. Patches to PNG file alone never reach UI because data flow is one-directional: UI → write file + cache; file changes → readCharacterData reads cache, not PNG. Even cache-nuke + ST restart can result in regenerated cache containing stale data (mechanism unclear, empirically observed).

**Fix: patch BOTH PNG (Step D above) AND cache file's `value` field with same patched JSON.**

```python
import os, json, hashlib

CACHE_DIR = "/home/haint/Projects/home-server/sillytavern/data/_cache/characters"

# Find existing cache entry for this character (key = path-mtime_ms)
target_cache_path = None
target_cache_outer = None
for fname in os.listdir(CACHE_DIR):
    fpath = os.path.join(CACHE_DIR, fname)
    try:
        with open(fpath) as f:
            outer = json.load(f)
        if f"{char_name}.png" in outer.get('key', ''):
            # Found existing cache entry - patch it
            target_cache_path = fpath
            target_cache_outer = outer
            break
    except: pass

if target_cache_path is None:
    # No cache yet — create one keyed by current PNG mtime
    mtime_ms = os.path.getmtime(PNG_PATH) * 1000
    cache_key = f"data/default-user/characters/{char_name}.png-{mtime_ms}"
    fname = hashlib.sha256(cache_key.encode()).hexdigest()
    target_cache_path = os.path.join(CACHE_DIR, fname)
    target_cache_outer = {'key': cache_key, 'value': ''}

# Write patched JSON into cache value field
target_cache_outer['value'] = json.dumps(card, ensure_ascii=False)

with open(target_cache_path, 'w') as f:
    json.dump(target_cache_outer, f, ensure_ascii=False)

print(f"✓ Patched cache: {target_cache_path}")
```

**Only patch entries for the patched character** (preserve cache for unrelated characters).

Then restart ST:

```bash
cd /home/haint/Projects/home-server && ./scripts/up.sh sillytavern
```

**Note**: If `--adv` is paired with `--expr` or other flags that need ST running (Forge/expression gen), restart is mandatory before those phases. If `--adv` runs alone, restart is still required so user can verify in UI.

### Step E: User verification reminder

Print:
```
Advanced Definition applied. Verify in ST:
  1. Reload ST (Ctrl+Shift+R)
  2. Open {CharName} character card → Advanced Definition tab
  3. Confirm all 5 fields populated, description trimmed
  4. If anything looks wrong: cp {CharName}.png.bak {CharName}.png
```

---

## Phase 2: Write settings + Audit (path-based MCP, no restart)

`mcp__st__st_save_settings_path` routes through ST's save handler — no `saveSettingsDebounced` race, no container restart, no full-tree round trip.

**Set char_prompts surgically:**

```python
key = "Parasite"  # NO extension (critical!)
mcp__st__st_save_settings_path(
    path=f"extension_settings.sd.character_prompts.{key}",
    value=POSITIVE_TAGS
)
mcp__st__st_save_settings_path(
    path=f"extension_settings.sd.character_negative_prompts.{key}",
    value=NEGATIVE_TAGS
)
```

**Audit checklist** — read just the SD subtree (~5KB), then auto-fix any mismatches via surgical writes:

```python
import json
sd = json.loads(mcp__st__st_get_settings(path="extension_settings.sd"))

checks = [
    ("sampler", "Euler"),                # not "Euler a"
    ("scheduler", "karras"),
    ("steps", lambda v: v >= 28),
    ("scale", lambda v: v in (4, 5)),
]
prefix_rule = "masterpiece, best quality, newest, absurdres, highres,"
mode4_rule  = "[END ROLEPLAY"

# Auto-fix any mismatch
fixes = []
if sd.get("sampler") != "Euler":
    mcp__st__st_save_settings_path(path="extension_settings.sd.sampler", value="Euler")
    fixes.append(f"sampler: {sd.get('sampler')!r} → 'Euler'")
# (apply similar fixes for scheduler/steps/scale/prompt_prefix/prompts.4)
```

Each failed check is one surgical write. No full-tree write needed.

No container restart needed.

Print audit report:
```
✓ sampler: Euler
✓ steps: 30
✗ scale was 7 → fixed to 5
✓ prompt_prefix: masterpiece...
✓ Mode 4 template: [END ROLEPLAY]
✓ char_prompts[Parasite]: pink_slug, small_creature, ...
```

---

## Phase 3: Expression Sprites (`--expr` or `--all`)

**28 standard emotion labels (distilbert go-emotions):**
`admiration, amusement, anger, annoyance, approval, caring, confusion, curiosity, desire, disappointment, disapproval, disgust, embarrassment, excitement, fear, gratitude, grief, joy, love, nervousness, optimism, pride, realization, relief, remorse, sadness, surprise, neutral`

**Prerequisite check:**
```python
import requests
try:
    r = requests.get("http://localhost:7860/sdapi/v1/sd-models", timeout=3)
    forge_running = r.status_code == 200
except:
    forge_running = False
```
If not running: warn "Forge not running. Start it with `./scripts/up.sh forge` then re-run with --expr."

**Create output folder:**
```bash
mkdir -p "/home/haint/Projects/home-server/sillytavern/data/default-user/characters/{CharName}"
```

**Generate each expression via Forge API:**

```python
import requests, base64, json

FORGE = "http://localhost:7860"
CHAR_DIR = f"/home/haint/Projects/home-server/sillytavern/data/default-user/characters/{char_name}"

EMOTION_TAGS = {
    "admiration":     "wide_eyes, slight_smile, admiring_expression, looking_up",
    "amusement":      "amused_expression, light_smile, raised_eyebrow",
    "anger":          "angry_expression, furrowed_brows, clenched_teeth, glaring",
    "annoyance":      "annoyed_expression, frowning, flat_gaze, pursed_lips",
    "approval":       "satisfied_expression, gentle_smile, approving_nod",
    "caring":         "warm_smile, soft_eyes, caring_expression, tender_look",
    "confusion":      "confused_expression, head_tilt, furrowed_brows, question_mark",
    "curiosity":      "curious_expression, wide_eyes, head_tilt, leaning_forward",
    "desire":         "half-closed_eyes, biting_lip, seductive_expression",
    "disappointment": "disappointed_expression, frown, downcast_eyes, dejected",
    "disapproval":    "disapproval_expression, frown, shaking_head, skeptical",
    "disgust":        "disgusted_expression, wrinkled_nose, frowning, recoiling",
    "embarrassment":  "blushing, embarrassed_expression, looking_away, shy",
    "excitement":     "excited_expression, wide_smile, bright_eyes, energetic",
    "fear":           "fearful_expression, wide_eyes, trembling, pale, scared",
    "gratitude":      "grateful_expression, gentle_smile, warm_eyes, thankful",
    "grief":          "grief_expression, tears, crying, sad_face, devastated",
    "joy":            "happy_expression, big_smile, laughing, open_mouth, bright_eyes",
    "love":           "loving_expression, heart-shaped_pupils, blush, dreamy",
    "nervousness":    "nervous_expression, sweat_drop, anxious_eyes, fidgeting",
    "optimism":       "optimistic_expression, hopeful_smile, bright_eyes, cheerful",
    "pride":          "proud_expression, confident_smile, chin_up, chest_out",
    "realization":    "realization, wide_eyes, open_mouth, surprised_expression",
    "relief":         "relieved_expression, exhale, gentle_smile, relaxed",
    "remorse":        "remorseful_expression, looking_down, guilty_face, sad",
    "sadness":        "sad_expression, frowning, tearful_eyes, melancholy",
    "surprise":       "surprised_expression, wide_eyes, open_mouth, startled",
    "neutral":        "neutral_expression, relaxed_face, calm, composed",
}

NEG = "lowres, worst quality, bad anatomy, deformed_face, extra_eyes, watermark, text, multiple_characters, duplicate"

EMOTIONS = list(EMOTION_TAGS.keys())

for i, emotion in enumerate(EMOTIONS):
    outfile = f"{CHAR_DIR}/{emotion}.png"
    
    # Skip if already exists
    import os
    if os.path.exists(outfile):
        print(f"[{i+1}/{len(EMOTIONS)}] {emotion} — skip (exists)")
        continue
    
    tags = EMOTION_TAGS[emotion]
    prompt = f"{CHAR_BASELINE}, portrait, close-up, face_focus, looking_at_viewer, {tags}, masterpiece, best quality, newest, absurdres, highres, soft_lighting, detailed_face"
    
    payload = {
        "prompt": prompt,
        "negative_prompt": NEG,
        "sampler_name": "Euler",
        "scheduler": "Karras",
        "steps": 20,
        "cfg_scale": 5,
        "width": 512,
        "height": 768,
        "seed": -1,
        "enable_hr": False,  # no hires for speed
    }
    
    r = requests.post(f"{FORGE}/sdapi/v1/txt2img", json=payload, timeout=120)
    r.raise_for_status()
    img_b64 = r.json()["images"][0]
    
    with open(outfile, 'wb') as f:
        f.write(base64.b64decode(img_b64))
    
    print(f"[{i+1}/{len(EMOTIONS)}] {emotion} ✓")

print(f"\nExpressions saved to: {CHAR_DIR}/")
print("Reload ST (Ctrl+Shift+R) to pick up new sprites.")
```

Where `CHAR_BASELINE` = the char_prompts_positive value from Phase 1.

**Timing:** ~20s/image × 28 = ~9 minutes. Print progress per image.

---

## Phase 4: World Info Lorebook (`--lore` or `--all`)

**LLM task:** Read the character card text and generate 3-5 World Info entries. Each entry should cover one distinct concept: character identity, world/setting, special mechanics, key relationships, or important rules.

For each entry produce:
- `comment`: short title (e.g., "Parasite — What it is")
- `key`: 2-4 trigger keywords (what would make this entry relevant mid-RP)
- `content`: 1-3 sentences injected into the prompt when triggered. Factual, lore-style.

### Position & Depth strategy

Set `position` and `depth` based on entry TYPE — not all entries belong at position=0:

| Lorebook type | position | depth | When to use |
|---------------|----------|-------|-------------|
| **Character mechanics** — extends what {{char}} IS (personality, abilities, lore specific to this char) | `1` | any | After char description. Reinforces identity. Example: Parasite lore |
| **Scenario triggers** — context for specific situations (location, event, activity) | `4` | `4` | @ Depth 4: injects near current messages where keyword appears. Example: Mother scenario lore |
| **Reference / world-building** — encyclopedic background info, species biology, setting details | `4` | `4` | @ Depth 4: reference most relevant close to where it's needed. Example: Bestiary |
| **World constant** — always-on world context (e.g., "this story is set in X") | `0` + `constant: True` | any | Before everything. Use sparingly — costs tokens every turn |

**Default rule:** If unsure → use `position=4, depth=4`. Injecting near current messages is almost always better than position=0 which places entry far from LLM's active attention.

**What NOT to do:** Don't use `position=0` (Before Char Defs) for situational/scenario entries — LLM attention drifts by the time it reaches current message.

**World Info JSON structure** (exact schema from ST source):

```python
import json, os

WORLDS_DIR = "/home/haint/Projects/home-server/sillytavern/data/default-user/worlds"
os.makedirs(WORLDS_DIR, exist_ok=True)

entries = {}
for i, entry in enumerate(LLM_GENERATED_ENTRIES):
    entries[str(i)] = {
        "uid": i,
        "key": entry["key"],          # list of strings
        "keysecondary": [],
        "comment": entry["comment"],
        "content": entry["content"],
        "constant": False,
        "vectorized": False,
        "selective": True,
        "selectiveLogic": 0,           # 0 = AND_ANY
        "addMemo": False,
        "order": 100,
        "position": position,          # 0=before char, 1=after char, 4=@ depth
        "depth": depth,                # injection depth for position=4 (default 4)
        "disable": False,
        "ignoreBudget": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "matchPersonaDescription": False,
        "matchCharacterDescription": True,  # activate on char desc match
        "matchCharacterPersonality": True,
        "matchCharacterDepthPrompt": False,
        "matchScenario": False,
        "matchCreatorNotes": False,
        "delayUntilRecursion": 0,
        "probability": 100,
        "useProbability": True,
        "depth": 4,
        "outletName": "",
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "matchWholeWords": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": 0,
        "sticky": None,
        "cooldown": None,
        "delay": None,
        "triggers": []
    }

lorebook = {
    "entries": entries,
    "name": f"{char_name} Lore"
}

# Save via MCP — ST hot-reloads, lorebook appears in World Info panel
mcp__st__st_save_worldinfo(name=char_name, data=lorebook)

print(f"Lorebook saved: {char_name}")
print(f"Link it in ST: open {char_name} character card → click lorebook icon → select '{char_name}'")
```

---

## Summary Report

After all phases complete, print:

```
=== ST Setup Complete: {CharName} ===

✓ char_prompts[{CharName}] = {positive[:60]}...
✓ char_negative_prompts[{CharName}] = {negative[:40]}...
✓ Settings audit: {N_fixed} corrections made
[✓ Advanced Definition redistributed: description -{X}% / personality / scenario / mes_example / depth_prompt (PNG patched, .bak saved)]
[✓ 28 expressions generated in characters/{CharName}/]
[✓ World Info lorebook saved: worlds/{CharName}.json]

Next steps:
- Ctrl+Shift+R to reload ST
[- {CharName} card → Advanced Definition tab → verify field redistribution]
[- ST → character card → lorebook icon → link '{CharName}' lorebook]
[- Character Expressions panel → verify 28 sprites loaded]
```

---

## Error Handling

- **Card not readable**: warn + ask user to paste visual description manually
- **Forge not running** (--expr): skip expression gen, note for user
- **Forge timeout per image**: retry once, then skip that emotion + continue
- **settings.json write fails**: check if container is still running (`podman ps | grep sillytavern`)
- **PNG patch fails (--adv)**: `.bak` is one `cp` away. Common cause: card uses neither `chara` nor `ccv3` keyword (rare V2 format). Skip Phase 1.5 in that case.
- **PNG patches silently revert (--adv)**: ST holds character cards in memory; when user opens card OR ST triggers card-save event, the in-memory (pre-patch) version overwrites the file. **Mandatory: stop ST via `./scripts/down.sh sillytavern` BEFORE Step D, restart after**. Same gotcha as settings.json `saveSettingsDebounced`.
- **PNG patched but UI shows old data (--adv)**: V2 character cards (`spec: chara_card_v2`, `spec_version: 2.0`) keep V1 mirror fields at root level (`card.description`, `card.personality`, ...) duplicated from `card.data.X`. ST frontend reads from V1 top-level paths. Patching only `card.data.X` leaves V1 stale → UI shows old data, fields appear empty even though file has been patched. **Fix: sync V1 mirror fields with V2 data on every patch** (see Step D). Verify with: `python3 -c "import json,base64,struct;..."` — both `card.X` and `card.data.X` should match.
- **PNG patched + V1 synced but UI STILL shows old data (--adv)**: ST disk cache (`data/_cache/characters/<sha256>`) is the source of truth for UI, not the PNG. ST source `endpoints/characters.js:182` reads cache first; PNG only on cache miss. PNG patches alone never reach UI because data flow is one-direction (UI→file). Cache-nuke + restart didn't fix it either (ST recreated cache with stale data, mechanism unclear). **Real fix: patch BOTH PNG and cache file `value` field with same patched JSON** (see Step D cache patch block). User's correct diagnosis: "patch chỉ hoạt động một chiều UI → image, không ngược lại."
- **LLM over-trims description (--adv)**: user reviews diff in Step C; can pick "Edit before applying" or "Skip Advanced Def".
- **depth_prompt too aggressive in RP**: bump depth from 2 → 4 manually in card UI to soften LLM attention.
