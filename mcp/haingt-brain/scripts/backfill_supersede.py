#!/usr/bin/env python3
"""P1 back-fill: memories that self-declare superseded but have no supersedes edge.

The audit found ~35 memories whose CONTENT says "[SUPERSEDED ...]", "RETIRED",
"supersedes X", "now corrected", etc., yet carry no `supersedes` relation — so
SUPERSEDED_FILTER never hides them and recall keeps serving stale facts live.

Edge direction is the highest-stakes decision (supersedes hides the TARGET), and
the markers come in TWO grammars that imply OPPOSITE directions:

  PASSIVE — "I am superseded":  "[SUPERSEDED ... see X]", "RETIRED", "OLD decision"
            → the CURRENT memory is dead; the referenced/sibling is the replacement.
            edge = (source = replacement, target = THIS)   # hide THIS
  ACTIVE  — "I supersede X":    "supersedes X", "CORRECTION to X", "REVERSED ... X"
            → the CURRENT memory is alive and kills the referenced one.
            edge = (source = THIS, target = X)             # hide X

Tiers:
  P1a (deterministic): content embeds a valid 12-hex id → direction from grammar.
  P1b (descriptive):   no id → ANN-resolve the newest same-project sibling.
       high confidence (cosine ≥ 0.90, single candidate) → hide.
       low confidence  → DEMOTE importance + metadata flag (recall still surfaces
                         it via the read-time conflict-surface), never hard-hide.

Idempotent. Dry-run by default; pass --execute to write. Affected target ids are
logged to brain_meta.p1_backfill_affected_ids so the July-11 decay re-enable can
exclude them from access-decay (they were demoted here, not by genuine disuse).

Usage:
  python scripts/backfill_supersede.py            # dry-run report
  python scripts/backfill_supersede.py --execute  # apply
"""

import argparse
import json
import re
import struct
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_SRC))

from haingt_brain.db import connect  # noqa: E402

HEX = re.compile(r"\b[0-9a-f]{12}\b")
PASSIVE_LEAD = re.compile(r"^\s*\[?\s*(?:SUPERSEDED|OUTDATED|OBSOLETE)\b", re.I)
PASSIVE_SELF = re.compile(r"\bRETIRED\b|\bOLD decision\b|\bnow corrected\b|no longer accurate", re.I)
ACTIVE = re.compile(r"\bsupersed\w+\b|\bCORRECTION to\b|\bREVERSED\b|\breverses\b", re.I)
ANY_MARKER = re.compile(r"supersed\w*|RETIRED|now corrected|no longer accurate|REVERSED|CORRECTION to", re.I)

HIGH_COSINE = 0.90
MIN_COSINE = 0.85


def classify_marker(content: str, this_id: str, existing_ids: set[str]) -> dict | None:
    """Pure direction classifier. Returns a proposal dict or None (no marker).

    dict shape: {"tier": "p1a"|"p1b", "role": "passive"|"active",
                 "source": id|None, "target": id|None, "confidence": "high"|"review"}
    For p1a, source/target are filled. For p1b, target=this_id (passive) and source
    is resolved later by ANN; active-without-id is unresolvable → confidence "review".
    """
    content = content or ""
    if not ANY_MARKER.search(content):
        return None

    def foreign_in(text: str) -> list[str]:
        return [h for h in HEX.findall(text) if h != this_id and h in existing_ids]

    foreign = foreign_in(content)
    lead = PASSIVE_LEAD.match(content)
    active_m = ACTIVE.search(content)

    # Role: leading [SUPERSEDED bracket is the strongest passive signal.
    if lead:
        role = "passive"
    elif active_m:
        role = "active"
    elif PASSIVE_SELF.search(content) or re.search(r"supersed\w*", content, re.I):
        role = "passive"
    else:
        return None

    if role == "active":
        # The id must sit ADJACENT to a supersede/correction/reverse verb to be its
        # OBJECT (the victim). A far-away id is just a cross-link, not the target —
        # acting on it would hide the wrong memory. Window = 60 chars after the verb.
        for m in ACTIVE.finditer(content):
            near = foreign_in(content[m.end(): m.end() + 60])
            if near:
                return {"tier": "p1a", "role": "active", "source": this_id,
                        "target": near[0], "confidence": "high"}
        # verb present but no adjacent id → cannot pinpoint the victim → review.
        return {"tier": "p1b", "role": "active", "source": None, "target": None, "confidence": "review"}

    # passive
    if lead:
        # The replacement id lives inside the leading bracket region.
        near = foreign_in(content[:180])
        uniq = list(dict.fromkeys(near))
        if len(uniq) == 1:
            return {"tier": "p1a", "role": "passive", "source": uniq[0],
                    "target": this_id, "confidence": "high"}
        if len(uniq) > 1:
            return {"tier": "p1a", "role": "passive", "source": None, "target": this_id,
                    "confidence": "review", "candidates": uniq}
    if foreign:
        # passive-self with an id anchored to a see/replaced-by/migration phrase.
        mm = re.search(
            r"(?:see|replaced by|migration memory|→|\bby\b)\s*\[*\s*([0-9a-f]{12})", content, re.I)
        if mm and mm.group(1) != this_id and mm.group(1) in existing_ids:
            return {"tier": "p1a", "role": "passive", "source": mm.group(1),
                    "target": this_id, "confidence": "high"}
        return {"tier": "p1a", "role": "passive", "source": None, "target": this_id,
                "confidence": "review", "candidates": foreign}
    # passive, no id → resolve replacement via ANN (P1b).
    return {"tier": "p1b", "role": "passive", "source": None, "target": this_id, "confidence": "pending"}


def _cosine(a: bytes, b: bytes) -> float:
    import math
    n = len(a) // 4
    va = struct.unpack(f"{n}f", a)
    vb = struct.unpack(f"{n}f", b)
    dot = sum(x * y for x, y in zip(va, vb))
    na = math.sqrt(sum(x * x for x in va))
    nb = math.sqrt(sum(x * x for x in vb))
    return dot / (na * nb) if na and nb else 0.0


def resolve_p1b_sibling(conn, this_id: str) -> tuple[str | None, float, int]:
    """ANN-resolve the newest same-project non-superseded sibling for a passive,
    id-less stale memory. Returns (sibling_id, cosine, n_candidates_in_band)."""
    me = conn.execute(
        "SELECT m.project, m.created_at, v.embedding FROM memories m "
        "JOIN memory_vectors v ON v.memory_id = m.id WHERE m.id = ?", (this_id,)
    ).fetchone()
    if not me:
        return None, 0.0, 0
    try:
        neighbors = conn.execute(
            "SELECT memory_id FROM memory_vectors WHERE embedding MATCH ? AND k = 8",
            (me["embedding"],),
        ).fetchall()
    except Exception:
        return None, 0.0, 0
    superseded = {r["target_id"] for r in conn.execute(
        "SELECT target_id FROM relations WHERE relation_type='supersedes'")}
    best_id, best_sim, in_band = None, 0.0, 0
    for nb in neighbors:
        oid = nb["memory_id"]
        if oid == this_id or oid in superseded:
            continue
        other = conn.execute(
            "SELECT m.created_at, v.embedding FROM memories m "
            "JOIN memory_vectors v ON v.memory_id=m.id WHERE m.id=?", (oid,)
        ).fetchone()
        if not other:
            continue
        # same project? compare against me["project"] (None matches None)
        oproj = conn.execute("SELECT project FROM memories WHERE id=?", (oid,)).fetchone()["project"]
        if me["project"] != oproj:
            continue
        # sibling must be NEWER (the replacement)
        if (other["created_at"] or "") <= (me["created_at"] or ""):
            continue
        sim = _cosine(me["embedding"], other["embedding"])
        if sim >= MIN_COSINE:
            in_band += 1
            if sim > best_sim:
                best_sim, best_id = sim, oid
    return best_id, best_sim, in_band


def _has_edge(conn, source, target) -> bool:
    return conn.execute(
        "SELECT 1 FROM relations WHERE source_id=? AND target_id=? AND relation_type='supersedes'",
        (source, target),
    ).fetchone() is not None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="apply (default: dry-run)")
    args = ap.parse_args()
    dry = not args.execute

    conn = connect()
    existing = {r["id"] for r in conn.execute("SELECT id FROM memories")}
    rows = conn.execute(
        "SELECT id, content, project, created_at FROM memories WHERE type != 'session'"
    ).fetchall()

    created, demoted, review, skipped = [], [], [], []
    affected_targets: list[str] = []

    for r in rows:
        prop = classify_marker(r["content"], r["id"], existing)
        if not prop:
            continue

        # Resolve p1b passive via ANN
        if prop["tier"] == "p1b" and prop["role"] == "passive" and prop["confidence"] == "pending":
            sib, sim, n = resolve_p1b_sibling(conn, r["id"])
            if sib and sim >= HIGH_COSINE and n == 1:
                prop.update(source=sib, confidence="high")
            elif sib and sim >= MIN_COSINE:
                prop.update(source=sib, confidence="low", sim=round(sim, 3))
            else:
                prop.update(confidence="review")

        src, tgt = prop.get("source"), prop.get("target")

        if prop["confidence"] == "high" and src and tgt and src in existing and tgt in existing:
            if _has_edge(conn, src, tgt):
                skipped.append((src, tgt, "edge-exists"))
                continue
            created.append((src, tgt, prop["role"], r["content"][:70]))
            affected_targets.append(tgt)
            if not dry:
                conn.execute(
                    "INSERT OR IGNORE INTO relations (source_id, target_id, relation_type, weight) "
                    "VALUES (?, ?, 'supersedes', 1.0)", (src, tgt))
                conn.execute(
                    "UPDATE memories SET importance = COALESCE(importance,0.5)*0.5 WHERE id=?", (tgt,))
        elif prop["confidence"] == "low" and tgt and tgt in existing:
            # demote + flag, do NOT hide (reversible, surfaces via read-time conflict)
            demoted.append((tgt, prop.get("sim"), r["content"][:70]))
            affected_targets.append(tgt)
            if not dry:
                meta = conn.execute("SELECT metadata FROM memories WHERE id=?", (tgt,)).fetchone()["metadata"]
                try:
                    md = json.loads(meta) if meta else {}
                except Exception:
                    md = {}
                md["superseded_candidate"] = True
                if prop.get("source"):
                    md["resolved_target"] = prop["source"]
                conn.execute(
                    "UPDATE memories SET importance = COALESCE(importance,0.5)*0.7, metadata=? WHERE id=?",
                    (json.dumps(md, ensure_ascii=False), tgt))
        else:
            review.append((r["id"], prop.get("role"), prop.get("confidence"), r["content"][:70]))

    if not dry:
        # record affected ids for July-11 decay exclusion
        if affected_targets:
            existing_meta = conn.execute(
                "SELECT value FROM brain_meta WHERE key='p1_backfill_affected_ids'").fetchone()
            prev = json.loads(existing_meta["value"]) if existing_meta else []
            merged = sorted(set(prev) | set(affected_targets))
            conn.execute(
                "INSERT INTO brain_meta (key, value) VALUES ('p1_backfill_affected_ids', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(merged),))
        conn.commit()

    mode = "DRY-RUN" if dry else "EXECUTED"
    print(f"\n=== P1 back-fill [{mode}] ===")
    print(f"HIDE (supersedes edge): {len(created)}")
    for s, t, role, c in created:
        print(f"  [{role}] {s} supersedes {t}  | {c}")
    print(f"\nDEMOTE+FLAG (low-conf, kept visible): {len(demoted)}")
    for t, sim, c in demoted:
        print(f"  demote {t} (sim={sim}) | {c}")
    print(f"\nREVIEW (ambiguous, untouched): {len(review)}")
    for i, role, conf, c in review:
        print(f"  {i} role={role} conf={conf} | {c}")
    print(f"\nskipped (edge already exists): {len(skipped)}")
    if dry:
        print("\n(dry-run — nothing written. Re-run with --execute to apply.)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
