# Save System Pattern

JSON-based save system. Uses JSON (not .tres) because class renames break .tres deserialization.

## SaveManager (Autoload)

```gdscript
class_name SaveManager
extends Node

const SAVE_DIR := "user://saves/"
const SAVE_EXT := ".save"

signal save_completed(slot: int)
signal load_completed(slot: int)
signal save_error(message: String)

func _ready() -> void:
    DirAccess.make_dir_recursive_absolute(SAVE_DIR)

func save_game(slot: int, data: Dictionary) -> void:
    var path := _slot_path(slot)
    data["_meta"] = {
        "timestamp": Time.get_datetime_string_from_system(),
        "version": ProjectSettings.get_setting("application/config/version", "1.0"),
    }

    var json := JSON.stringify(data, "\t")
    var file := FileAccess.open(path, FileAccess.WRITE)
    if file == null:
        save_error.emit("Cannot write: %s" % path)
        return

    file.store_string(json)
    file.close()
    save_completed.emit(slot)

func load_game(slot: int) -> Dictionary:
    var path := _slot_path(slot)
    if not FileAccess.file_exists(path):
        return {}

    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        save_error.emit("Cannot read: %s" % path)
        return {}

    var parsed := JSON.parse_string(file.get_as_text())
    file.close()

    if parsed == null:
        save_error.emit("Corrupt save: %s" % path)
        return {}

    load_completed.emit(slot)
    return parsed

func has_save(slot: int) -> bool:
    return FileAccess.file_exists(_slot_path(slot))

func get_save_preview(slot: int) -> Dictionary:
    var data := load_game(slot)
    return data.get("_meta", {})

func delete_save(slot: int) -> void:
    var path := _slot_path(slot)
    if FileAccess.file_exists(path):
        DirAccess.remove_absolute(path)

func _slot_path(slot: int) -> String:
    return SAVE_DIR + "slot_%d%s" % [slot, SAVE_EXT]
```

## Saveable Component (attach to nodes)

```gdscript
class_name Saveable
extends Node

@export var save_id: String

func _ready() -> void:
    if save_id.is_empty():
        save_id = str(get_path())

func get_save_data() -> Dictionary:
    var parent := get_parent()
    var data := {"id": save_id}
    if parent is Node2D:
        data["position"] = {"x": parent.position.x, "y": parent.position.y}
    if parent.has_method("get_custom_save_data"):
        data.merge(parent.get_custom_save_data())
    return data

func load_save_data(data: Dictionary) -> void:
    var parent := get_parent()
    if data.has("position") and parent is Node2D:
        parent.position = Vector2(data.position.x, data.position.y)
    if parent.has_method("load_custom_save_data"):
        parent.load_custom_save_data(data)
```
