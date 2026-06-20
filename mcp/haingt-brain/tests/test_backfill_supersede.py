"""Tests for P1 back-fill (D3): marker direction + ANN sibling resolution."""

import sys
from pathlib import Path

from brain_test_utils import create_test_db, insert_memory, make_embedding, blend_embedding

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import backfill_supersede as bf  # noqa: E402

SUPERSEDED_SUBQUERY = (
    "SELECT 1 FROM memories m WHERE m.id = ? AND m.id NOT IN "
    "(SELECT target_id FROM relations WHERE relation_type='supersedes')"
)


DEAD = "dead00000001"
REPL = "aaaaaaaaaaaa"
VICTIM = "bbbbbbbbbbbb"
NEW = "cccccccccccc"


class TestClassifyMarker:
    def test_passive_bracket_with_id(self):
        existing = {DEAD, REPL}
        p = bf.classify_marker(f"[SUPERSEDED 2026-05-29 — see migration memory {REPL}] old stuff",
                               DEAD, existing)
        assert p["tier"] == "p1a" and p["confidence"] == "high"
        assert p["source"] == REPL and p["target"] == DEAD  # hide THIS (dead)

    def test_active_supersedes_id(self):
        existing = {NEW, VICTIM}
        p = bf.classify_marker(f"DECISION (2026-06-12, supersedes {VICTIM}): now we bundle the MCP",
                               NEW, existing)
        assert p["tier"] == "p1a" and p["confidence"] == "high"
        assert p["source"] == NEW and p["target"] == VICTIM  # hide the referenced victim

    def test_active_correction_to_id(self):
        existing = {NEW, VICTIM}
        p = bf.classify_marker(f"CORRECTION to {VICTIM}: the real weights are different", NEW, existing)
        assert p["source"] == NEW and p["target"] == VICTIM

    def test_multiple_ids_is_review(self):
        existing = {REPL, VICTIM, NEW}
        p = bf.classify_marker(f"[SUPERSEDED — see {REPL} and also {VICTIM} for context]", NEW, existing)
        assert p["confidence"] == "review"

    def test_passive_no_id_is_p1b_pending(self):
        p = bf.classify_marker("[SUPERSEDED 2026-05-30 — current: 0 chi gold] thai san model", "x", set())
        assert p["tier"] == "p1b" and p["role"] == "passive" and p["confidence"] == "pending"

    def test_no_marker_returns_none(self):
        assert bf.classify_marker("just a normal decision about combat AI", "x", set()) is None

    def test_unknown_referenced_id_ignored(self):
        # id present in text but NOT an existing memory → treated as no foreign id → p1b
        p = bf.classify_marker("[SUPERSEDED — see deadbeef1234] gone", "x", set())
        assert p["tier"] == "p1b"


class TestDirectionContract:
    def test_hidden_target_excluded_by_superseded_filter(self):
        """End-to-end: the DEAD memory must be the one SUPERSEDED_FILTER excludes."""
        conn = create_test_db()
        insert_memory(conn, REPL, "current pattern: glob autoload", embedding_seed=1)
        insert_memory(conn, DEAD, f"[SUPERSEDED — see migration memory {REPL}] old symlink pattern",
                      embedding_seed=2)
        existing = {REPL, DEAD}
        p = bf.classify_marker(
            conn.execute("SELECT content FROM memories WHERE id=?", (DEAD,)).fetchone()["content"],
            DEAD, existing)
        conn.execute(
            "INSERT INTO relations (source_id,target_id,relation_type) VALUES (?,?,'supersedes')",
            (p["source"], p["target"]))
        conn.commit()
        # DEAD hidden, REPL survives
        assert conn.execute(SUPERSEDED_SUBQUERY, (DEAD,)).fetchone() is None
        assert conn.execute(SUPERSEDED_SUBQUERY, (REPL,)).fetchone() is not None
        conn.close()


class TestResolveP1bSibling:
    def test_high_conf_single_sibling(self):
        conn = create_test_db()
        insert_memory(conn, "stale", "[SUPERSEDED] thai san v2", "decision",
                      embedding=make_embedding(10), project="finance", created_days_ago=30)
        insert_memory(conn, "current", "thai san v3", "decision",
                      embedding=blend_embedding(10, 20, 0.7), project="finance", created_days_ago=1)
        sib, sim, n = bf.resolve_p1b_sibling(conn, "stale")
        assert sib == "current" and sim >= 0.90 and n == 1
        conn.close()

    def test_sibling_must_be_newer(self):
        conn = create_test_db()
        insert_memory(conn, "stale", "[SUPERSEDED] x", "decision",
                      embedding=make_embedding(10), project="finance", created_days_ago=1)
        insert_memory(conn, "older", "y", "decision",
                      embedding=blend_embedding(10, 20, 0.7), project="finance", created_days_ago=30)
        sib, sim, n = bf.resolve_p1b_sibling(conn, "stale")
        assert sib is None  # only an OLDER sibling exists → not a valid replacement
        conn.close()

    def test_different_project_excluded(self):
        conn = create_test_db()
        insert_memory(conn, "stale", "[SUPERSEDED] x", "decision",
                      embedding=make_embedding(10), project="finance", created_days_ago=30)
        insert_memory(conn, "other", "y", "decision",
                      embedding=blend_embedding(10, 20, 0.7), project="chimera", created_days_ago=1)
        sib, sim, n = bf.resolve_p1b_sibling(conn, "stale")
        assert sib is None
        conn.close()
