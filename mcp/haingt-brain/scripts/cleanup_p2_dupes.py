#!/usr/bin/env python3
"""P2 cleanup: collapse duplicate-spam + unify the chimera/the-ninth-bride label.

The audit found the same decision ("side-view camera locked") saved 7× — 6 within
one minute, across TWO project labels. This script:

  (A) Label unify:  project 'the-ninth-bride' → 'chimera' (canonical, matches the
      ~/Projects/chimera directory). memories + memory_fts.
  (B) Reversible dedup: cluster near-identical same-type/same-project memories
      (cosine ≥ THRESHOLD), keep the NEWEST as canonical, and HIDE the rest via a
      `canonical supersedes dup` edge (NOT a delete — recoverable with brain_unlink),
      repointing any inbound relations onto the canonical so the graph isn't orphaned.

Unlike consolidate.merge_duplicates (which hard-deletes at 0.95), nothing is removed.

Dry-run by default; pass --execute to apply.
"""

import argparse
import math
import struct
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_SRC))

from haingt_brain.db import connect  # noqa: E402

DEDUP_THRESHOLD = 0.93
OLD_LABEL = "the-ninth-bride"
NEW_LABEL = "chimera"


def _cosine(a: bytes, b: bytes) -> float:
    n = len(a) // 4
    va = struct.unpack(f"{n}f", a)
    vb = struct.unpack(f"{n}f", b)
    dot = sum(x * y for x, y in zip(va, vb))
    na = math.sqrt(sum(x * x for x in va))
    nb = math.sqrt(sum(x * x for x in vb))
    return dot / (na * nb) if na and nb else 0.0


def unify_labels(conn, dry_run=True) -> int:
    n = conn.execute("SELECT COUNT(*) FROM memories WHERE project = ?", (OLD_LABEL,)).fetchone()[0]
    if not dry_run and n:
        conn.execute("UPDATE memories SET project = ? WHERE project = ?", (NEW_LABEL, OLD_LABEL))
        try:
            conn.execute("UPDATE memory_fts SET project = ? WHERE project = ?", (NEW_LABEL, OLD_LABEL))
        except Exception:
            pass
        conn.commit()
    return n


def find_dup_clusters(conn, threshold=DEDUP_THRESHOLD):
    """Greedy newest-first clustering of near-identical same-type/same-project memories.

    Uses sqlite-vec ANN to fetch each memory's nearest neighbors (k=8) instead of a
    full O(n²) scan, then keeps neighbors above `threshold`. Returns list of
    (canonical_id, [dup_ids...]). Run AFTER unify_labels so cross-label copies share
    one project.
    """
    # Anti-series guard: same protection as contradiction.py so formulaic phase-logs
    # ("P-Combat-b" vs "P-Combat-c") are NEVER collapsed as duplicates.
    try:
        from haingt_brain.contradiction import is_series_pair
    except Exception:
        def is_series_pair(a, b):  # pragma: no cover
            return False

    def _norm_proj(p):
        # the-ninth-bride WILL be unified to chimera, so treat them as one project
        # even in dry-run (otherwise cross-label side-view copies never cluster).
        return NEW_LABEL if p == OLD_LABEL else p

    rows = conn.execute(
        "SELECT id, content, type, project, created_at FROM memories "
        "WHERE type NOT IN ('tool','session') ORDER BY created_at DESC"
    ).fetchall()
    meta = {r["id"]: r for r in rows}
    embs = {}
    for r in rows:
        v = conn.execute("SELECT embedding FROM memory_vectors WHERE memory_id=?", (r["id"],)).fetchone()
        if v:
            embs[r["id"]] = v["embedding"]

    assigned = set()
    clusters = []
    for r in rows:  # newest-first → first seen in a group is canonical
        cid = r["id"]
        if cid in assigned or cid not in embs:
            continue
        try:
            nbrs = conn.execute(
                "SELECT memory_id FROM memory_vectors WHERE embedding MATCH ? AND k = 8",
                (embs[cid],)).fetchall()
        except Exception:
            continue
        dups = []
        for nb in nbrs:
            oid = nb["memory_id"]
            o = meta.get(oid)
            if not o or oid == cid or oid in assigned or oid not in embs:
                continue
            if o["type"] != r["type"]:
                continue
            if _norm_proj(r["project"]) != _norm_proj(o["project"]) and \
               r["project"] is not None and o["project"] is not None:
                continue
            # only OLDER neighbors become dups of this newer canonical
            if (o["created_at"] or "") > (r["created_at"] or ""):
                continue
            if is_series_pair(r["content"], o["content"]):
                continue  # distinct-true phase-log siblings — never dedup
            if _cosine(embs[cid], embs[oid]) >= threshold:
                dups.append(oid)
        if dups:
            for d in dups:
                assigned.add(d)
            assigned.add(cid)
            clusters.append((cid, dups))
    return clusters


def _repoint_relations(conn, canonical, dup):
    """Move inbound/outbound edges of dup onto canonical (skip self-loops)."""
    for src, tgt, rtype in conn.execute(
        "SELECT source_id, target_id, relation_type FROM relations WHERE source_id=? OR target_id=?",
        (dup, dup),
    ).fetchall():
        ns = canonical if src == dup else src
        nt = canonical if tgt == dup else tgt
        if ns == nt:
            continue
        conn.execute("INSERT OR IGNORE INTO relations (source_id,target_id,relation_type,weight) VALUES (?,?,?,1.0)",
                     (ns, nt, rtype))
    conn.execute("DELETE FROM relations WHERE source_id=? OR target_id=?", (dup, dup))


def collapse_clusters(conn, clusters, dry_run=True) -> int:
    hidden = 0
    for canonical, dups in clusters:
        for dup in dups:
            hidden += 1
            if not dry_run:
                _repoint_relations(conn, canonical, dup)
                conn.execute(
                    "INSERT OR IGNORE INTO relations (source_id,target_id,relation_type,weight) "
                    "VALUES (?,?, 'supersedes', 1.0)", (canonical, dup))
                conn.execute(
                    "UPDATE memories SET importance = COALESCE(importance,0.5)*0.5 WHERE id=?", (dup,))
    if not dry_run:
        conn.commit()
    return hidden


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--threshold", type=float, default=DEDUP_THRESHOLD)
    args = ap.parse_args()
    dry = not args.execute
    conn = connect()

    relabeled = unify_labels(conn, dry_run=dry)
    clusters = find_dup_clusters(conn, threshold=args.threshold)
    hidden = collapse_clusters(conn, clusters, dry_run=dry)

    mode = "DRY-RUN" if dry else "EXECUTED"
    print(f"\n=== P2 cleanup [{mode}] (threshold={args.threshold}) ===")
    print(f"Label unify '{OLD_LABEL}' -> '{NEW_LABEL}': {relabeled} memories")
    print(f"Dup clusters: {len(clusters)}  | memories hidden (reversible supersedes): {hidden}")
    for canonical, dups in clusters:
        c = conn.execute("SELECT substr(content,1,70) c, project FROM memories WHERE id=?", (canonical,)).fetchone()
        print(f"\n  canonical {canonical} [{c['project']}]: {c['c']}")
        for d in dups:
            dc = conn.execute("SELECT substr(content,1,70) c FROM memories WHERE id=?", (d,)).fetchone()
            print(f"    hide {d}: {dc['c']}")
    if dry:
        print("\n(dry-run — nothing written. Re-run with --execute to apply.)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
