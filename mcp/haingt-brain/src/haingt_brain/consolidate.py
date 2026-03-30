"""Auto-consolidation: merge duplicates, decay unused patterns, consolidate old sessions."""

import json
import sqlite3
import struct
from datetime import datetime, timedelta

from .db import serialize_embedding


def consolidate_all(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    """Run all consolidation strategies. Returns a report of actions taken."""
    report = {
        "duplicates_merged": 0,
        "patterns_decayed": 0,
        "sessions_consolidated": 0,
        "importance_decayed": 0,
        "weak_pruned": 0,
        "details": [],
    }

    r1 = merge_duplicates(conn, threshold=0.80, dry_run=dry_run)
    report["duplicates_merged"] = r1["merged"]
    report["details"].extend(r1["details"])

    r2 = decay_patterns(conn, days_inactive=90, dry_run=dry_run)
    report["patterns_decayed"] = r2["decayed"]
    report["details"].extend(r2["details"])

    r3 = consolidate_sessions(conn, older_than_days=30, dry_run=dry_run)
    report["sessions_consolidated"] = r3["consolidated"]
    report["details"].extend(r3["details"])

    r4 = decay_importance(conn, dry_run=dry_run)
    report["importance_decayed"] = r4["decayed"]
    report["weak_pruned"] = r4["pruned"]
    report["details"].extend(r4["details"])

    # Record consolidation timestamp
    _record_consolidation(conn)

    return report


def merge_duplicates(
    conn: sqlite3.Connection,
    threshold: float = 0.80,
    dry_run: bool = False,
) -> dict:
    """
    Find and merge near-duplicate memories using sqlite-vec ANN search.

    For each non-tool memory, queries sqlite-vec for nearest neighbors.
    O(n·k) instead of O(n²) — scales to 1000+ memories.

    Strategy: keep the memory with higher access_count (or newer if tied).
    The other gets deleted. Tags are merged.
    """
    result = {"merged": 0, "details": []}

    # Get all non-tool memories
    rows = conn.execute(
        "SELECT id, content, type, tags, access_count, created_at FROM memories WHERE type != 'tool'"
    ).fetchall()

    if len(rows) < 2:
        return result

    # Build lookup for quick access
    mem_by_id = {r["id"]: dict(r) for r in rows}
    to_delete: set[str] = set()

    for row in rows:
        if row["id"] in to_delete:
            continue

        # Get this memory's embedding
        vec_row = conn.execute(
            "SELECT embedding FROM memory_vectors WHERE memory_id = ?", (row["id"],)
        ).fetchone()
        if not vec_row:
            continue

        # Use sqlite-vec ANN to find nearest neighbors (k=5 is enough for duplicate detection)
        try:
            neighbors = conn.execute(
                """SELECT memory_id, distance FROM memory_vectors
                   WHERE embedding MATCH ? AND k = 6""",
                (vec_row["embedding"],),
            ).fetchall()
        except sqlite3.OperationalError:
            continue

        for neighbor in neighbors:
            nb_id = neighbor["memory_id"]
            if nb_id == row["id"] or nb_id in to_delete:
                continue

            nb = mem_by_id.get(nb_id)
            if not nb or nb["type"] != row["type"]:
                continue  # Only merge same-type

            # Convert distance to cosine similarity
            # sqlite-vec returns L2 distance by default for FLOAT vectors
            # For normalized embeddings: cosine_sim ≈ 1 - (distance² / 2)
            # But safer to compute cosine directly
            nb_vec = conn.execute(
                "SELECT embedding FROM memory_vectors WHERE memory_id = ?", (nb_id,)
            ).fetchone()
            if not nb_vec:
                continue

            sim = _cosine_from_bytes(vec_row["embedding"], nb_vec["embedding"])
            if sim < threshold:
                continue

            # Determine which to keep
            row_dict = dict(row)
            if (row_dict["access_count"] > nb["access_count"]) or (
                row_dict["access_count"] == nb["access_count"]
                and row_dict["created_at"] >= nb["created_at"]
            ):
                keep, remove = row_dict, nb
            else:
                keep, remove = nb, row_dict

            detail = f"Merge [{remove['type']}] \"{remove['content'][:60]}\" into \"{keep['content'][:60]}\" (sim={sim:.3f})"
            result["details"].append(detail)

            if not dry_run:
                # Merge tags
                tags_keep = json.loads(keep["tags"]) if keep["tags"] else []
                tags_remove = json.loads(remove["tags"]) if remove["tags"] else []
                merged_tags = list(set(tags_keep + tags_remove))
                conn.execute(
                    "UPDATE memories SET tags = ? WHERE id = ?",
                    (json.dumps(merged_tags), keep["id"]),
                )

                # Delete the duplicate
                _delete_memory(conn, remove["id"])

            to_delete.add(remove["id"])
            result["merged"] += 1

    if not dry_run:
        conn.commit()

    return result


def decay_patterns(
    conn: sqlite3.Connection,
    days_inactive: int = 90,
    dry_run: bool = False,
) -> dict:
    """
    Remove pattern memories that haven't been accessed in `days_inactive` days.

    Only affects type='pattern'. Other types are permanent.
    """
    result = {"decayed": 0, "details": []}

    cutoff = (datetime.utcnow() - timedelta(days=days_inactive)).isoformat()

    stale = conn.execute(
        """SELECT id, content, access_count, last_accessed, created_at FROM memories
           WHERE type = 'pattern'
             AND (last_accessed IS NULL OR last_accessed < ?)
             AND created_at < ?""",
        (cutoff, cutoff),
    ).fetchall()

    for row in stale:
        detail = f"Decay pattern: \"{row['content'][:60]}\" (accessed {row['access_count']}x, last: {row['last_accessed'] or 'never'})"
        result["details"].append(detail)

        if not dry_run:
            _delete_memory(conn, row["id"])

        result["decayed"] += 1

    if not dry_run:
        conn.commit()

    return result


def consolidate_sessions(
    conn: sqlite3.Connection,
    older_than_days: int = 30,
    dry_run: bool = False,
) -> dict:
    """
    Consolidate old session summaries into weekly digests.

    Sessions older than `older_than_days` get grouped by week.
    Each week's sessions are merged into one summary memory.
    Original session records are kept (for audit) but marked consolidated.
    """
    result = {"consolidated": 0, "details": []}

    cutoff = (datetime.utcnow() - timedelta(days=older_than_days)).isoformat()

    old_sessions = conn.execute(
        """SELECT id, project, summary, started_at, ended_at FROM sessions
           WHERE ended_at IS NOT NULL
             AND summary IS NOT NULL
             AND ended_at < ?
           ORDER BY started_at""",
        (cutoff,),
    ).fetchall()

    if len(old_sessions) < 2:
        return result

    # Group by (project, ISO week)
    weeks: dict[str, list] = {}
    for s in old_sessions:
        try:
            dt = datetime.fromisoformat(s["started_at"])
            week_key = f"{s['project'] or 'global'}_{dt.isocalendar()[0]}_W{dt.isocalendar()[1]:02d}"
        except (ValueError, TypeError):
            continue
        weeks.setdefault(week_key, []).append(s)

    for week_key, sessions in weeks.items():
        if len(sessions) < 2:
            continue  # Only consolidate if 2+ sessions in a week

        summaries = [s["summary"] for s in sessions if s["summary"]]
        if not summaries:
            continue

        combined = f"Week {week_key}: {len(sessions)} sessions.\n" + "\n".join(
            f"- {s}" for s in summaries
        )

        detail = f"Consolidate {len(sessions)} sessions into weekly digest: {week_key}"
        result["details"].append(detail)

        if not dry_run:
            from .tools.save import brain_save
            brain_save(
                conn, combined, "session",
                tags=["weekly-digest", week_key],
                metadata={"source": "consolidation", "source_session_ids": [s["id"] for s in sessions]},
            )

            # Delete old session summaries from memories table (session records kept)
            for s in sessions:
                conn.execute(
                    "DELETE FROM memories WHERE type = 'session' AND content = ?",
                    (s["summary"],),
                )

        result["consolidated"] += len(sessions)

    if not dry_run:
        conn.commit()

    return result


def decay_importance(
    conn: sqlite3.Connection,
    dry_run: bool = False,
) -> dict:
    """
    Apply Ebbinghaus time-decay to all memory importance values.

    Exemptions:
    - preference type (permanent, never decays)
    - tool type (auto-managed by toolbox discovery)
    - memories accessed within last 7 days (recently active)

    Memories whose importance decays below 0.05 are pruned.
    """
    from .importance import compute_decay, compute_graph_boost

    result = {"decayed": 0, "pruned": 0, "graph_boosted": 0, "details": []}
    PRUNE_THRESHOLD = 0.05

    rows = conn.execute("""
        SELECT id, type, content, importance, access_count, last_accessed, created_at
        FROM memories
        WHERE type NOT IN ('preference', 'tool')
          AND (last_accessed IS NULL OR last_accessed < datetime('now', '-7 days'))
    """).fetchall()

    for row in rows:
        last = row["last_accessed"] or row["created_at"]
        try:
            dt = datetime.fromisoformat(last)
            days = (datetime.utcnow() - dt).total_seconds() / 86400
        except (ValueError, TypeError):
            continue

        old_imp = row["importance"] if row["importance"] is not None else 0.5

        # Graph boost: hub memories (many connections) resist decay
        graph_boost = compute_graph_boost(conn, row["id"])
        if graph_boost > 0:
            old_imp = min(1.0, old_imp + graph_boost)
            result["graph_boosted"] += 1

        new_imp = compute_decay(old_imp, days)

        if new_imp < PRUNE_THRESHOLD:
            result["details"].append(
                f"Prune [{row['type']}] \"{row['content'][:60]}\" "
                f"(importance {old_imp:.3f} → {new_imp:.3f})"
            )
            if not dry_run:
                _delete_memory(conn, row["id"])
            result["pruned"] += 1
        elif abs(new_imp - old_imp) > 0.01:
            if not dry_run:
                conn.execute(
                    "UPDATE memories SET importance = ? WHERE id = ?",
                    (round(new_imp, 4), row["id"]),
                )
            result["decayed"] += 1

    if not dry_run:
        conn.commit()

    return result


def should_consolidate(conn: sqlite3.Connection, interval_days: int = 7) -> bool:
    """Check if consolidation should run based on last run time."""
    row = conn.execute(
        """SELECT value FROM brain_meta WHERE key = 'last_consolidation'"""
    ).fetchone()
    if not row:
        return True

    try:
        last = datetime.fromisoformat(row["value"])
        return datetime.utcnow() - last > timedelta(days=interval_days)
    except (ValueError, TypeError):
        return True


def _record_consolidation(conn: sqlite3.Connection) -> None:
    """Record the current time as last consolidation."""
    conn.execute(
        """INSERT OR REPLACE INTO brain_meta (key, value) VALUES ('last_consolidation', datetime('now'))"""
    )
    conn.commit()


def _delete_memory(conn: sqlite3.Connection, memory_id: str) -> None:
    """Delete a memory and all its associated data."""
    conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (memory_id,))
    conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
    conn.execute("DELETE FROM relations WHERE source_id = ? OR target_id = ?", (memory_id, memory_id))
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))


def _cosine_from_bytes(a_bytes: bytes, b_bytes: bytes) -> float:
    """Compute cosine similarity between two raw embedding byte buffers."""
    import math
    n = len(a_bytes) // 4
    a = struct.unpack(f"{n}f", a_bytes)
    b = struct.unpack(f"{n}f", b_bytes)
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
