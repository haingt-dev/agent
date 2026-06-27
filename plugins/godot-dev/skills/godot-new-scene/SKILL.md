---
name: godot-new-scene
model: haiku
description: "Scaffold a new Godot scene + script following this project's existing layout + conventions."
allowed-tools: Read, Write, Glob, Bash, AskUserQuestion
argument-hint: "[scene_name]"
---

# Godot — New Scene

Scaffold a new Godot scene (`.tscn`) + its script (`.gd`) that drops cleanly into *this* project —
matching where its scenes/scripts already live and the conventions they already use. The point is
zero-friction starting points that look like the dev wrote them, not a generic skeleton that has to
be rewritten.

## Why "follow the project," not a fixed layout

Every Godot project organizes differently (`scenes/` + `scripts/`, feature-folders, a flat `src/`,
…). Hardcoding one layout (the mistake in the project-local versions this replaces) makes the skill
useless everywhere else. So **discover the project's structure and mirror it** instead of assuming.

## Procedure

1. **Scene name** — from `$ARGUMENTS` (snake_case, e.g. `resource_depot`). If absent, ask.

2. **Discover the layout** — don't assume. Look at how the project already organizes scenes/scripts:
   ```
   ls **/*.tscn **/*.gd   (or Glob); read project.godot for "run/main_scene" hints
   ```
   Infer the convention (separate `scenes/`+`scripts/` dirs? co-located? feature folders?) and where
   a new scene of this kind belongs. If genuinely ambiguous, ask with the candidate locations.

3. **Read a sibling** — open the nearest existing scene+script pair to copy the project's real
   patterns: base class (`extends`), `class_name` usage, typed vars, signal style, autoload refs.
   Honor `CLAUDE.md` conventions if present (the `godot-gdscript-patterns` skill carries the
   Godot-4 baseline: snake_case, static typing, `##` docstrings, composition over inheritance).

4. **Create the script** at the project's script path:
   ```gdscript
   class_name {PascalName}
   extends {BaseClass}
   ## {one-line purpose}
   ```
   Typed members, `@onready` node refs, `@export` for inspector data, signals in past tense.

5. **Create the scene** at the project's scene path. Prefer the **godot MCP** (`create_scene` /
   `add_node` / `save_scene`) when it's available in the session — it writes a valid `.tscn` the
   editor will load without complaint. If not available, hand-write a minimal Godot-4 `.tscn`:
   ```
   [gd_scene load_steps=2 format=3]
   [ext_resource type="Script" path="res://{path}/{name}.gd" id="1"]
   [node name="{RootName}" type="{RootType}"]
   script = ExtResource("1")
   ```
   Keep it a skeleton — root node + script only; the dev builds the tree.

6. Show the created file paths for confirmation.
