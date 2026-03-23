---
name: story
description: "Capture stories worth writing about — dev journeys AND personal narratives."
model: sonnet
disable-model-invocation: true
allowed-tools: Read, Glob, AskUserQuestion, Bash(obsidian *), Bash(git log *), Bash(git diff *)
---

# Story Capture

Capture moments worth writing about — debugging journeys, architecture decisions, creative workarounds, personal realizations, family narratives, belief shifts.

Stories live in the Idea Vault as first-class notes (`type: story`). They're raw material for blog posts, devlogs, and personal essays — not journal entries.

## Trigger Signals

### Technical
- **Debugging odyssey**: multi-step investigation with a non-obvious root cause
- **Architecture surprise**: a design decision that went against initial instinct
- **Creative hack**: an unconventional workaround that actually worked
- **Performance win**: measurable improvement with an interesting approach
- **Expectation flip**: "tried X, expected it to work, failed because Y"
- **Tool/library gotcha**: undocumented behavior or subtle pitfall

### Personal
- **Belief shift**: a conviction that changed or crystallized based on experience
- **Heritage discovery**: connecting dots across generations
- **Life reframe**: seeing a "failure" or setback as a hidden gift
- **Perspective flip**: a moment where understanding shifted fundamentally
- **System insight**: realizing how a personal system works differently than assumed
- **Context epiphany**: a conversation that only worked because of deep personal context

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
   - `git log --oneline -10` for recent commit context (skip if story is personal/non-code)

4. Read vault schema files:
   - `Read /home/haint/Projects/Idea_Vault/00 System/Meta/Tags.md` — valid tag namespaces
   - `Read /home/haint/Projects/Idea_Vault/00 System/Meta/Status.md` — valid status values
   - `Read /home/haint/Projects/Idea_Vault/00 System/Templates/Story Template.md` — frontmatter + body structure

5. Determine `up` link:
   a. Discover existing project notes:
      `Glob("**/Project - *.md", path="/home/haint/Projects/Idea_Vault/20 Projects")`
      Extract names from filenames (e.g., `Project - Bookie.md` -> `Bookie`)
   b. If story is clearly about one discovered project -> use `"[[Project - <Name>]]"`
   c. If story is about a registered project with NO Vault note yet -> create it (see Project Note Creation below)
   d. Cross-project, tool/meta, or personal -> use `"[[Story MOC]]"`
   e. When genuinely unsure, ask via AskUserQuestion with discovered project names + `"[[Story MOC]]"` as options

6. Draft the story:
   - Follow the Story Template structure from step 4
   - Read `references/writing-samples.md` first — absorb voice from real examples
   - Read `references/voice-guide.md` second — apply guardrails
   - Always include `journal/story` as first tag, add domain tags from Tags.md

7. Show draft to user using **AskUserQuestion** — MUST wait for approval before saving.
   Options: "Save as-is", "Edit first" (user provides feedback), "Discard".
   Do NOT save in the same response as the draft.

8. Generate filename: `YYYY-MM-DD Title With Spaces.md`
   - Date prefix: `date +%Y-%m-%d` (system date, no `obsidian eval` needed)
   - Strip Vietnamese diacritics from filename (keep in title/body).
     Mapping: ắăâàáảạã->a, đ->d, êềếệẹẻẽ->e, ôồốổộõọỏ->o, ươừứụủũ->u, ịỉĩ->i, ỳỷỹ->y
   - Use spaces (Vault convention), not hyphens

9. Check if file already exists. If it does, append ` 2`, ` 3`, etc. until unique.

10. Create note via Obsidian CLI:
    ```bash
    # Create from template — `open` triggers Templater (resolves dates, title, type, status, base tags)
    obsidian create path="10 Journal/Stories/{filename}.md" template="Story Template" open

    # Override properties that differ from template defaults:
    # up — only if linking to a project instead of default [[Story MOC]]
    obsidian property:set path="10 Journal/Stories/{filename}.md" name="up" value="[[Project - {Name}]]"
    # tldr — always set from drafted content
    obsidian property:set path="10 Journal/Stories/{filename}.md" name="tldr" value="{tldr}" type=text
    # tags — only if adding domain tags beyond journal/story
    obsidian property:set path="10 Journal/Stories/{filename}.md" name="tags" value="journal/story,{other-tags}" type=list

    # Update body: read template-created note, replace placeholder sections with drafted content, write back
    ```

    Template already handles (skip these): `created`, `updated`, `type: story`, `status: draft`, `up: [[Story MOC]]` (default).

## Project Note Creation

When a story references a project with no Vault note:

1. Read `/home/haint/Projects/agent/registry.json` for project metadata
2. Read `/home/haint/Projects/Idea_Vault/00 System/Templates/Project Template.md` for structure
3. Read `/home/haint/Projects/Idea_Vault/00 System/Meta/Project Types.md` for valid types
4. Get current datetime via `obsidian eval`
5. Map registry type: `godot` -> `gamedev`, `infra` -> `homelab`, `app` -> ask via AskUserQuestion
6. Create via CLI:
   ```bash
   # Create from template — `open` triggers Templater (resolves dates, title, type, status, tags)
   obsidian create path="20 Projects/{Name}/Project - {Name}.md" template="Project Template" open

   # Override project_type (template uses interactive picker, CLI needs explicit value)
   obsidian property:set path="20 Projects/{Name}/Project - {Name}.md" name="project_type" value="{mapped_type}" type=text
   ```

## Notes

- Stories are Vault notes — no manual index needed. Dataview in Story MOC handles discovery
- Keep stories self-contained — each file should make sense without needing other stories
- Status: `draft` initially, user changes to `published` when used in blog post
- Agent registry: `/home/haint/Projects/agent/registry.json`
