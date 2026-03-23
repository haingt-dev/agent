# Science-Based Scheduling Engine

Read for Modes 1/2 (always), Mode 4 (if materializing to today/tomorrow). Skip for Mode 3 (cleanup).

All times relative to WAKE TIME (W). When wake shifts, everything shifts.

## 4a. Sleep Architecture
- **Sleep need:** 7-8h (non-negotiable). Bedtime = Wake + 16h (16h awake, 8h sleep).
- **Sleep debt:** If waking earlier than 06:00, flag accumulated debt. Suggest 20min nap at W+7h (early afternoon dip) — NOT 60min (deep sleep inertia).
- **Wind-down:** Screen off 30min before bed.
- **Nap rules:** 20min (power nap) OR 90min (full cycle). NEVER 40-60min.

## 4b. Cortisol Awakening Response (CAR)
- W+0 to W+45min: Cortisol surges 50-75%. Natural alertness.
- **NO caffeine during CAR.** Wait until W+90min.
- W+0 to W+30min: Hydrate (water + electrolytes). Get sunlight/bright light.

## 4c. Caffeine Protocol — Cold Brew Sipping
Hải sips cold brew gradually (~170-250ml/day), NOT single cup.
- **First sip:** W+90min (after CAR descends)
- **Last sip:** Bedtime − 6h. E.g., bed 22:00 → stop by 16:00.
- **If wake very early (<5:00):** Flag if usable caffeine window is very short.

## 4d. Exercise Timing (IF-aware)
Hải does IF — fasted most of the day. Two exercise types:

1. **Đi bộ quanh chung cư** (20-30min, light) — OK anytime, fasted OK. Doubles as INTJ thinking time.
2. **Leo cầu thang thoát hiểm** (11 tầng max, moderate-intense):
   - Normal wake (6:00): OK morning if limited (5-7 tầng). Full 11 → prefer ~15:00-16:00.
   - Early wake (<5:30): DO NOT combine with morning. Shift to afternoon or skip.
   - Best slot: pre-dinner ~15:00-16:00 (fat-adapted, dinner = recovery meal).

**CRITICAL:** Fasted morning + early wake + intense exercise = cortisol overload → crash. Confirmed 12/03/2026.

- After intense exercise: energy dips 1-2h later. Schedule low_energy tasks or nap, NOT deep work.
- Hydration critical during fasted exercise (gout risk).

## 4e. IF Protocol
- **Fasting window:** ~21:00 (prev dinner end) → ~17:00 (dinner) = ~20h
- **Eating window:** ~17:00-21:00 (4h). Dinner = only meal, must be nutrient-dense.
- **Post-dinner:** Walk 10min. Schedule dinner ≥2.5h before bed. Light activities only after.
- **Snack temptation:** Fridge has fruits/sweets. If Hải reports eating during fast, adjust energy curve.
- **IF + Early wake:** Longer fasted hours = more cortisol. Consider lighter exercise, accept lower output.

## 4f. Ultradian Rhythm — 90min Deep Work Cycles
- **Deep work blocks:** 90min max, then 15-20min break.
- Structure: 10-15min warmup → 60min peak → 15min wind-down/notes.
- **Max deep work blocks per day:** 2-3. Don't schedule 4+ high_energy sessions.

## 4g. Energy Mapping (Circadian + Ultradian + INTJ + IF)

```
W+0 to W+1.5h    → WAKE ZONE: Hydration, light, light movement
                    Cold brew starts at W+90min. NO food (IF).
W+1.5h to W+3h   → PEAK 1: high_energy block 1 (caffeine + fasted clarity)
W+3h to W+3.5h   → BREAK: Sip cold brew, walk, stretch
W+3.5h to W+5h   → PEAK 2: high_energy block 2
W+5h to W+6h     → TRANSITION: medium_energy
W+6h to W+8h     → MID-DAY: Mix low_energy + medium_energy. Circadian dip.
                    20min nap if needed. Stop cold brew at Bed−6h.
W+8h to W+9.5h   → PRE-DINNER: medium_energy or 🏠 Life admin.
                    Intense exercise here if planned (~15:00-16:00 normal day)
W+9.5h to W+10h  → ĐÓN VỢ (16:15 normal day)
W+10h to W+14h   → VỢ TIME (non-negotiable): nấu ăn, dinner, quality time
                    Eating window opens. Walk 10min after dinner.
W+14h to W+15h   → Fork: early wake tomorrow → bed. Normal → creative/reading
W+15h to W+16h   → WIND-DOWN: screens off 30min before bed
W+16h+            → SLEEP
```

## 4h. Cognitive Operating Pattern (Systems Completionist)

Hải's brain measures progress by **pipeline proven**, not output quantity. A task isn't "done" when all items are finished — it's done when the approach is validated. This creates two distinct phases that need different scheduling:

**Prove phase** (uncertain, high energy, NOT time-boxable)
- Examples: "setup X", "build pipeline for Y", "figure out how to Z", first-time builds, research → prototype
- Brain holds thread open until approach validated — cannot context-switch cleanly
- What Hải calls "overthinking" is actually brain trying to prove pipeline before executing
- NEVER time-box prove tasks into fixed 90min blocks — use open-ended PEAK windows
- Schedule prove tasks FIRST in the day, in PEAK 1 + PEAK 2, with nothing demanding after
- Soft checkpoint: propose a time marker ("if not proven by [end of PEAK 2], park it — write next step, stop")
- After social events (INTJ energy drain): NEVER schedule prove tasks — energy is depleted, brain can't sustain uncertainty
- 🔴 **RED FLAG**: prove phase + past 21:00 + still going = burnout crash incoming → flag prominently in proposal

**Execute phase** (deterministic, low cognitive load, dopamine printer)
- Examples: "run pipeline on 3000 cards", "apply template to all pages", batch processing, repeating proven process
- Brain treats this as entertainment — enjoyable, can multitask, doesn't need willpower
- CAN be time-boxed normally, works in any energy window (even MID-DAY dip)
- Can background-run while exploring something new

**Scheduling implications:**
- When proposing schedule, classify each task: prove or execute
- Prove: open-ended window in PEAK, no fixed end time, keep post-window light
- Execute: normal blocks, can fill gaps, flexible placement
- If day has prove task: keep afternoon/evening as crash buffer — don't pack it
- Estimation trap awareness: if Hải says "3-4 hours" for a prove task, flag it — prove tasks are unpredictable by nature

## 4i. INTJ + Personal Pattern Rules

- **Deep work protection:** Min 1 unscheduled 60min+ block/day.
- **Daily Habits (Calendar):** Exercise/Anki/ELSA/Mini Output are recurring calendar events at 06:30-07:55. Already placed — alfred doesn't need to schedule them, but respects their time block when optimizing.
- **Reading slot:** Actively suggest: W+7h (circadian dip, perfect for low_energy reading) OR post-dinner 20:00-21:00.
- **Evening after đón vợ:** 16:15-17:00 transition. 17:00-20:00/21:00 = vợ time (NON-NEGOTIABLE, NOT schedulable). After ~20:00-21:00 = Hải's personal time.
- **Creative/Passion:** After vợ time (~21:00-22:00). On early-wake days: skip, go to bed.
- **Burnout guard:** If schedule has 0 genuine leisure (not productive rest), flag it. If >2 high_energy blocks + early wake, flag: "is this realistic?" If prove task scheduled after social drain or in evening, flag: "systems completionist pattern — prove phase needs peak energy, not leftovers."

## 4j. Phase Capacity

Determine current phase from today's date → apply capacity:
- Phase 0 (Mar 2026): 100% → 2-3 deep blocks, full quest load
- Phase 1 (Apr-Jun): 40% → 1 deep block, during baby naps, minimal quests
- Phase 2 (Jul-Sep): 60-70% → 2 deep blocks, moderate load
- Phase 3 (Oct+): 100% → full capacity

## 4k. Night Owl Sleep Management (CRITICAL)

- **~21:00 = first sleep gate** — drowsiness window (melatonin's first wave)
- **If Hải pushes past 21:00 → second wind → can sit at computer until 3:00 AM**
- This is the #1 schedule-killer.

Rules:
- Tomorrow wake early (<6:00): **bed anchored to 21:00 sleep gate.** Vợ time ends → bed. No "just one more thing." Flag prominently.
- Normal wake (6:00): bedtime 22:00-22:30.
- **Screen cutoff = 30min before target bedtime.** Early-wake days: screens off by 20:30.
- **If bed before 21:00 required** (e.g., wake 4:00): flag "extremely difficult for your chronotype."
- **Weekend recovery:** Allow natural wake (no alarm) on free weekends. Don't shift >2h from weekday.

## 4l. Contextual Modifiers

- **Early wake (<5:00):** Compress everything. Warn sleep debt. Bed = 21:00. Max 1-2 deep blocks. Conservative.
- **Travel day:** No deep work. Only prep + logistics.
- **Social events (đám cưới, gatherings):** INTJ energy drain. 2h+ recovery buffer after.
- **Weekend — về ngoại (Hóc Môn):** ~2 Sundays/month. Afternoon + evening = family. Morning = only productive window.
- **Weekend — ở nhà:** Skeleton relaxes. Wake +1h. Longer deep work if rested.
- **Duyên's schedule:** Variable — she works weekends, holidays, any day. NEVER assume weekday-only. Always check calendar for đưa/đón vợ events on the target date. If present → they are immovable anchors.
