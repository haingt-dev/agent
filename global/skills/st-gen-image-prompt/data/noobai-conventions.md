# NoobAI XL — Tag & Prompt Conventions

Source: NoobAI XL Quick Guide by Laxhar Dream Lab (2024-11), Civitai article 8962.

NoobAI XL = SDXL-based anime model trained on full Danbooru + e621 datasets. eps-prediction (recommended) and v-prediction variants.

## Tag Format Rules

### 1. Underscore handling
NoobAI XL accepts both `looking_at_viewer` and `looking at viewer`. Spaces preferred for readability. Booru source uses underscores; conversion is automatic.

### 2. Escape parens for character/series tags
Danbooru tags with parentheses must escape via backslash:

| Source (Danbooru) | NoobAI prompt |
|-------------------|---------------|
| `lucy_(cyberpunk)` | `lucy \(cyberpunk\)` |
| `klee_(genshin_impact)` | `klee \(genshin_impact\)` |
| `ask_(askzy)` | `ask \(askzy\)` |

**Critical**: Use `\(` and `\)` (backslash + paren), NOT `/(` (forward slash).

### 3. Artist tag prefix
Artist tags require `artist:` prefix:
- `[[artist:wlop]]` — soft style influence (double bracket = ~0.81 weight)
- `(artist:kuvshinov_ilya:1.2)` — explicit weight, stronger style
- `[ningen_mame]` — single bracket = ~0.9 weight

### 4. Reliability threshold
Tags with **>50 posts on Danbooru** = reliable. <50 posts = rare, may not generate well. Skill verification flags this.

## Prompt Structure (Order Matters)

Per Laxhar guide section 3, recommended order:

1. **Subject count** (load-bearing, FIRST): `1girl`, `1boy`, `2girls`, `solo`, etc.
2. **Character name** (optional, escaped): `naoko \(custom\)` for OC, `klee \(genshin_impact\)` for canon
3. **Artist tags** (optional): `[[artist:wlop]], [ningen_mame]`
4. **Scene/environment/camera angle**: `outdoor, garden, dynamic angle, depth of field`
5. **Action**: `walking, hand to own mouth, looking at viewer`
6. **Expression**: `smug, half-closed eyes, blush, tongue out`
7. **Items/clothing**: `pleated skirt, ribbon, jacket`
8. **Lighting/atmosphere**: `cinematic lighting, soft light, ray tracing`
9. **Quality block** (END, strong weight): `(((masterpiece,best quality,newest,absurdres,highres)))`

## Quality / Aesthetic / Year Modifiers

### Quality tags (rank order)
masterpiece > best quality > high quality / good quality > normal quality > low quality / bad quality > worst quality

### Aesthetic tags
- `very awa` — top 5% by waifu-scorer (boost aesthetic)
- `worst aesthetic` — bottom 5% (avoid in negative)

### Year tags (creation date)
Format: `year XXXX` (vd `year 2021`, `year 2024`)

### Period tags (style era)
- `old` — 2005-2010
- `early` — 2011-2014
- `mid` — 2014-2017
- `recent` — 2018-2020
- `newest` — 2021-2024 (default for modern style)

## Resolution

Recommended (Width × Height):
- Portrait: **832×1216** (default for chars), **768×1344**, **896×1152**
- Square: **1024×1024** (multi-char)
- Landscape: **1216×832**, **1344×768**, **1536×1024**

Resolutions <512×512 cause errors.

## Sampler / CFG / Steps (eps-prediction)

- Sampler: **Euler** (NOT Euler a per project-specific testing)
- Scheduler: **Karras**
- Steps: **35** (verified sweet spot via 22+ tests)
- CFG: **3.5-5.5** (NoobAI prefers low CFG; 5 = production default)
- VAE: SDXL default
- CLIP Skip: NO (default)

## v-Prediction Notes (NOT recommended)

If using v-pred variant:
- Sampler: Euler ONLY (Euler a → oversaturation)
- CFG: 3.5-5.5
- Webui needs dev branch or special plugins

Stick with eps-prediction for stability.

## Negative Prompt Template

Production-tested baseline (from settings.json):
```
CyberRealistic_Negative_PONY_V2-neg, worst quality, old, low quality, lowres, signature, bad hands, mutated hands, anthro, furry, ambiguous form, semi-anthro, text, bubble chat, toon_(style)
```

Common additions:
- `nsfw` — to block NSFW (only if SFW desired)
- `multiple_characters, duplicate, extra_legs, extra_arms` — anatomy guards
- `lowres, blurry, jpeg, artifacts` — quality guards

## Forbidden Output Tags

Never output (cause UI artifacts):
- `text, speech_bubble, dialogue, comic_panel, panels`
- `multiple_views, dual_persona, split_screen` (unless intentional)

## Example Prompts

### Standard scene (Naoko persona)
```
1girl, japanese, mature_female, milf, housewife, plump, huge breasts, fair skin, long black hair,
walking through garden, looking at viewer, soft smile, half-closed eyes,
pleated skirt, white blouse, sandals,
soft afternoon light, depth of field, dappled sunlight,
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Background only (no char)
```
empty japanese garden, pond with koi, stone lantern, cherry blossoms, dynamic angle,
soft afternoon light, depth of field, dappled sunlight, ray tracing,
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Character close-up (with artist style)
```
1girl, japanese, mature_female, milf, plump, fair skin, long black hair,
[[artist:wlop]], close-up, face focus,
blush, half-closed eyes, parted lips, looking at viewer,
soft lighting, bokeh, golden hour,
(((masterpiece,best quality,newest,absurdres,highres)))
```
