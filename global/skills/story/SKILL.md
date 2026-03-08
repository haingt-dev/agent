---
name: story
description: "Capture interesting dev stories for future devlogs/blog posts — debugging journeys, architecture decisions, creative workarounds."
model: sonnet
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, AskUserQuestion, Bash(git log *), Bash(git diff *)
---

# Dev Story Capture

Capture moments worth writing about — debugging journeys, architecture decisions, creative workarounds, performance breakthroughs, unexpected failures.

## Trigger Signals

Suggest capturing a story when you notice:
- **Debugging odyssey**: multi-step investigation with a non-obvious root cause
- **Architecture surprise**: a design decision that went against initial instinct
- **Creative hack**: an unconventional workaround that actually worked
- **Performance win**: measurable improvement with an interesting approach
- **Expectation flip**: "tried X, expected it to work, failed because Y"
- **Tool/library gotcha**: undocumented behavior or subtle pitfall

## Workflow

### When auto-suggesting

1. Ask: "Moment thu vi day — capture story khong?"
2. If user confirms, proceed to step 3

### When manually invoked (`/story`)

1. Ask user to briefly describe the story (or use current conversation context)
2. Proceed to step 3

### Capture process

3. Gather context:
   - Current conversation (the journey, decisions, surprises)
   - `.memory-bank/context.md` and `task.md` if they exist
   - `git log --oneline -10` for recent commit context
4. Draft the story using the template structure:
   - **Title**: concise, descriptive (not clickbait)
   - **Date**: today
   - **Tags**: 2-4 tags from the content
   - **TL;DR**: 1-2 sentences capturing the insight
   - **The Problem**: what we were trying to do
   - **The Journey**: what happened, what we tried, what surprised us
   - **The Insight**: the takeaway — what we learned
   - **Technical Details**: optional, include if the technical specifics are interesting
5. Show draft to user using **AskUserQuestion** — MUST wait for approval before saving. Options: "Save as-is", "Edit first" (user provides feedback), "Discard". Do NOT call Write/Edit in the same response as the draft.
6. Generate slug from title (lowercase, hyphens, no special chars)
7. Check if `.memory-bank/stories/YYYY-MM-DD-slug.md` already exists. If it does, append `-2`, `-3`, etc. until unique (e.g., `2026-03-05-cache-bug-2.md`)
8. Save to `.memory-bank/stories/YYYY-MM-DD-slug.md`
9. Append entry to `.memory-bank/stories/index.md` as a table row: `| YYYY-MM-DD | Title | tag1, tag2 |`

## File Locations

- Stories: `.memory-bank/stories/YYYY-MM-DD-slug.md`
- Index: `.memory-bank/stories/index.md`
- Template reference: `~/Projects/agent/templates/memory-bank/stories/template.md`

## Notes

- Slug generation: strip Vietnamese diacritics, lowercase, replace spaces/special chars with hyphens
- Stories are NOT auto-loaded into session context — they live in a subfolder of .memory-bank which session-start.sh ignores by design. This keeps context lean; stories are reference material for blog posts, not working context needed every session.
- Keep stories self-contained — each file should make sense without needing other stories
- Status field: `draft` initially, user changes to `published` when used in a blog post
- If `.memory-bank/stories/` doesn't exist, create it and initialize index.md first
