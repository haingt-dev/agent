---
name: godot-write-gdd
description: "Author/update a Godot project's GDD as a docs/gdd/ Obsidian folder (index + section notes)."
model: sonnet
allowed-tools: Read, Write, Edit, Glob
argument-hint: "[section or topic]"
---

# Godot — Write GDD

Author and maintain a Godot project's Game Design Document as a **self-contained Obsidian
"mini-vault" folder** at `docs/gdd/`. The dev opens that folder directly in Obsidian, so every
note must be a first-class Obsidian citizen (valid frontmatter, folder-local links) — and it's
versioned with the code. This skill is generic; the project supplies only the content.

## Why this shape (read before editing)

- **Modular wiki, not a monolith.** One concern per note, cross-linked — like code, many small
  modules over one giant file. A short master index (hub) spokes out to section notes. This keeps
  the GDD a *living* doc: you edit one small note, the index re-aggregates itself.
- **Self-contained folder.** `docs/gdd/` is opened as its own vault. Links resolve *within the
  folder* — so `up:` points at the local index `"[[GDD - {codename}]]"`, **never** a main-vault
  `[[Project MOC]]`. There is **no Templater** here: emit literal frontmatter (real
  `YYYY-MM-DD HH:mm` timestamps, the known up-link), not `<% tp.* %>` placeholders.
- **The frontmatter contract is load-bearing.** Obsidian's Dataview indexes these notes; a wrong
  date format or unquoted `up:` silently drops a note from the index. Get it right on the first write.

## The convention

```
docs/gdd/
├─ GDD - {codename}.md            # master index / hub  (one-page discipline)
├─ {PREFIX} - Design Pillars.md   # ─┐
├─ {PREFIX} - Game Loops.md       #  │ Core — the STABLE spine (rarely changes)
├─ {PREFIX} - Player Progression.md # ─┘
├─ {PREFIX} - {Feature}.md        # Features — mechanics that span the game (evolve freely)
├─ {PREFIX} - {Content}.md        # Content — narrative / characters / levels (variable)
└─ archive/{PREFIX} - {Old}.md    # deprecated sections, MOVED not deleted
```

- `{codename}` = the project's stable codename; `{PREFIX}` = its short tag (IC, BK, …).
- **Taxonomy = Summary · Core · Features · Content** (the index groups sections under these). Trim
  to the project — cut groups you don't need; never pad to fill a template.
- **Core is the stable anchor** (pillars → loops → progression). Keep it to a few small notes; it's
  the reference the rest of the design hangs off, not a dumping ground.

### Single-source backlogs (Open Questions et al.)

A cross-cutting backlog — the **Open Questions** note, or any register aggregating items owned by
many notes — has **one canonical home**: each item's full text + status lives there under a
**stable ID** (`Q3`, `D1`, `R2`…) that the rest of the vault references. Each owning note carries a
**one-line pointer** back (the IDs that touch it + a link), **never a re-typed copy** — re-typing
the item in both places is the trap: the two drift, and the reader can't tell which is current.
*(A status legend + an at-a-glance table in the canonical note is the recommended trackability
layer, but that format is project taste; the single-source rule is the law.)*

**Shape the canonical note as a prioritized top-down work-queue** — the dev solves it from the top,
one item at a time. Rank items **dependency-first, severity-second** (an upstream schema/economy node
blocks the ones below it). Tag each with a **Mode** — 🔨 forge (a live design call) · ✍️ scribe (fix
drift, no new thinking) · ⏸ plan/gate (not a design node) · 🧪 prototype (needs playtest data) — so
the reader knows *how* each closes. Keep **Parked** (prototype-gated leans), **Deferred**
(planning/gate), and **Resolved** (traceability) as sections *outside* the active queue. IDs may
encode origin (`Q#` question · `D#` reef · `R#` risk · `G#` spec-gap · `C#` contradiction · `S#`
status). **NB** these Mode/Status glyphs are local to the note — the index reuses 🔴/🟡/🟢 for
section-completeness; don't conflate them.

Templates (read them, fill literally — do not copy the Templater syntax):
- Master index → [references/gdd-index-template.md](references/gdd-index-template.md)
- Section note → [references/gdd-section-template.md](references/gdd-section-template.md)
- Open Questions (work-queue) → [references/gdd-open-questions-template.md](references/gdd-open-questions-template.md)

## Procedure

1. **Load context** — `docs/gdd/GDD - {codename}.md` (index) + the relevant section notes. If
   `docs/gdd/` doesn't exist yet, ask before scaffolding it from the templates (a new GDD folder is
   a decision, not a default). Also read `docs/STATUS.md` (project phase) and the
   `{PREFIX} - Design Pillars.md` note (the constraints).

2. **Find the target** from `$ARGUMENTS` (a section name or topic). If absent, ask what to
   write/update.

3. **Existing section** → read its note, show the current content, ask what to change, update
   in-place (preserve frontmatter; bump `updated:` to now). **New section** → create
   `{PREFIX} - {Section}.md` from the section template with literal frontmatter, place it in the
   right taxonomy group, and add a row to the index's section table (the Dataview block
   auto-lists it, but the human-readable layered table is hand-curated — add the wikilink + status).

4. **Guard the pillars** — read `{PREFIX} - Design Pillars.md`; if a change works against a stated
   pillar, flag it before writing. Don't silently encode a contradiction.

5. **Deprecate, don't delete** — when a section leaves the active design, MOVE its note to
   `archive/` (keep the frontmatter; set `status` accordingly) and drop it from the index's live table.

6. **Reflect status** — when a system moves design state, update that note's `status:`
   (idea → in-progress → complete) and, if it shifts the project's phase, note it in `docs/STATUS.md`
   (the `godot-status` skill owns that dashboard — cross-link, don't duplicate).

7. Bilingual (VN/EN) — match the language the user writes.

8. Summarize what changed: which note(s), what moved, any pillar tension raised.

## Frontmatter rules (non-negotiable — Dataview depends on them)

- `created` / `updated`: exactly `YYYY-MM-DD HH:mm` (24-hour, no `T`, no seconds, unquoted).
- `up:`: a **quoted** wikilink → `up: "[[GDD - {codename}]]"`.
- `tags:`: inline array → `[gdd, project/gamedev]`.
- Filename H1 must match the filename (`# {PREFIX} - {Section}`).
- Flat layout — section notes live directly in `docs/gdd/`; only `archive/` (and asset dirs) nest.
