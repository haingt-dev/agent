#!/usr/bin/env python3
"""Backfill cleanup for the consolidation feedback loop bug.

Background
----------
Before the fix in `consolidate.py:480` (exclude prior synthesis nodes),
`cluster_and_synthesize` would re-cluster its own previous output, spawning
near-identical synthesis memories every run. This script cleans up the
residue: duplicate "consolidation"-source memories that have already
accumulated in the production DB.

Two phases:

Phase A — Run `merge_duplicates(threshold=0.80)`. Synthesis duplicates that
exceed the similarity threshold get merged. Strategy keeps the row with the
higher `access_count`; verified that originals win (synthesis avg access ~0.04).

Phase B — Targeted DELETE for residual loop-spawn that didn't dedup
(different enough wording but obviously redundant). Heuristic: small
cluster_size (<=4) AND created on/after the bug-surfacing date.

Usage
-----
    uv run python scripts/backfill_consolidation_loop.py            # dry-run
    uv run python scripts/backfill_consolidation_loop.py --execute  # apply
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from haingt_brain.consolidate import _delete_memory, merge_duplicates
from haingt_brain.db import connect


# Loop bug surfaced around 2026-05-07 onward (3 days before the audit on
# 2026-05-14). Older "consolidation" rows are likely legitimate weekly
# digests from `consolidate_sessions`, not loop spawn.
CUTOFF_DATE = "2026-05-07"
LOOP_CLUSTER_SIZE_MAX = 4


def count_consolidation_rows(conn, recent_only: bool = False) -> int:
    sql = """
        SELECT COUNT(*) FROM memories
        WHERE json_extract(metadata, '$.source') = 'consolidation'
    """
    if recent_only:
        sql += f" AND created_at >= '{CUTOFF_DATE}'"
    return conn.execute(sql).fetchone()[0]


def find_loop_spawn(conn) -> list[dict]:
    """Find consolidation rows with small cluster_size — likely loop residue."""
    rows = conn.execute(
        """
        SELECT m.id,
               substr(m.content, 1, 80) AS preview,
               m.created_at,
               (
                   SELECT COUNT(*)
                   FROM relations r
                   WHERE r.target_id = m.id
                     AND r.relation_type = 'part_of'
               ) AS cluster_size
        FROM memories m
        WHERE json_extract(m.metadata, '$.source') = 'consolidation'
          AND m.created_at >= ?
        """,
        (CUTOFF_DATE,),
    ).fetchall()
    return [
        dict(r) for r in rows if (r["cluster_size"] or 0) <= LOOP_CLUSTER_SIZE_MAX
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes. Default is dry-run.",
    )
    args = parser.parse_args()
    dry_run = not args.execute

    conn = connect()

    before_total = count_consolidation_rows(conn, recent_only=False)
    before_recent = count_consolidation_rows(conn, recent_only=True)
    print(f"Before:  {before_total} total consolidation rows ({before_recent} since {CUTOFF_DATE})")
    print()

    # ── Phase A: merge_duplicates ─────────────────────────────────────
    print(f"Phase A — merge_duplicates(threshold=0.80) [dry_run={dry_run}]")
    phase_a = merge_duplicates(conn, threshold=0.80, dry_run=dry_run)
    print(f"  merged: {phase_a['merged']}")
    if phase_a.get("details"):
        print("  sample:")
        for d in phase_a["details"][:5]:
            print(f"    - {d}")
        if len(phase_a["details"]) > 5:
            print(f"    ... and {len(phase_a['details']) - 5} more")
    print()

    # ── Phase B: targeted residual cleanup ────────────────────────────
    print(f"Phase B — targeted DELETE for loop residue (cluster_size <= {LOOP_CLUSTER_SIZE_MAX}, since {CUTOFF_DATE})")
    candidates = find_loop_spawn(conn)
    print(f"  candidates: {len(candidates)}")
    if candidates:
        print("  sample:")
        for c in candidates[:5]:
            print(f"    - [{c['id']}] cluster={c['cluster_size']} | {c['preview']}")
        if len(candidates) > 5:
            print(f"    ... and {len(candidates) - 5} more")

    if not dry_run and candidates:
        for c in candidates:
            _delete_memory(conn, c["id"])
        conn.commit()
        print(f"  DELETED {len(candidates)} rows")

    print()

    after_total = count_consolidation_rows(conn, recent_only=False)
    after_recent = count_consolidation_rows(conn, recent_only=True)
    print(f"After:   {after_total} total consolidation rows ({after_recent} since {CUTOFF_DATE})")
    print(f"Removed: {before_total - after_total} total ({before_recent - after_recent} since {CUTOFF_DATE})")

    if dry_run:
        print()
        print("DRY RUN — no changes applied. Re-run with --execute to apply.")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
