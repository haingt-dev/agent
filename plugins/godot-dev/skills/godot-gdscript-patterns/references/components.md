# Component System Pattern

Reusable behavior components attached as child nodes. Connect via signals in the parent.

## HealthComponent

```gdscript
class_name HealthComponent
extends Node

signal health_changed(current: int, maximum: int)
signal damaged(amount: int, source: Node)
signal healed(amount: int)
signal died

@export var max_health: int = 100
@export var invincibility_time: float = 0.0

var current_health: int:
    set(value):
        var old := current_health
        current_health = clampi(value, 0, max_health)
        if current_health != old:
            health_changed.emit(current_health, max_health)

var _invincible: bool = false

func _ready() -> void:
    current_health = max_health

func take_damage(amount: int, source: Node = null) -> int:
    if _invincible or current_health <= 0:
        return 0
    var actual := mini(amount, current_health)
    current_health -= actual
    damaged.emit(actual, source)
    if current_health <= 0:
        died.emit()
    elif invincibility_time > 0:
        _start_invincibility()
    return actual

func heal(amount: int) -> int:
    var actual := mini(amount, max_health - current_health)
    current_health += actual
    if actual > 0:
        healed.emit(actual)
    return actual

func _start_invincibility() -> void:
    _invincible = true
    await get_tree().create_timer(invincibility_time).timeout
    _invincible = false
```

## HitboxComponent (deals damage)

```gdscript
class_name HitboxComponent
extends Area2D

signal hit(hurtbox: HurtboxComponent)

@export var damage: int = 10
@export var knockback_force: float = 200.0

var owner_node: Node

func _ready() -> void:
    owner_node = get_parent()
    area_entered.connect(_on_area_entered)

func _on_area_entered(area: Area2D) -> void:
    if area is HurtboxComponent:
        var hurtbox := area as HurtboxComponent
        if hurtbox.owner_node != owner_node:
            hit.emit(hurtbox)
            hurtbox.receive_hit(self)
```

## HurtboxComponent (receives damage)

```gdscript
class_name HurtboxComponent
extends Area2D

signal hurt(hitbox: HitboxComponent)

@export var health_component: HealthComponent

var owner_node: Node

func _ready() -> void:
    owner_node = get_parent()

func receive_hit(hitbox: HitboxComponent) -> void:
    hurt.emit(hitbox)
    if health_component:
        health_component.take_damage(hitbox.damage, hitbox.owner_node)
```

## Wiring in Parent Scene

```
Enemy (CharacterBody2D)
├── HealthComponent
├── HurtboxComponent (connects to HealthComponent via @export)
├── HitboxComponent
└── Sprite2D
```

Connect signals in the parent script or editor:
```gdscript
func _ready() -> void:
    $HealthComponent.died.connect(_on_died)
    $HurtboxComponent.hurt.connect(_on_hurt)
```
