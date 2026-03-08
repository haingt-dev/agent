---
name: godot-debugging
description: "Debug Godot 4.x errors, crashes, and unexpected behavior. Corrective lens for Godot 3 vs 4 API confusion, async pitfalls, lifecycle timing, and physics gotchas."
model: sonnet
allowed-tools: Read, Grep, Glob, Bash(grep *), mcp__claude_ai_Context7__resolve-library-id, mcp__claude_ai_Context7__query-docs
---

# Godot Debugging

## Debugging Workflow

1. Read the FULL error message — "ON BASE: NULL INSTANCE" matters more than the property name
2. Check scene tree path validity (node names, hierarchy, timing)
3. Use `print_stack()` for call chain, not just `print()`
4. Profile before optimizing — Debug > Profiler > Time column

## Corrective Lens: What Models Get Wrong

### Godot 3 vs 4 API Confusion

Models frequently suggest deprecated Godot 3 APIs. Always use the Godot 4 equivalents:

| Godot 3 (WRONG) | Godot 4 (CORRECT) | Notes |
|---|---|---|
| `deg2rad()` | `deg_to_rad()` | All math utils renamed |
| `rand_range()` | `randf_range()` | Also `randi_range()` for int |
| `connect("signal", obj, "method")` | `signal_name.connect(callable)` | Callable-based signals |
| `move_and_slide(velocity, up)` | `move_and_slide()` | velocity is now a property |
| `BUTTON_LEFT` | `MOUSE_BUTTON_LEFT` | All input enums renamed |
| `yield(obj, "signal")` | `await obj.signal` | yield removed entirely |
| `instance()` | `instantiate()` | PackedScene method |
| `KinematicBody2D` | `CharacterBody2D` | Node type renamed |
| `Sprite` | `Sprite2D` | 2D suffix added |
| `export var` | `@export var` | Annotation syntax |
| `onready var` | `@onready var` | Annotation syntax |
| `set_cell(x, y, id)` | `set_cell(layer, coords, source, atlas, alt)` | TileMap completely reworked |

### Async/Await Pitfalls

- `await` on signal that fires instantly → returns immediately (not next frame)
- `await tween.finished` when duration=0 → hangs forever
- Calling coroutine without `await` → silently becomes dangling task, no error
- Hot reload + active `await` → crash (coroutine references freed objects)
- `await` does NOT pause the caller unless the caller also uses `await`:
  ```gdscript
  death_sequence()  # Returns immediately — does NOT wait
  await death_sequence()  # This DOES wait
  ```

### Scene Lifecycle Gotchas

- `_ready()` is bottom-up (children first, then parent) — NOT top-down
- `@onready` vars resolved BEFORE `_ready()` body runs
- `instantiate()` without `add_child()` → node exists but NOT in tree (no `_ready`, no `_process`)
- `_init()` runs before tree entry — no access to `$Children` or `get_parent()`
- `queue_free()` doesn't happen immediately — node is still accessible until end of frame

### Input Processing

- `is_action_just_pressed()` in `_physics_process()` can miss inputs at low framerates
- Use `_unhandled_input()` for game input, `_input()` only for UI
- `Input.get_vector()` returns normalized vector — no need to `.normalized()` again
- Input actions are case-sensitive — "Jump" != "jump"

### Physics

- `move_and_slide()` modifies `velocity` (wall sliding) — read velocity AFTER call, not before
- `call_deferred()` required for collision shape changes during physics callbacks
- High velocity → tunneling through thin walls (>16px/frame at 60fps)
- `RayCast2D`/`3D` must be enabled AND `force_raycast_update()` called for immediate results

## When to Fetch Fresh Docs

If unsure about exact API signatures for Godot 4.4+, use Context7:
1. `mcp__claude_ai_Context7__resolve-library-id` → find "godot"
2. `mcp__claude_ai_Context7__query-docs` → get current API details

## Project Conventions (Wildtide + Chimera)

- `gdformat` + `gdlint` on all `.gd` files
- `push_error()` for unrecoverable, `push_warning()` for suspicious but safe
- `assert()` for debug-only invariants (stripped in release)
- Static typing mandatory: all vars, params, returns
