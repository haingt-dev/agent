---
up: "[[GDD - {Codename}]]"
created: {YYYY-MM-DD HH:mm}
updated: {YYYY-MM-DD HH:mm}
type: note
status: in-progress
tags: [gdd, project/gamedev]
aliases: []
---

# {PREFIX} - Open Questions

<!-- The canonical single-source backlog, shaped as a PRIORITIZED TOP-DOWN WORK-QUEUE.
     Full text + status of every open item lives HERE under a stable ID; each owning note carries a
     one-line pointer back (ID + link), never a re-typed copy. See SKILL.md → Single-source backlogs. -->

## Overview

The single backlog of honest TBDs, **structured as a prioritized top-down work-queue.** This note
is the canonical home — every item's full text + status lives *here* under a stable ID; each owning
note carries a one-line **pointer** back (the ID + a link), never a re-typed copy.

**How to use it:** solve **▶ THE QUEUE** from the top down, one item at a time. Each item names its
resolution **Mode**. **Parked / Deferred / Resolved** sit *outside* the active queue — don't work
them now. IDs may encode the item's origin (`Q#` question · `D#` reef/decision · `R#` risk ·
`G#` spec-gap · `C#` contradiction · `S#` status).

## Legends

**Status** — 🔴 **OPEN** (undecided; needs a pass) · ⚪ **GATE-DEFERRED** (decided to decide later,
at a named gate) · 🟢 **LOCKED** (direction settled, only tuning remains) · ✅ **RESOLVED** (closed;
kept for traceability).

**Mode** — 🔨 **forge** (a live design decision to make now) · ✍️ **scribe** (fix the text: stale
wording / drift / mis-tag — no new design thinking) · ⏸ **plan/gate** (not a design node — belongs
to planning or a named gate) · 🧪 **prototype** (honest answer needs playtest data).

> These Mode/Status glyphs are **local to this note.** The master index reuses 🔴/🟡/🟢 with a
> *different* meaning (section completeness) — don't conflate them.

## ▶ THE QUEUE — solve top-down

<!-- Rank DEPENDENCY-FIRST, SEVERITY-SECOND. Group into bands (foundation → dependent → heaviest).
     Sev = blocks | refactor | minor. Dep = upstream IDs that must close first (— if none). -->

| # | ID | What to resolve | Mode | Sev | Dep | Owning note(s) |
|---|----|-----------------|------|-----|-----|----------------|
| 1 | {ID} | {the decision to make, one line} | 🔨 | blocks | — | [[{PREFIX} - {Owning note}]] |

## ⏸ Parked — 🧪 prototype-gated leans (don't solve now)

| ID | Item | Status |
|----|------|--------|
| {Q#} | {tuning knob — settled direction, prototype-tunable} | 🟢 tuning |

## ⏸ Deferred — planning / gate (not design nodes)

| ID | Item | Why deferred |
|----|------|--------------|
| {ID} | {item} | ⏸ planning / ⚪ gate — {reason} |

## ✅ Resolved — traceability

| ID | Item | Outcome |
|----|------|---------|
| {ID} | {item} | ✅ {one-line outcome + owning note} |

## Details — active queue nodes

*(Single-source full text for the ▶ QUEUE. Owning notes point in; do not re-type these there.)*

**{ID} — {short title} [🔨 {sev}]**
{The question / the drift · why it blocks completeness · the decision to make · any prior/lean.}
Owning: [[{PREFIX} - {Owning note}]].

## References
- [[GDD - {Codename}]] — index
- [[{PREFIX} - {Owning note}]] — {which IDs it owns}
