#!/usr/bin/env python3
"""Re-audit: measure contradictory/duplicate memory pairs in the live brain.

Read-only. The gate for flipping BRAIN_AUTO_SUPERSEDE live: run before and after
the back-fill / cleanup / supersede_pass to see residual unlinked-contradiction
drop. Counts high-similarity same-subject pairs and how many already carry a
supersedes/contradicts edge (= handled) vs none (= still co-surface in recall).

Usage:
  python scripts/audit_contradictions.py            # full report
  python scripts/audit_contradictions.py --json      # machine-readable summary
"""

import argparse
import json
import math
import struct
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_SRC))

from haingt_brain.db import connect  # noqa: E402

DURABLE = ("decision", "discovery", "pattern", "preference", "entity")
K = 8
FLOOR = 0.72
THRESHOLDS = [0.72, 0.78, 0.82, 0.86, 0.90, 0.94]


def _cosine(emb_a, emb_b):
    return sum(x * y for x, y in zip(emb_a, emb_b))


def run_audit(conn):
    qm = ",".join("?" * len(DURABLE))
    mems = {r["id"]: dict(r) for r in conn.execute(
        f"SELECT id, type, project, created_at FROM memories WHERE type IN ({qm})", DURABLE)}

    emb = {}
    for r in conn.execute("SELECT memory_id, embedding FROM memory_vectors"):
        mid = r["memory_id"]
        if mid not in mems:
            continue
        raw = r["embedding"]
        n = len(raw) // 4
        v = struct.unpack(f"{n}f", raw)
        nrm = math.sqrt(sum(x * x for x in v)) or 1.0
        emb[mid] = [x / nrm for x in v]

    edges = {}
    for r in conn.execute("SELECT source_id, target_id, relation_type FROM relations"):
        key = frozenset((r["source_id"], r["target_id"]))
        edges.setdefault(key, set()).add(r["relation_type"])

    pairset = {}
    for mid in emb:
        raw = conn.execute("SELECT embedding FROM memory_vectors WHERE memory_id=?", (mid,)).fetchone()
        if not raw:
            continue
        try:
            nbrs = conn.execute(
                "SELECT memory_id FROM memory_vectors WHERE embedding MATCH ? AND k=?",
                (raw["embedding"], K)).fetchall()
        except Exception:
            continue
        for nb in nbrs:
            oid = nb["memory_id"]
            if oid == mid or oid not in emb:
                continue
            key = tuple(sorted((mid, oid)))
            if key in pairset:
                continue
            s = _cosine(emb[mid], emb[oid])
            if s >= FLOOR:
                pairset[key] = s

    pairs = []
    for (a, b), s in pairset.items():
        rel = edges.get(frozenset((a, b)), set())
        pairs.append({
            "sim": s,
            "linked_super": bool(rel & {"supersedes", "contradicts"}),
            "linked_any": bool(rel),
        })

    edge_counts = {}
    for r in conn.execute("SELECT relation_type, COUNT(*) n FROM relations GROUP BY relation_type"):
        edge_counts[r["relation_type"]] = r["n"]

    table = []
    for t in THRESHOLDS:
        sub = [p for p in pairs if p["sim"] >= t]
        table.append({
            "threshold": t,
            "all": len(sub),
            "unlinked": len([p for p in sub if not p["linked_super"]]),
            "super_linked": len([p for p in sub if p["linked_super"]]),
            "any_linked": len([p for p in sub if p["linked_any"]]),
        })

    return {
        "memories_durable": len(mems),
        "with_embeddings": len(emb),
        "total_pairs_ge_floor": len(pairs),
        "edge_counts": edge_counts,
        "by_threshold": table,
        "residual_unlinked_082": next(r["unlinked"] for r in table if r["threshold"] == 0.82),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    conn = connect()
    rep = run_audit(conn)
    conn.close()

    if args.json:
        print(json.dumps(rep, indent=2))
        return 0

    print("\n=== Contradiction re-audit (read-only) ===")
    print(f"durable memories: {rep['memories_durable']}  (with embeddings: {rep['with_embeddings']})")
    print(f"edges: {rep['edge_counts']}")
    print(f"total pairs >= {FLOOR}: {rep['total_pairs_ge_floor']}")
    print(f"\n{'thresh':>7} | {'all':>5} | {'unlinked':>8} | {'super/contra-linked':>19} | {'any-linked':>10}")
    for r in rep["by_threshold"]:
        print(f"{r['threshold']:>7} | {r['all']:>5} | {r['unlinked']:>8} | {r['super_linked']:>19} | {r['any_linked']:>10}")
    print(f"\nRESIDUAL unlinked-contradiction (sim>=0.82, no super/contradicts edge): "
          f"{rep['residual_unlinked_082']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
