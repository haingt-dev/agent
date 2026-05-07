# LoRA Catalog — Forge / NoobAI EPS 1.1 stack

Maps scene keywords → LoRA injection. Skill (Phase 2.5) checks scene tags against catalog, appends matching `<lora:name:weight>` syntax + trigger words.

**Lookup logic**: scene tag is "match" if the scene/chat context contains ANY of the keywords (case-insensitive substring or token match). Multiple matches → multiple LoRAs (max 4 simultaneously to avoid prompt dilution).

**Weight ranges**:
- Quality LoRAs: 0.4–0.6 (always-on, low impact)
- Concept LoRAs: 0.6–0.9 (scene-specific, stronger)
- Style LoRAs: 0.3–0.7 (subtle to medium)

---

## Always-On Quality (auto-include every gen)

| LoRA | Trigger words | Weight | Notes |
|------|--------------|--------|-------|
| `anima-preview-3-masterpieces-v5` | `masterpiece, very aesthetic` | 0.5 | Already in `prompt_prefix` — LoRA reinforces. ID #929497 |
| `AddMicroDetails_Illustrious_v6` | `addmicrodetails` | 0.4 | Universal detail boost. ID #1377820 |

**Always inject these 2 LoRAs at end of prompt** (before quality block):
```
<lora:anima-preview-3-masterpieces-v5:0.5>, <lora:AddMicroDetails_Illustrious_v6:0.4>, addmicrodetails
```

---

## Concept-Triggered (inject when scene matches)

### Parasite / Body Horror

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `parasite, infection, body_horror, takeover, transformation, corruption, eldritch, skin_change, changed` | `<lora:Parasite_horror_transformation_IL_port:0.8>` | `changed, horror, parasite, takeover, transformation, body horror, corruption` |

### Oviposition / Egg-laying

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `oviposition, egg_laying, ovipositor, egg, eggs, frog_eggs, insect_eggs, spider_eggs, alien_eggs` | `<lora:Oviposition_xray_illus-000040:0.7>` | `oviposition, frog eggs, insect eggs, spider eggs, silk, spiderweb, fish eggs, alien eggs` |
| _(stack with above for tentacle ovi):_ `tentacle_ovi, ovipositor_tentacle` | `<lora:oviposition_anima:0.6>` | `tentacle sex, oviposition, implanting eggs, transparent tentacles` |

### Tentacles (general)

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `tentacle, tentacles, tentacle_sex` | `<lora:oviposition_anima:0.6>` | `tentacle sex, transparent tentacles` |

### Monstergirl / MGE

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `monstergirl, monster_girl, mge, monster_girl_encyclopedia, slime_carrier, parasite_slime, dark_matter, barometz` | `<lora:MGE_SlimeCarrier_v4.1_IL:0.7>` | _(no required triggers — LoRA infers from concept tags)_ |

### Arachne / Spider Yuri

| Trigger keywords (any) | LoRA | Add tags |
|------------------------|------|----------|
| `arachne, spider_girl, arachnesex, spider_yuri, web, spiderweb` | `<lora:Arache_sex_illus-000037:0.8>` | `purple arachne, arachnesex, interspecies, tentacle sex, monstergirl, restrained, spiderwebs, silk, yuri` |

---

## Stacking Rules

1. **Max 4 LoRAs simultaneously** — beyond 4 dilutes prompt adherence + may exceed VRAM.
2. **Always-on quality (2)** + max 2 concept LoRAs.
3. **Compatible categories**: Parasite + Oviposition can stack (body horror with egg implant). Tentacle + Oviposition stack natural.
4. **Conflicting**: Arachne + MGE Slime — pick one dominant theme per gen.
5. **Order in prompt**: scene tags first → concept LoRAs → quality LoRAs → quality block.

## Output format example

For scene "naoko bị parasite kí sinh, tentacle ovi":
```
1girl, [identity baseline], indoors, bedroom, lying on bed, naked,
parasite, body horror, transformation, tentacle sex, oviposition, implanting eggs, transparent tentacles,
<lora:Parasite_horror_transformation_IL_port:0.8>, changed, horror, takeover, corruption,
<lora:oviposition_anima:0.6>, transparent tentacles,
<lora:anima-preview-3-masterpieces-v5:0.5>, <lora:AddMicroDetails_Illustrious_v6:0.4>, addmicrodetails,
(((masterpiece,best quality,newest,absurdres,highres)))
```

---

## Maintenance

When adding/removing LoRAs:
1. Place file ở `forge/data/forge/models/Lora/` (qua `/civitai-model download <id>`)
2. Update this file: add/remove section
3. Note trigger words from Civitai page (qua `mcp__civitai__get_model`)

Verify file presence: `ls /home/haint/Projects/home-server/forge/data/forge/models/Lora/*.safetensors`
