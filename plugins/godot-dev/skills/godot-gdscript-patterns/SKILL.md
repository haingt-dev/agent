---
name: godot-gdscript-patterns
description: "Godot 4.x GDScript architecture patterns and project conventions. Guides pattern selection (state machine vs component vs singleton), enforces project conventions, and provides on-demand pattern references. Use when building a new Godot system, refactoring architecture, or asking about GDScript best practices."
model: sonnet
allowed-tools: Read, Grep, Glob
---

# Godot GDScript Patterns

## Shared Conventions (Wildtide + Chimera)

### Naming
- Files/variables/functions: `snake_case`
- Classes: `PascalCase`
- Constants: `SCREAMING_SNAKE_CASE`
- Signals: `snake_case` past tense (`health_changed`, `died`)

### Typing
- Static typing mandatory: all vars, params, returns, loop vars
- `@export` for inspector, `@onready` for node refs
- `##` docstrings (double hash) for public API, not `#` comments

### Architecture Rules
- Resources (`.tres`) for data, scripts for logic — never hardcode tunable values
- Signals for decoupling — avoid `get_node()` chains between systems
- Composition over deep inheritance (especially Chimera)
- Max 3 autoloads (Wildtide: GameManager, MetricSystem, EventBus)

## Pattern Selection Guide

When building a new system, choose pattern based on the problem:

| Problem | Pattern | When NOT to use |
|---|---|---|
| Entity with multiple behavior modes | State Machine | <3 states (just use if/match) |
| Shared behavior across entity types | Component System | Behavior only used by 1 entity type |
| Game-wide event communication | Signal Bus (EventBus autoload) | Direct parent-child communication |
| Data variation (weapons, enemies, items) | Resource (`.tres` files) | Runtime-only calculated values |
| Frequently spawned/destroyed objects | Object Pool | <20 objects or infrequent spawning |
| Async scene transitions | Scene Manager | Simple `get_tree().change_scene_to_file()` |
| Persistent game state | Save Manager (JSON) | `.tres` for saves (fragile on refactor) |

If the pattern needs more detail, read the reference file:
- `references/state-machine.md` — Full StateMachine + State base class implementation
- `references/components.md` — HealthComponent, Hitbox/Hurtbox, KnockbackComponent
- `references/save-system.md` — Multi-slot JSON save with encryption + preview
- `references/object-pool.md` — Generic ObjectPool with signal-based return

## Corrective Lens: Pattern Mistakes

### State Machine
- Use node-based states (not enum+match) for >3 states — each state gets its own script
- Disable `process_mode` on inactive states — don't just skip update calls
- Pass `msg: Dictionary` to `enter()` for state-specific initialization data
- `transition_to()` should disable old state's processing BEFORE enabling new state

### Signals
- Connect in the PARENT, not in the emitting node
- Avoid signal forwarding chains >2 levels deep — use EventBus instead
- `CONNECT_ONE_SHOT` for cleanup connections that should fire once
- Check `is_connected()` before connecting in code that may run multiple times

### Resources
- ALWAYS `duplicate()` resources at runtime if multiple instances share the same `.tres`
- Resources with signals: connect AFTER `duplicate()`, not before
- Don't put heavy logic in Resources — they're data containers
- `class_name` on Resource subclasses for typed exports

### Async/Await in Patterns
- Scene transitions: `await` BEFORE swapping scenes, not after
- Object pool: never `await` inside pool return logic (blocks the pool)
- Save system: use JSON not `.tres` for save files (class rename breaks `.tres` loads)
- Tween chaining: `tween.chain()` is cleaner than sequential `await`

## Performance Patterns

- Cache node references in `_ready()`, never `$Path` in `_process()`
- `distance_squared_to()` instead of `distance_to()` in hot paths (avoids sqrt)
- `set_physics_process(false)` on off-screen or idle entities
- Object pool for bullets/particles/VFX — not `queue_free()` + `instantiate()` every frame
- Reuse arrays/dictionaries in hot paths — `array.clear()` instead of `var array = []`
- Use typed arrays (`Array[Node2D]`) — faster iteration than untyped

## Fresh Docs

For exact Godot 4.x API signatures, use Context7 MCP rather than guessing:
1. `mcp__claude_ai_Context7__resolve-library-id` → find "godot"
2. `mcp__claude_ai_Context7__query-docs` → get current API details
