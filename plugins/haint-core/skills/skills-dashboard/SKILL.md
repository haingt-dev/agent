---
name: skills-dashboard
description: "Show all available skills for current project — lists every skill with description, usage, and scope (global vs project). Use this skill whenever the user asks about available skills, slash commands, what commands exist, 'what can you do', 'list skills', or wants to see a skill overview/dashboard. Also trigger when user asks for details about a specific skill by name."
---

# Skills Dashboard

Show all available skills for the current project, grouped by plugin and scope.

## Usage

```
/skills-dashboard              → full dashboard
/skills-dashboard [name]       → detail for a specific skill
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
- If a plugin has multiple entries with different scopes/paths, consolidate: show all matching project paths

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
If neither directory exists, skip this section entirely.

## Step 5: Present Dashboard

If no argument (full dashboard):

```
## Skills Dashboard — [current project name]

### [plugin-name] (v[version] · global)

| Skill | Description |
|---|---|
| /[name] | [description] |
| /[name] | [description] |

### [another-plugin] (v[version] · project: [path1], [path2])

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
- Search across all available plugins for a skill matching the argument (exact match on name, case-insensitive)
- If found: read the full SKILL.md and show name, description, usage examples, modes/arguments
- If not found: say so and list available skill names as suggestions
- If ambiguous (partial match hits multiple): list matches and ask user to be more specific

## Rules

- READ-ONLY — do not modify any files
- Show scope clearly: "global" for user-scoped, "project: [paths]" for project-scoped with all matching paths listed
- Sort skills alphabetically within each plugin
- If a plugin has no skills directory, skip it
- Keep it scannable — no walls of text in dashboard mode
