---
name: skills
description: Dashboard of all available skills in current project context
---

# Skills — Dashboard

Show all available skills for the current project, grouped by plugin and scope.

## Usage

```
/skills          → full dashboard
/skills [name]   → detail for a specific skill
```

## Step 1: Read Plugin Registry

Read `~/.claude/plugins/installed_plugins.json` to get all installed plugins with:
- Plugin name and marketplace
- Version
- Scope (user = global, project = specific paths)
- Install path (cache directory)

## Step 2: Filter by Current Project

For each plugin entry:
- `scope: "user"` → always available (global)
- `scope: "project"` → only show if `projectPath` matches current working directory

## Step 3: Scan Skills

For each matching plugin, list directories in `{installPath}/skills/`.
For each skill directory, read the SKILL.md frontmatter (between `---` markers) to get:
- `name`: skill name
- `description`: one-line description

Also read the `## Usage` section (first code block after `## Usage` header) for usage examples.

## Step 4: Check Custom Commands

Check for custom commands in:
- `~/.claude/commands/*.md` (global)
- `.claude/commands/*.md` (project-local)

These are simple slash commands (not plugin skills). List them with filename as command name.

## Step 5: Present Dashboard

If no argument (full dashboard):

```
## Skills Dashboard — [current project name]

### [plugin-name] (v[version] · [scope])

| Skill | Description |
|---|---|
| /[name] | [description] |
| /[name] | [description] |

### [another-plugin] (v[version] · project)

| Skill | Description |
|---|---|
| /[name] | [description] |

### Custom Commands

| Command | Source |
|---|---|
| /[name] | global |
| /[name] | project |
```

If argument is a skill name (detail mode):
- Read the full SKILL.md for that skill
- Show: name, description, usage examples, modes/arguments

## Rules

- READ-ONLY — do not modify any files
- Show scope clearly: "global" for user-scoped, "project: [paths]" for project-scoped
- Sort skills alphabetically within each plugin
- If a plugin has no skills directory, skip it
- If no custom commands directories exist, skip that section
- Keep it scannable — no walls of text in dashboard mode
