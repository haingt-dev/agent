---
name: st-gen-image-prompt
description: "Build ST image gen prompt — booru tags from chat scene"
argument-hint: "[CharName] [--describe '<text>'] [--last N] [--no-clipboard]"
allowed-tools: Bash, Read, mcp__st__st_get_character, mcp__st__st_get_settings, mcp__st__st_get_recent_chat
---

# ST Gen Image Prompt — Magnum-free image prompt builder

Generate complete booru-tag image prompt cho SillyTavern. Replaces Magnum Mode 4 extraction. Output paste-ready for ST `🎨 Freestyle` button (Mode FREE=6 pass-through).

**Workflow:**
1. Read chat context (last N msgs từ ST chat .jsonl) HOẶC `--describe '<custom>'`
2. Read identity baseline từ `data/identity-baselines/<CharName>.txt`
3. Generate booru tags theo NoobAI XL conventions
4. Verify tags qua Danbooru DB (lazy fetch ~5MB CSV vào `~/.cache/`)
5. Output paste-ready prompt + verification report

## Constants

```
ST_DATA = /home/haint/Projects/home-server/sillytavern/data/default-user
SKILL_DIR = ~/.claude/skills/st-gen-image-prompt
SKILL_DATA = $SKILL_DIR/data
CACHE_DIR = ~/.cache/st-gen-image-prompt
DEFAULT_LAST_N = 10
TAG_DB_URL = https://raw.githubusercontent.com/DominikDoom/a1111-sd-webui-tagcomplete/main/tags/danbooru.csv
TAG_DB_TTL_DAYS = 30
MIN_TAG_COUNT = 50
```

---

## Phase 0: Parse Arguments

Extract from `$ARGUMENTS`:
- `CharName` = first non-flag positional. If absent → auto-detect from latest `chats/<dir>/*.jsonl` mtime.
- `--describe '<text>'` → custom scene (overrides chat reading)
- `--last N` → number of chat messages to read (default 10)
- `--no-clipboard` → skip auto-copy to clipboard (default = auto-copy enabled)

Validate:
- Char folder `chats/<CharName>/` exists OR `--describe` given. If neither → error.

---

## Phase 1: Gather Context

**Step 0 — Ensure tag DB cache:**

```python
import urllib.request, time
from pathlib import Path

CACHE = Path.home() / ".cache/st-gen-image-prompt"
CACHE.mkdir(parents=True, exist_ok=True)
csv_path = CACHE / "danbooru.csv"
ts_path = CACHE / ".last_fetch"

needs_fetch = not csv_path.exists()
if not needs_fetch and ts_path.exists():
    needs_fetch = (time.time() - ts_path.stat().st_mtime) > 30 * 86400

if needs_fetch:
    print("Fetching Danbooru tag DB (~5-10MB, one-time, cached 30d)...")
    url = "https://raw.githubusercontent.com/DominikDoom/a1111-sd-webui-tagcomplete/main/tags/danbooru.csv"
    urllib.request.urlretrieve(url, csv_path)
    ts_path.touch()
    print(f"✓ Cached: {csv_path} ({csv_path.stat().st_size // 1024}KB)")
```

**Step 1 — Read char card via MCP** (replaces legacy PNG tEXt parse):

```python
import json

resp = mcp__st__st_get_character(name=CharName)
card = json.loads(resp) if isinstance(resp, str) else resp
d = card.get('data', card)  # spec v3 nests under 'data'
print(f"NAME: {d.get('name', CharName)}")
print(f"DESCRIPTION: {d.get('description', '')[:1500]}")
print(f"PERSONALITY: {d.get('personality', '')[:300]}")
print(f"SCENARIO: {d.get('scenario', '')[:300]}")
```

**Step 2 — Read persona via path-based MCP** (each call returns a small subtree):

```python
import json

avatar = json.loads(mcp__st__st_get_settings(path="user_avatar")) or ''
try:
    persona_name = json.loads(mcp__st__st_get_settings(path=f"power_user.personas.{avatar}"))
except Exception:
    persona_name = ''
try:
    persona_desc = json.loads(mcp__st__st_get_settings(path=f"power_user.persona_descriptions.{avatar}.description"))
except Exception:
    persona_desc = ''
print(f"PERSONA: {persona_name} (avatar={avatar})")
print(f"PERSONA_DESC: {persona_desc[:1000]}")
```

**Step 3 — Read identity baseline**:

```python
from pathlib import Path
BASELINE_DIR = Path.home() / ".claude/skills/st-gen-image-prompt/data/identity-baselines"

char_baseline = ""
char_baseline_file = BASELINE_DIR / f"{CharName}.txt"
if char_baseline_file.exists():
    char_baseline = char_baseline_file.read_text(encoding='utf-8').strip()
    print(f"CHAR_BASELINE: {char_baseline}")
else:
    print(f"WARN: No baseline for {CharName}. Run /st-setup first or skill will derive identity from card description.")

persona_baseline = ""
if persona_name:
    persona_baseline_file = BASELINE_DIR / f"{persona_name}.txt"
    if persona_baseline_file.exists():
        persona_baseline = persona_baseline_file.read_text(encoding='utf-8').strip()
        print(f"PERSONA_BASELINE: {persona_baseline}")
```

**Step 4 — Read chat context via MCP** (skip if `--describe`):

```python
import json

# /api/chats/recent returns a list of {file_name, file_size, last_mes, ...}
recent_list = mcp__st__st_get_recent_chat(char_name=CharName)
recent_meta = json.loads(recent_list) if isinstance(recent_list, str) else recent_list
if not recent_meta:
    print("ERROR: No chat files found. Use --describe '<text>' instead.")
else:
    # Take top entry (most recent). To fetch full message array, use /api/chats/get
    # via a thin Bash curl call (not yet exposed as MCP tool):
    import subprocess
    file_name = recent_meta[0].get('file_name', '').rsplit('.jsonl', 1)[0]
    print(f"CHAT_FILE: {file_name}.jsonl")

    # Fallback to direct file read for full chat content (the lightweight option until
    # we add an st_get_chat MCP tool returning the full messages array):
    from pathlib import Path
    chat_path = Path("/home/haint/Projects/home-server/sillytavern/data/default-user/chats") / CharName / f"{file_name}.jsonl"
    msgs = []
    with open(chat_path, encoding='utf-8') as f:
        for line in f:
            try:
                m = json.loads(line)
                if 'mes' not in m or m.get('is_system'):
                    continue
                role = "USER" if m.get('is_user') else "CHAR"
                msgs.append(f"[{role}] {m['mes']}")
            except Exception:
                continue
    LAST_N = 10  # or from --last arg
    recent = msgs[-LAST_N:]
    print(f"\n=== Recent {len(recent)} messages ===")
    for m in recent:
        print(m[:500])
```

**Note:** `mcp__st__st_get_recent_chat` returns chat metadata (file names, sizes), not full message bodies. The direct `chats/{CharName}/{file}.jsonl` read above pulls the actual messages. A future `st_get_chat(char, file)` MCP tool would replace this fully.

**Step 5 — Read reference docs**:

Use `Read` tool to load:
- `~/.claude/skills/st-gen-image-prompt/data/noobai-conventions.md` — tag escape, prompt order, quality block
- `~/.claude/skills/st-gen-image-prompt/data/prompt-template.md` — canonical example

---

## Phase 2: Generate Prompt (LLM task)

You (Claude) have all context. Now produce a NoobAI XL-compatible booru-tag prompt.

### Tag formatting rules (NoobAI XL specific)

1. **Underscore handling**: NoobAI accepts both `looking_at_viewer` and `looking at viewer`. Use **spaces** in output for readability (per Laxhar guide section 3).
2. **Escape parens** for character/series tags: `klee_(genshin_impact)` → `klee \(genshin_impact\)`
3. **Artist prefix**: rare in scene, but if needed: `[[artist:wlop]]` (brackets reduce weight, prevent style domination)
4. **Tag count**: 15-30 tags ideal. <15 → underspecified scene. >30 → diluted prompt.

### Prompt order (load-bearing)

```
[Subject count] → [Identity baseline] → [Scene/setting] → [Action] → [Expression] → [Outfit/items] → [Lighting/atmosphere] → [Quality block]
```

Example structure:
```
1girl, [identity baseline tags from data/identity-baselines/<CharName>.txt],
[scene tags: action, location, pose],
[expression: emotion, eye state, mouth state],
[outfit: clothing or undressed state],
[lighting: time, mood, light source],
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Identity injection rules

- **DEFAULT**: Prepend full identity baseline RIGHT after subject count.
- **SKIP identity** for background-only scenes:
  - User `--describe` chứa "no people", "empty", "background only", "no characters" → skip identity
  - Detected via chat context: scene clearly setting-focused without {{char}} present
- **SKIP outfit** when scene shows different clothing state:
  - Bath/shower → skip clothing baseline (`naked`, `nude` from scene)
  - Different outfit specified in scene → use scene outfit, skip baseline outfit
- **PERSONA identity**: If scene includes {{user}} (NSFW interaction, dialogue with user), prepend persona identity baseline too.

### POV dedup (gotcha 5.32)

Pick AT MOST:
- ONE external view: `close-up | wide_shot | pov | side_view | from_below | from_above | dynamic_angle | foreshortening`
- ONE internal view (optional): `x-ray | internal_view | cross-section`

NEVER stack 3+ view tags. Stacking causes split composition / inset panels / duplicate subjects.

### Output discipline

- ONE continuous comma-separated line of booru tags
- NO prose, NO English explanations, NO section labels (`Action:`, `Scene:`)
- NEVER output: `text, speech_bubble, dialogue, comic_panel, panels`
- End with: `(((masterpiece,best quality,newest,absurdres,highres)))`

---

## Phase 2.5: Tag Verification

For EACH tag in the draft prompt:

```python
def normalize_tag(tag):
    """Strip weights, escape, convert to canonical form."""
    import re
    t = tag.strip()
    # Strip weight syntax
    t = re.sub(r'^\(+', '', t)
    t = re.sub(r'\)+$', '', t)
    t = re.sub(r':\d+\.?\d*$', '', t)
    t = re.sub(r'^\[+', '', t)
    t = re.sub(r'\]+$', '', t)
    # Strip escape backslashes
    t = t.replace('\\(', '(').replace('\\)', ')')
    # Skip artist: prefix
    if t.startswith('artist:'):
        t = t[7:]
    # Convert spaces → underscores for CSV lookup
    return t.lower().replace(' ', '_').strip()

def load_tag_db(csv_path):
    db = {}
    with open(csv_path, encoding='utf-8') as f:
        for line in f:
            parts = line.rstrip().split(',', 3)
            if len(parts) < 3:
                continue
            try:
                tag, cat, count = parts[0], int(parts[1]), int(parts[2])
            except ValueError:
                continue
            db[tag] = (cat, count)
            # Index aliases too
            if len(parts) > 3:
                aliases = parts[3].strip('"').split(',')
                for alias in aliases:
                    a = alias.strip()
                    if a:
                        db[a] = (cat, count)  # alias maps to same metadata
    return db

# Verify each tag
db = load_tag_db(csv_path)
verified, rare, removed = [], [], []
SKIP_VERIFY = {'masterpiece', 'best_quality', 'newest', 'absurdres', 'highres'}

for tag in draft_tags:
    norm = normalize_tag(tag)
    if norm in SKIP_VERIFY:
        verified.append(tag)
        continue
    if norm in db:
        cat, count = db[norm]
        if count >= 50:
            verified.append(tag)
        else:
            rare.append((tag, count))
    else:
        removed.append(tag)
```

**Skip verification** for:
- Quality block tags (`masterpiece`, `best_quality`, etc.)
- Identity baseline tags (already curated, trust source)
- Custom tags từ `--describe` user input (assume user knows)

**Offline fallback**: If `~/.cache/st-gen-image-prompt/danbooru.csv` không tồn tại + no internet → skip verification, warn user "VERIFICATION SKIPPED".

---

## Phase 2.6: LoRA Injection

Read `~/.claude/skills/st-gen-image-prompt/data/lora-catalog.md` để biết LoRAs nào available + scene triggers nào → inject `<lora:name:weight>` syntax + trigger words vào prompt.

### Logic

1. **Always-on quality LoRAs** — append to every gen:
   - `<lora:anima-preview-3-masterpieces-v5:0.5>, <lora:AddMicroDetails_Illustrious_v6:0.4>, addmicrodetails`
   - These reinforce `prompt_prefix` ("masterpiece, very aesthetic") + add fine detail.

2. **Concept-triggered LoRAs** — scan verified scene tags (Phase 2.5 output) against catalog:
   - For each catalog row, check if ANY trigger keyword appears in scene tags (case-insensitive substring match, allow underscore↔space variants).
   - Match → add LoRA + add tags listed in catalog row.
   - **Cap**: max 2 concept LoRAs simultaneously (catalog rule). If >2 match, pick by scene tag count (more matches = more relevant).

3. **Compatibility check**:
   - Arachne + MGE Slime — pick stronger match, drop other.
   - Parasite + Oviposition — STACK OK (common scenario).
   - Tentacle + Oviposition — STACK OK.

4. **Inject order** in final prompt (after scene tags, before quality block):
   ```
   [scene tags from Phase 2 + verification]
   ,
   [concept LoRAs + their add_tags]
   ,
   [always-on quality LoRAs + their triggers]
   ,
   (((masterpiece,best quality,newest,absurdres,highres)))
   ```

5. **If no match found** → only inject always-on quality LoRAs.

### Pseudocode

```python
from pathlib import Path
import re

CATALOG = Path.home() / ".claude/skills/st-gen-image-prompt/data/lora-catalog.md"
catalog_text = CATALOG.read_text(encoding='utf-8')

# Parse catalog rows (simplified — extract from markdown tables)
# Each row: keywords (list), lora (str), add_tags (str)

ALWAYS_ON = [
    "<lora:anima-preview-3-masterpieces-v5:0.5>",
    "<lora:AddMicroDetails_Illustrious_v6:0.4>",
    "addmicrodetails",
]

scene_text = ", ".join(verified_tags).lower()
scene_text_norm = scene_text.replace(' ', '_')  # normalize for keyword match

matched = []  # list of (priority_score, lora_block, add_tags_block)

for row in parse_catalog_rows(catalog_text):
    hits = sum(1 for kw in row['keywords'] if kw.lower() in scene_text_norm or kw.lower() in scene_text)
    if hits > 0:
        matched.append((hits, row['lora'], row['add_tags']))

# Sort by priority, take top 2
matched.sort(key=lambda x: x[0], reverse=True)
top_matches = matched[:2]

# Compose injection block
parts = list(verified_tags)
for _, lora, add_tags in top_matches:
    parts.append(lora)
    if add_tags:
        parts.append(add_tags)
parts.extend(ALWAYS_ON)
parts.append("(((masterpiece,best quality,newest,absurdres,highres)))")

final_prompt = ", ".join(parts)
```

### Display in output (Phase 3)

Add to verification report:
```
═══ LoRA Injection ═══
✓ Always-on (2): Aesthetic Quality, Add Micro Details
✓ Concept matches (1): Parasite Horror Transformation [keywords: parasite, transformation]
⊘ No match: Oviposition (no egg/ovi keywords in scene)
```

---

## Phase 3: Display Output + Auto-Copy to Clipboard

### Auto-copy helper

```python
import subprocess, shutil, os

def copy_to_clipboard(text):
    """Auto-copy to clipboard. Detect Wayland/X11 + fall back gracefully.
    Returns: tool_name on success, None on failure."""
    session = os.environ.get('XDG_SESSION_TYPE', '').lower()
    
    # Try Wayland first (KDE Plasma default 2026)
    if session == 'wayland' and shutil.which('wl-copy'):
        try:
            subprocess.run(['wl-copy'], input=text, text=True, check=True, timeout=5)
            return 'wl-copy'
        except Exception:
            pass
    
    # Fall back to X11 tools
    for tool in ['xclip', 'xsel']:
        if shutil.which(tool):
            try:
                args = [tool, '-selection', 'clipboard'] if tool == 'xclip' else [tool, '-b', '-i']
                subprocess.run(args, input=text, text=True, check=True, timeout=5)
                return tool
            except Exception:
                pass
    
    return None

# Usage in skill:
if not no_clipboard_flag:
    tool = copy_to_clipboard(final_prompt)
    if tool:
        clipboard_status = f"✓ Auto-copied to clipboard via {tool}"
    else:
        clipboard_status = "⚠ Auto-copy unavailable. Install: sudo dnf install wl-clipboard (Wayland) or xclip (X11)"
else:
    clipboard_status = "⊘ Clipboard skipped (--no-clipboard flag)"
```

### Output format

```
═══════════════════════════════════════
GENERATED IMAGE PROMPT — {CharName}
Context: {chat ({N} msgs from {chat_file}) | --describe '{text}'}
═══════════════════════════════════════

{final verified prompt with quality block}

═══════════════════════════════════════
TAG VERIFICATION
═══════════════════════════════════════
✓ Verified ({N} tags, count ≥50)
⚠ Rare ({M} tags, count <50): {tag1 (count), tag2 (count), ...}
✗ Removed ({K} tags, not in DB): {tag1, tag2, ...}

═══════════════════════════════════════
CLIPBOARD: {clipboard_status}
═══════════════════════════════════════
NEXT STEPS
═══════════════════════════════════════
1. ST: paste into input box (Ctrl+V — clipboard already has prompt)
2. Click 🎨 Freestyle button (or type /sd <Ctrl+V>)

NOTE: ST sẽ auto-prepend prompt_prefix + character_negative_prompts[{CharName}]
═══════════════════════════════════════
```

---

## Edge Cases

| Case | Handling |
|------|----------|
| No baseline file | Warn, skill derives identity từ card description on the fly |
| No chat history + no `--describe` | Error, ask user to provide `--describe` |
| Tag DB fetch fails (offline) | Warn "VERIFICATION SKIPPED", output unverified prompt |
| LLM hallucinates >5 tags | Show all in `Removed` section, suggest user override với `--describe` |
| Persona not set | Skip persona identity injection, output scene-only prompt |
| Char folder không có .png | Error "Character {CharName}.png not found in characters/" |
| `--describe` rỗng | Same as no `--describe` flag |
| Clipboard tool not installed | Display prompt + warn "Install: sudo dnf install wl-clipboard". User copy thủ công bằng terminal selection. |
| Wayland session but wl-copy missing | Fall back try xclip/xsel (rare on Wayland but possible) |

---

## Related Skills

- `/st-setup <CharName>` → set initial char visual baseline (writes to `data/identity-baselines/<CharName>.txt`)
- `/st-persona <CharName>` → convert char → persona (also creates persona baseline)
- `/st-arc-save` → bake RP arc into lorebook (independent, separate from image gen)

## References

- NoobAI XL Quick Guide (Laxhar Dream Lab, 2024-11): tag escape, prompt order, sampler defaults
- Danbooru tag DB: a1111-sd-webui-tagcomplete project (https://github.com/DominikDoom/a1111-sd-webui-tagcomplete)
- ST source `public/scripts/extensions/stable-diffusion/index.js` `getGenerationType()` — `/sd` mode dispatcher
- `sillytavern/PROMPT-PLAYBOOK.md` gotchas 5.32 (POV dedup), 5.37 (Magnum retired), 5.38 (char_prompts emptied), 5.39 (Mode FREE pass-through)
