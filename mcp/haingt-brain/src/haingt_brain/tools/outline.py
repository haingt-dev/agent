"""brain_outline: Extract file structure with line numbers for targeted reads."""

import json
import re
from pathlib import Path


def brain_outline(filepath: str) -> dict:
    """
    Extract file structure (headings, functions, keys) from a file.
    Enables targeted Read calls with offset+limit instead of reading entire files.

    Args:
        filepath: Absolute path or ~-expanded path to the file.

    Returns:
        dict with file metadata and outline entries.
        On error: {"error": "..."}
    """
    try:
        path = Path(filepath).expanduser()
    except Exception as e:
        return {"error": f"Invalid path: {e}"}

    if not path.exists():
        return {"error": f"File not found: {filepath}"}

    if not path.is_file():
        return {"error": f"Not a file: {filepath}"}

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    lines = content.splitlines()
    total_lines = len(lines)
    ext = path.suffix.lstrip(".").lower()

    try:
        entries = _dispatch(ext, lines)
    except Exception as e:
        entries = [{"error": f"Outline extraction failed: {e}"}]

    return {
        "file": str(path.resolve()),
        "total_lines": total_lines,
        "type": ext or "unknown",
        "outline": entries,
    }


def _dispatch(ext: str, lines: list) -> list:
    if ext == "md":
        return _outline_md(lines)
    elif ext == "py":
        return _outline_py(lines)
    elif ext == "gd":
        return _outline_gd(lines)
    elif ext in ("yml", "yaml"):
        return _outline_yaml(lines)
    elif ext == "json":
        return _outline_json(lines)
    elif ext in ("sh", "bash"):
        return _outline_sh(lines)
    else:
        return _outline_fallback(lines)


def _outline_md(lines: list) -> list:
    return [
        {"line": i + 1, "text": line.rstrip()}
        for i, line in enumerate(lines)
        if line.startswith("#")
    ][:40]


def _outline_py(lines: list) -> list:
    pattern = re.compile(r"^(    |  )?(?:async )?(?:def |class )")
    return [
        {"line": i + 1, "text": line.rstrip()}
        for i, line in enumerate(lines)
        if pattern.match(line)
    ][:30]


def _outline_gd(lines: list) -> list:
    pattern = re.compile(
        r"^(?:func |class |class_name |var |signal |@export|@onready)"
    )
    return [
        {"line": i + 1, "text": line.rstrip()}
        for i, line in enumerate(lines)
        if pattern.match(line)
    ][:30]


def _outline_yaml(lines: list) -> list:
    pattern = re.compile(r"^[a-zA-Z_-]")
    return [
        {"line": i + 1, "text": line.rstrip()}
        for i, line in enumerate(lines)
        if pattern.match(line)
    ][:20]


def _outline_json(lines: list) -> list:
    try:
        data = json.loads("\n".join(lines))
        if isinstance(data, dict):
            return [
                {
                    "key": k,
                    "type": type(v).__name__,
                    "size": len(v) if isinstance(v, (dict, list)) else None,
                }
                for k, v in list(data.items())[:20]
            ]
        elif isinstance(data, list):
            return [
                {
                    "type": "array",
                    "length": len(data),
                    "first_type": type(data[0]).__name__ if data else "empty",
                }
            ]
        else:
            return [{"type": type(data).__name__, "value_preview": str(data)[:100]}]
    except Exception:
        # Fallback: lines with "key": pattern
        return [
            {"line": i + 1, "text": line.rstrip()}
            for i, line in enumerate(lines)
            if '"' in line and ":" in line
        ][:20]


def _outline_sh(lines: list) -> list:
    pattern = re.compile(
        r"^[a-zA-Z_][a-zA-Z0-9_]*\(\)\s*\{|^function\s+"
    )
    return [
        {"line": i + 1, "text": line.rstrip()}
        for i, line in enumerate(lines)
        if pattern.match(line)
    ][:20]


def _outline_fallback(lines: list) -> list:
    return [
        {"line": i + 1, "text": line.rstrip()}
        for i, line in enumerate(lines[:8])
    ]
