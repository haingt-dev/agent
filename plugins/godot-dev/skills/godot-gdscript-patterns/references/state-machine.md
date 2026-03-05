# State Machine Pattern

Node-based state machine where each state is a child node with its own script.

## StateMachine (parent node)

```gdscript
# state_machine.gd
class_name StateMachine
extends Node

signal state_changed(from_state: StringName, to_state: StringName)

@export var initial_state: State

var current_state: State
var states: Dictionary = {}

func _ready() -> void:
    for child in get_children():
        if child is State:
            states[child.name] = child
            child.state_machine = self
            child.process_mode = Node.PROCESS_MODE_DISABLED

    if initial_state:
        current_state = initial_state
        current_state.process_mode = Node.PROCESS_MODE_INHERIT
        current_state.enter()

func _process(delta: float) -> void:
    if current_state:
        current_state.update(delta)

func _physics_process(delta: float) -> void:
    if current_state:
        current_state.physics_update(delta)

func _unhandled_input(event: InputEvent) -> void:
    if current_state:
        current_state.handle_input(event)

func transition_to(state_name: StringName, msg: Dictionary = {}) -> void:
    if not states.has(state_name):
        push_error("State '%s' not found" % state_name)
        return

    var previous_state := current_state
    previous_state.exit()
    previous_state.process_mode = Node.PROCESS_MODE_DISABLED

    current_state = states[state_name]
    current_state.process_mode = Node.PROCESS_MODE_INHERIT
    current_state.enter(msg)

    state_changed.emit(previous_state.name, current_state.name)
```

## State (base class)

```gdscript
# state.gd
class_name State
extends Node

var state_machine: StateMachine

func enter(_msg: Dictionary = {}) -> void:
    pass

func exit() -> void:
    pass

func update(_delta: float) -> void:
    pass

func physics_update(_delta: float) -> void:
    pass

func handle_input(_event: InputEvent) -> void:
    pass
```

## Example: PlayerIdle

```gdscript
# player_idle.gd
class_name PlayerIdle
extends State

@export var player: Player

func enter(_msg: Dictionary = {}) -> void:
    player.animation.play("idle")

func physics_update(_delta: float) -> void:
    var direction := Input.get_vector("left", "right", "up", "down")
    if direction != Vector2.ZERO:
        state_machine.transition_to("Move")

func handle_input(event: InputEvent) -> void:
    if event.is_action_pressed("attack"):
        state_machine.transition_to("Attack")
```
