# Prompt Templates — Canonical Examples

Reference templates cho skill output. Skill copy structure, fill in specific tags theo scene context.

## Template 1: Standard scene (char + scene)

```
1girl, [identity baseline tags],
[location/setting], [time of day],
[action], [pose], looking at viewer,
[expression], [eye state], [mouth state],
[outfit / clothing state],
[lighting], [atmosphere], depth of field,
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Filled example (Naoko in garden)
```
1girl, japanese, mature_female, milf, housewife, plump, huge breasts, fair skin, long black hair,
suburban japanese garden, afternoon,
walking, hands clasped, looking at viewer,
soft smile, half-closed eyes, parted lips,
white blouse, pleated skirt, sandals,
soft afternoon light, dappled sunlight, depth of field,
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Template 2: Char close-up (face focus)

```
1girl, [identity baseline],
close-up, face focus,
[expression], [emotion], [eye contact],
[hair state], [skin detail],
[lighting], bokeh, [atmosphere],
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Filled example
```
1girl, japanese, mature_female, milf, plump, fair skin, long black hair,
close-up, face focus, looking at viewer,
flushed cheeks, half-closed eyes, parted lips, tongue out,
hair over one eye, sweat,
soft lighting, golden hour, bokeh,
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Template 3: Background only (no char)

NO `1girl`/`1boy`. NO identity baseline.

```
[location/setting] [no humans],
[notable elements], [composition tags],
[lighting], [atmosphere], depth of field, bokeh,
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Filled example
```
empty japanese garden, no humans, pond with koi, stone lantern, cherry blossoms,
wide shot, dynamic angle, depth of field,
soft afternoon light, dappled sunlight, ray tracing,
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Template 4: NSFW interaction (char + persona)

```
1girl, [char identity baseline],
[persona/{{user}} interaction context],
[scene location], [intimate setting],
[action / pose], [body interaction],
[expression], [reaction state],
[clothing state — usually undressed/disheveled],
[lighting], [atmosphere],
(((masterpiece,best quality,newest,absurdres,highres)))
```

### Filled example (Parasite + Naoko)
```
1girl, japanese, mature_female, milf, plump, fair skin, long black hair,
parasite, slug, on body, intimate,
bedroom, dim light, night,
lying on back, parted thighs, body trembling,
flushed cheeks, half-closed eyes, mouth open, drooling,
disheveled clothing, naked breasts, exposed,
soft lamp light, sweat, body fluids,
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Template 5: Multiple chars

```
2girls, [each char identity baseline],
[interaction tags: standing together, hugging, etc.],
[scene location],
[mutual action], [mutual expression],
[outfit per char if needed],
[lighting], [atmosphere],
(((masterpiece,best quality,newest,absurdres,highres)))
```

## Negative Prompt Template (auto-prepended by ST)

ST auto-applies global `negative_prompt` + `character_negative_prompts[CharName]`. Skill does NOT need to inject negative.

Reference (ST default):
```
CyberRealistic_Negative_PONY_V2-neg, worst quality, old, low quality, lowres, signature, bad hands, mutated hands, anthro, furry, ambiguous form, semi-anthro, text, bubble chat, toon_(style)
```

Per-char negative (from settings.json `character_negative_prompts`):
- Your Oblivious Mother: `muscular, masculine, male, slim, skinny, flat_chest, young_woman, teenager, child`
- Parasite: (empty)

## Tag count guidelines

| Scene complexity | Tag count |
|------------------|-----------|
| Simple portrait | 12-18 tags |
| Standard scene | 18-25 tags |
| Complex action | 22-30 tags |
| Multi-char NSFW | 25-35 tags |

Below 12 → underspecified, output bland. Above 35 → diluted attention, detail blur.

## Common booru tag categories

### Subject count (FIRST)
`1girl`, `1boy`, `2girls`, `2boys`, `solo`, `multiple_girls`, `1girl, 1boy`

### Body framing
`upper body`, `lower body`, `cowboy shot`, `full body`, `face focus`, `cropped legs`

### POV (pick ONE max)
`close-up`, `wide shot`, `pov`, `side view`, `from below`, `from above`, `dynamic angle`, `foreshortening`

### Internal POV (optional, ONE max)
`x-ray`, `internal view`, `cross-section`

### Expression
`smile`, `light smile`, `smug`, `blush`, `flushed cheeks`, `tears`, `crying`, `angry`, `surprised`, `scared`, `confused`, `sad`, `embarrassed`

### Eye state
`eye contact`, `looking at viewer`, `half-closed eyes`, `closed eyes`, `wide eyes`, `glaring`, `looking down`, `looking away`

### Mouth state
`open mouth`, `parted lips`, `closed mouth`, `tongue out`, `drooling`, `biting lip`, `smiling`

### Hair states
`hair over one eye`, `messy hair`, `bedhead`, `wet hair`, `hair down`, `ponytail`, `bun`

### Lighting
`soft lighting`, `cinematic lighting`, `rim lighting`, `backlighting`, `golden hour`, `blue hour`, `dappled sunlight`, `harsh light`, `dim light`, `candlelight`, `lamp light`

### Atmosphere
`depth of field`, `bokeh`, `light particles`, `light leaks`, `dust particles`, `ray tracing`, `volumetric lighting`, `god rays`

### Setting (Japanese contexts)
`japanese garden`, `traditional house`, `tatami room`, `shoji screen`, `bedroom`, `bathroom`, `kitchen`, `living room`, `genkan`, `engawa`

### Time
`morning`, `afternoon`, `evening`, `night`, `dusk`, `dawn`

### Quality block (LAST, always)
```
(((masterpiece,best quality,newest,absurdres,highres)))
```
