# GDD section note template — `{PREFIX} - {Section}.md`

One concern per note. Fill `{...}` literally; `up:` points at the folder-local index. Drop body
headings that don't apply — don't pad.

```markdown
---
up: "[[GDD - {Codename}]]"
created: {YYYY-MM-DD HH:mm}
updated: {YYYY-MM-DD HH:mm}
type: note
status: idea
tags: [gdd, project/gamedev]
aliases: []
---

# {PREFIX} - {Section}

## Overview
{2–3 sentences: what this design area is + the goal it serves.}

## Details
{The deep dive — mechanics, how it connects to other systems (link them: [[{PREFIX} - {Other}]]),
the player-experience intent.}

## Data / Metrics
{Tables, formulas, balance constants — only if applicable.}

| Parameter | Value | Notes |
|---|---|---|
| {…} | {…} | {…} |

## Open Questions
<!-- Single-source rule (see SKILL.md → Single-source backlogs): if a central
     [[{PREFIX} - Open Questions]] note exists, this section is a POINTER, not a copy — list the
     item IDs + a link, never re-type the question here (the two copies drift). -->
*Single source → [[{PREFIX} - Open Questions]]. Items touching this system:* {Q3 · D1 · …}

## References
- [[GDD - {Codename}]] — index
- [[{PREFIX} - {Related}]] — cross-referenced system
```

`status` lifecycle: `idea` → `in-progress` → `complete`. When a section leaves the active design,
move the file to `archive/` (keep its frontmatter).
