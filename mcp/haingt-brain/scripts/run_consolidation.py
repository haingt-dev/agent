#!/usr/bin/env python3
"""Weekly consolidation runner (cron). Audit 2026-06-12.

Runs merge + sessions + cluster. The 'decay' and 'patterns' strategies are
EXCLUDED on purpose: both act on last_accessed, which was systematically
under-recorded until injection telemetry landed (prompt-context.py bumps
access_count since 2026-06-12). Re-evaluate enabling them after ~4 weeks of
accumulated access data, and retune compute_decay first — current curve
prunes a never-recalled importance-0.8 memory in ~60 days.

Cron: 30 23 * * 0 (Sunday, 30 min after the daily backup bundle starts, so
the morning backup always holds pre-consolidation state).
Log: ~/.local/share/haingt-brain/consolidation.log
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"
LOG_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "consolidation.log"
STRATEGIES = {"merge", "sessions", "cluster"}


def load_env() -> None:
    env_file = REPO / ".env"
    if not env_file.exists():
        return
    import os
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    load_env()
    import sqlite_vec
    from haingt_brain.consolidate import consolidate_all

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    entry = {"ts": datetime.now().isoformat(timespec="seconds")}
    try:
        # TTL purge: pre-compact snapshots are post-compact continuity aids
        # (98% never recalled after day 1, vector-less, dedup-invisible) —
        # they re-accumulate between runs, so purge >14d each week.
        from haingt_brain.consolidate import _delete_memory

        stale = conn.execute(
            """SELECT id FROM memories
               WHERE type = 'session'
                 AND json_extract(metadata, '$.source') = 'pre-compact-hook'
                 AND created_at < datetime('now', '-14 days')"""
        ).fetchall()
        for (sid,) in stale:
            _delete_memory(conn, sid)
        conn.commit()
        entry["snapshots_purged"] = len(stale)

        report = consolidate_all(conn, dry_run=False, strategies=STRATEGIES)
        entry["status"] = report.get("status", "ok")
        entry["merged"] = report.get("duplicates_merged", 0)
        entry["sessions"] = report.get("sessions_consolidated", 0)
        entry["clusters"] = report.get("clusters_synthesized", 0)
        if report.get("memory_limit_warnings"):
            entry["memory_warnings"] = report["memory_limit_warnings"]
        rc = 0
    except Exception as e:
        entry["status"] = "error"
        entry["error"] = f"{type(e).__name__}: {e}"
        rc = 1
    finally:
        conn.close()

    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps(entry, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
