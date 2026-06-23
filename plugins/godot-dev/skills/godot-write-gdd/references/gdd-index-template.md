# Master GDD index template — `GDD - {codename}.md`

Fill the `{...}` placeholders with literal values. Dates are real `YYYY-MM-DD HH:mm`. The `up:`
is omitted (a standalone folder has no parent note); the title alias names the doc instead.

```markdown
---
created: {YYYY-MM-DD HH:mm}
updated: {YYYY-MM-DD HH:mm}
type: note
status: in-progress
tags: [gdd, project/gamedev]
aliases: ["Game Design Document: {Codename}", GDD]
---

# GDD - {Codename}

**Vibe:** {one-line feel}  ·  **Genre:** {genre}  ·  **Platform:** {platform}

> {One-sentence pitch — what the game IS. The whole design serves this.}

![key art]({optional relative path or link, or omit})

## Design pillars
{3–5 pillars, one line each — the inline stable spine. Detail lives in the Design Pillars note.}
- **{Pillar}** — {one line}

## Core loop
{1–3 sentences. Detail in the Game Loops note.}

---

## Sections

> Hand-curated map grouped by taxonomy. The Dataview block below auto-lists every note in this
> folder by `up:` link — this table is the *reading order + status* layer. Status: 🔴 stub · 🟡 in-progress · 🟢 complete.

### Summary
| Section | Note | Status |
|---|---|---|
| {…} | [[{PREFIX} - {Section}]] | 🟡 |

### Core (stable spine)
| Section | Note | Status |
|---|---|---|
| Design Pillars | [[{PREFIX} - Design Pillars]] | 🟢 |
| Game Loops | [[{PREFIX} - Game Loops]] | 🟡 |
| Player Progression | [[{PREFIX} - Player Progression]] | 🟡 |

### Features
| Section | Note | Status |
|---|---|---|
| {…} | [[{PREFIX} - {Feature}]] | 🔴 |

### Content
| Section | Note | Status |
|---|---|---|
| {…} | [[{PREFIX} - {Content}]] | 🔴 |

### Archived
| Section | Note | Removed because |
|---|---|---|
| {…} | [[archive/{PREFIX} - {Old}]] | {reason} |

---

## All notes (auto)
\`\`\`dataview
TABLE status, tags FROM "" WHERE contains(up, this.file.link) SORT file.name ASC
\`\`\`
```

Notes:
- `FROM ""` scopes the query to the opened folder — no hardcoded vault path. This is what makes the
  index self-aggregate in any project's `docs/gdd/`.
- Keep this index **one-page-ish**: pitch + pillars + loop + the section tables. Depth lives in the
  section notes, not here.
