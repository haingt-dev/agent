"""brain_unlink: Delete a single relation edge (the manual inverse of an auto/batch belief-revision link).

This is the "brake" for the auto-edge writers (contradiction.py / supersede_pass): every
automatically-created supersedes/contradicts edge can be undone here without deleting either
memory. Removing a `supersedes` edge optionally restores the importance the save-path demoted.
"""

import sqlite3

VALID_RELATION_TYPES = {
    "causes", "fixes", "contradicts", "relates_to",
    "used_in", "part_of", "supersedes",
}


def brain_unlink(
    conn: sqlite3.Connection,
    source_id: str,
    target_id: str,
    relation_type: str,
    restore_importance: bool = True,
) -> dict:
    """Delete a single relation edge between two memories.

    Args:
        source_id: The source memory ID of the edge.
        target_id: The target memory ID of the edge.
        relation_type: One of causes, fixes, contradicts, relates_to, used_in, part_of, supersedes.
        restore_importance: For a `supersedes` edge, undo the save-time importance demotion
            on the target (importance was halved when the edge was created). Default True.

    Returns:
        dict with status. status is one of: "unlinked", "not_found", "invalid_relation_type".
    """
    if relation_type not in VALID_RELATION_TYPES:
        return {
            "status": "invalid_relation_type",
            "relation_type": relation_type,
            "valid": sorted(VALID_RELATION_TYPES),
        }

    edge = conn.execute(
        "SELECT 1 FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = ?",
        (source_id, target_id, relation_type),
    ).fetchone()
    if not edge:
        return {
            "status": "not_found",
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
        }

    importance_restored: float | bool = False
    if relation_type == "supersedes" and restore_importance:
        # Inverse of the save-path demotion (importance *= 0.5). Cap at 1.0.
        target = conn.execute(
            "SELECT importance FROM memories WHERE id = ?", (target_id,)
        ).fetchone()
        if target is not None and target["importance"] is not None:
            restored = min(1.0, target["importance"] * 2)
            conn.execute(
                "UPDATE memories SET importance = ? WHERE id = ?", (restored, target_id)
            )
            importance_restored = round(restored, 3)

    conn.execute(
        "DELETE FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = ?",
        (source_id, target_id, relation_type),
    )
    conn.commit()

    return {
        "status": "unlinked",
        "source_id": source_id,
        "target_id": target_id,
        "relation_type": relation_type,
        "importance_restored": importance_restored,
    }
