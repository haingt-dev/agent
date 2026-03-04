---
name: story
description: Capture interesting dev stories for future devlogs/blog posts. Auto-suggests when detecting notable moments.
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

1. Ask: "Moment thú vị đấy — capture story không?"
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
5. Show draft to user for review/edits
6. Generate slug from title (lowercase, hyphens, no special chars)
7. Save to `.memory-bank/stories/YYYY-MM-DD-slug.md`
8. Append entry to `.memory-bank/stories/index.md`

## File Locations

- Stories: `.memory-bank/stories/YYYY-MM-DD-slug.md`
- Index: `.memory-bank/stories/index.md`
- Template reference: `~/Projects/agent/templates/memory-bank/stories/template.md`

## Notes

- Stories are NOT auto-loaded into session context (subfolder of .memory-bank is ignored by session-start.sh)
- Keep stories self-contained — each file should make sense without needing other stories
- Status field: `draft` initially, user changes to `published` when used in a blog post
- If `.memory-bank/stories/` doesn't exist, create it and initialize index.md first
