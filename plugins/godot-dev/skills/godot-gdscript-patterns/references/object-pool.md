# Object Pool Pattern

Pre-instantiate objects and recycle them instead of `instantiate()` + `queue_free()` every frame.

## ObjectPool

```gdscript
class_name ObjectPool
extends Node

@export var pooled_scene: PackedScene
@export var initial_size: int = 10
@export var can_grow: bool = true

var _available: Array[Node] = []
var _in_use: Array[Node] = []

func _ready() -> void:
    for i in initial_size:
        _create_instance()

func _create_instance() -> Node:
    var instance := pooled_scene.instantiate()
    instance.process_mode = Node.PROCESS_MODE_DISABLED
    instance.visible = false
    add_child(instance)
    _available.append(instance)

    if instance.has_signal("returned_to_pool"):
        instance.returned_to_pool.connect(_return_to_pool.bind(instance))

    return instance

func get_instance() -> Node:
    var instance: Node

    if _available.is_empty():
        if can_grow:
            instance = _create_instance()
            _available.erase(instance)
        else:
            push_warning("Pool exhausted and cannot grow")
            return null
    else:
        instance = _available.pop_back()

    instance.process_mode = Node.PROCESS_MODE_INHERIT
    instance.visible = true
    _in_use.append(instance)

    if instance.has_method("on_spawn"):
        instance.on_spawn()

    return instance

func _return_to_pool(instance: Node) -> void:
    if not instance in _in_use:
        return

    _in_use.erase(instance)

    if instance.has_method("on_despawn"):
        instance.on_despawn()

    instance.process_mode = Node.PROCESS_MODE_DISABLED
    instance.visible = false
    _available.append(instance)

func return_all() -> void:
    for instance in _in_use.duplicate():
        _return_to_pool(instance)
```

## Pooled Object Contract

Pooled objects should implement:
- `signal returned_to_pool` — emit when done (lifetime expired, hit something, etc.)
- `func on_spawn() -> void` — reset state when taken from pool
- `func on_despawn() -> void` — cleanup when returned to pool

```gdscript
# Example: pooled_bullet.gd
class_name PooledBullet
extends Area2D

signal returned_to_pool

@export var speed: float = 500.0
@export var lifetime: float = 5.0

var direction: Vector2
var _timer: float

func on_spawn() -> void:
    _timer = lifetime

func on_despawn() -> void:
    direction = Vector2.ZERO

func initialize(pos: Vector2, dir: Vector2) -> void:
    global_position = pos
    direction = dir.normalized()
    rotation = direction.angle()

func _physics_process(delta: float) -> void:
    position += direction * speed * delta
    _timer -= delta
    if _timer <= 0:
        returned_to_pool.emit()

func _on_body_entered(body: Node2D) -> void:
    if body.has_method("take_damage"):
        body.take_damage(10)
    returned_to_pool.emit()
```
