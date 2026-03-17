---
name: story
description: "Capture stories worth writing about — dev journeys AND personal narratives."
model: sonnet
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, AskUserQuestion, Bash(git log *), Bash(git diff *), Bash(date +%Y-%m-%d), Bash(mkdir -p *)
---

# Story Capture

Capture moments worth writing about — debugging journeys, architecture decisions, creative workarounds, personal realizations, family narratives, belief shifts.

Stories live in the Idea Vault as first-class notes (`type: story`). They're raw material for blog posts, devlogs, and personal essays — not journal entries.

## Trigger Signals

Suggest capturing a story when you notice:

### Technical
- **Debugging odyssey**: multi-step investigation with a non-obvious root cause
- **Architecture surprise**: a design decision that went against initial instinct
- **Creative hack**: an unconventional workaround that actually worked
- **Performance win**: measurable improvement with an interesting approach
- **Expectation flip**: "tried X, expected it to work, failed because Y"
- **Tool/library gotcha**: undocumented behavior or subtle pitfall

### Personal
- **Belief shift**: a conviction that changed or crystallized based on experience
- **Heritage discovery**: connecting dots across generations — family stories that explain who you are
- **Life reframe**: seeing a "failure" or setback as a hidden gift
- **Perspective flip**: a moment where understanding shifted fundamentally
- **System insight**: realizing how a personal system (finance, workflow, identity) works differently than assumed
- **Context epiphany**: a conversation that only worked because of deep personal context

## Workflow

### When auto-suggesting

1. Ask: "Moment thú vị đây — capture story không?"
2. If user confirms, proceed to step 3

### When manually invoked (`/story`)

1. Ask user to briefly describe the story (or use current conversation context)
2. Proceed to step 3

### Capture process

3. Gather context:
   - Current conversation (the journey, decisions, surprises)
   - `git log --oneline -10` for recent commit context (skip if story is personal/non-code)

4. Determine `up` link:
   a. Discover existing project notes:
      `Glob("**/Project - *.md", path="/home/haint/Projects/Idea_Vault/20 Projects")`
      Extract names from filenames (e.g., `Project - Bookie.md` → `Bookie`)
   b. If story is clearly about one of the discovered projects → use `"[[Project - <Name>]]"`
   c. If story is about a registered project that has NO Vault note yet:
      - Read `/home/haint/Projects/agent/registry.json` for project metadata
      - Read the Vault template at `/home/haint/Projects/Idea_Vault/00 System/Templates/Project Template.md`
      - Create directory: `mkdir -p "/home/haint/Projects/Idea_Vault/20 Projects/<Name>"`
      - Create note at `/home/haint/Projects/Idea_Vault/20 Projects/<Name>/Project - <Name>.md`
        using the Vault template with Templater variables resolved:
        - `<% tp.file.creation_date() %>` → today's date+time (YYYY-MM-DD HH:mm)
        - `<% tp.file.title %>` → `Project - <Name>`
        - `<% tp.user.select_project_type(tp) %>` → map from registry type:
          `godot` → `gamedev`, `infra` → `homelab`, `app` → ask via AskUserQuestion
          (valid types from `/home/haint/Projects/Idea_Vault/00 System/Meta/Project Types.md`)
        - `summary` from `registry.json` → fill Overview section
      - Then use `"[[Project - <Name>]]"` as `up` link
   d. Cross-project, tool/meta (Claude Code, shell, infra), or personal → use `"[[Story MOC]]"`
   e. When genuinely unsure, ask via AskUserQuestion with:
      - All discovered project names as `"[[Project - <Name>]]"` options
      - `"[[Story MOC]] (no specific project)"` as final option

5. Draft the story using the template structure (see below)

6. Show draft to user using **AskUserQuestion** — MUST wait for approval before saving.
   Options: "Save as-is", "Edit first" (user provides feedback), "Discard".
   Do NOT call Write/Edit in the same response as the draft.

7. Generate filename: `YYYY-MM-DD Title With Spaces.md`
   - Get today's date via `date +%Y-%m-%d`
   - Strip Vietnamese diacritics from filename (keep in title/body).
     Mapping: ắăâàáảạã→a, đ→d, êềếệẹẻẽ→e, ôồốổộõọỏ→o, ươừứụủũ→u, ịỉĩ→i, ỳỷỹ→y
   - Use spaces (Vault convention), not hyphens
   - Example: "Bytes Vs Chars Vietnamese TTS" not "bytes-vs-chars-vietnamese-tts"

8. Check if file already exists at `/home/haint/Projects/Idea_Vault/10 Journal/Stories/YYYY-MM-DD Title.md`.
   If it does, append ` 2`, ` 3`, etc. until unique.

9. Save to `/home/haint/Projects/Idea_Vault/10 Journal/Stories/YYYY-MM-DD Title With Spaces.md`

## Story Template

```yaml
---
up: "[[Story MOC]]"
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: story
status: draft
tldr: >
  1-2 sentences capturing the insight
tags:
  - journal/story
  - swe/backend    # map to Vault taxonomy from 00 System/Meta/Tags.md
---
```

### Body sections

```markdown
# Title (Vietnamese OK, descriptive, not clickbait)

## TL;DR
1-2 sentences — same as frontmatter tldr

## The Problem / The Context
Technical: what we were trying to do
Personal: what prompted this reflection

## The Journey
What happened, what we tried, what surprised us

## The Insight
The takeaway. Without this, it's a log entry, not a story.

## Technical Details
Optional: code, configs, specifics worth preserving. Omit for personal stories.
```

### Tone guidance

- **Technical stories**: analytical, show-don't-tell. Evidence first, conclusion after. Code snippets welcome
- **Personal stories**: reflective, self-aware. Concrete details over abstract philosophy
- **Both**: honest. Don't romanticize. If unsure, say so

## Tag Mapping

Map old-style tags to Vault taxonomy:
- debugging, plugin-system, config-management → `swe/devops`
- tts, voice-cloning, utf-8 → `swe/backend`
- remotion, animation, visual-design → `swe/frontend` + `content-creation/video`
- ai, context → `tech/ai`
- life, family, freedom → `journal/life` + `journal/family`
- finance → `finance`
- identity, career → `journal/life`

Always include `journal/story` as first tag.

## Notes

- Stories are Vault notes — no manual index needed. Dataview in Story MOC handles discovery.
- Keep stories self-contained — each file should make sense without needing other stories
- Status: `draft` initially, user changes to `published` when used in blog post
- No `.memory-bank/stories/` management — that system is retired
- Tag taxonomy reference: `/home/haint/Projects/Idea_Vault/00 System/Meta/Tags.md`
- Vault project template: `/home/haint/Projects/Idea_Vault/00 System/Templates/Project Template.md`
- Project type taxonomy: `/home/haint/Projects/Idea_Vault/00 System/Meta/Project Types.md`
- Agent registry: `/home/haint/Projects/agent/registry.json`
