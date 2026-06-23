# godot-dev — MCP & tool routing

The point of the plugin is not just knowledge lenses — it's knowing *which* tool to reach for at
each step of indie Godot work, so the MCPs actually get used. When working in a Godot project, route
like this:

| You're doing… | Reach for | Why |
|---|---|---|
| Run / play the project, open the editor, inspect the scene tree, create/edit scenes & nodes | **`godot` MCP** (bundled — `run_project`, `launch_editor`, `create_scene`, `add_node`, `save_scene`, …) | Live engine control + valid `.tscn` authoring; beats hand-editing scene files. |
| Unsure about a Godot 4.x API / a 3→4 migration / a class signature | **Context7** (`resolve-library-id` → `query-docs`) | Fetch the *current* Godot docs instead of trusting stale memory. The `godot-debugging` skill leans on this. |
| Need concept art, a mood board, a sprite, a character round | **`/gen-art`** | The universal image hub routes to the right backend (cloud concept-art vs local sprite gen). Don't bundle image gen here. |
| "What did we decide / what's the pattern for X" | **brain** (`brain_recall`, `brain_tools`) | Prior decisions, patterns, and the right skill/tool for the task. |
| Format / lint / test / commit a change | **`/ship`** (+ the project's git Stop-hook for gdformat) | Mechanical quality gate — not a godot-dev skill (deliberately). |

## The skills in this plugin

| Skill | Use it to… |
|---|---|
| `godot-write-gdd` | author/update the `docs/gdd/` Obsidian GDD folder (index + section notes) |
| `godot-check-gdd` | check recent code against the GDD pillars + sections for drift / scope creep |
| `godot-new-scene` | scaffold a `.tscn`+`.gd` following the project's existing layout |
| `godot-status` | check/init the `docs/STATUS.md` project dashboard |
| `godot-debugging` | Godot-4 errors, crashes, 3→4 API confusion (corrective lens) |
| `godot-gdscript-patterns` | GDScript architecture patterns + naming/typing conventions |

Skill **discovery** is handled by the brain Semantic Toolbox (`brain_tools`), not by verbose
descriptions — each skill's `description` is deliberately one terse line; the rich trigger text lives
in the toolbox index (curated via `/toolbox-curator`).
