"""Tests for the batch supersede_pass strategy (D6)."""

from unittest.mock import patch

from brain_test_utils import create_test_db, insert_memory, make_embedding, blend_embedding

from haingt_brain import consolidate
from haingt_brain.consolidate import supersede_pass, consolidate_all, SAFE_STRATEGIES

SUP_SUBQ = ("SELECT 1 FROM memories m WHERE m.id = ? AND m.id NOT IN "
            "(SELECT target_id FROM relations WHERE relation_type='supersedes')")


def _band_pair(conn):
    """Two same-type same-project memories with cosine ~0.86 (in 0.80-0.97 band)."""
    insert_memory(conn, "newer", "use library B for the parser now", "decision",
                  embedding=make_embedding(10), project="proj", created_days_ago=1)
    insert_memory(conn, "older", "use library A for the parser", "decision",
                  embedding=blend_embedding(10, 20, 0.62), project="proj", created_days_ago=20)


class TestSupersedePass:
    def test_contradicts_default_surfaces_both(self):
        conn = create_test_db()
        _band_pair(conn)
        with patch("haingt_brain.contradiction.classify_pair",
                   return_value={"verdict": "contradicts", "confidence": 0.9}):
            res = supersede_pass(conn, dry_run=False)
        assert res["contradict_edges"] == 1 and res["supersede_edges"] == 0
        # contradicts hides nothing — both still pass SUPERSEDED_FILTER
        assert conn.execute(SUP_SUBQ, ("older",)).fetchone() is not None
        assert conn.execute(SUP_SUBQ, ("newer",)).fetchone() is not None
        conn.close()

    def test_supersedes_hides_older_on_reversal(self):
        conn = create_test_db()
        _band_pair(conn)
        with patch("haingt_brain.contradiction.classify_pair",
                   return_value={"verdict": "supersedes", "confidence": 0.9}):
            res = supersede_pass(conn, dry_run=False)
        assert res["supersede_edges"] == 1
        # older is now hidden, newer survives
        assert conn.execute(SUP_SUBQ, ("older",)).fetchone() is None
        assert conn.execute(SUP_SUBQ, ("newer",)).fetchone() is not None
        imp = conn.execute("SELECT importance FROM memories WHERE id='older'").fetchone()[0]
        assert imp < 0.5  # demoted
        conn.close()

    def test_anti_series_skip_real_guard(self):
        """Phase-log siblings must produce ZERO edges via the real anti-series guard."""
        conn = create_test_db()
        insert_memory(conn, "p_b", "Iron Cradle P-Combat-b EXECUTED + GREEN (ADR-0020)", "decision",
                      embedding=make_embedding(10), project="ic", created_days_ago=1)
        insert_memory(conn, "p_a", "Iron Cradle P-Combat-a EXECUTED + GREEN (ADR-0019)", "decision",
                      embedding=blend_embedding(10, 20, 0.62), project="ic", created_days_ago=2)
        # do NOT mock classify_pair → real anti-series guard short-circuits, no LLM
        res = supersede_pass(conn, dry_run=False)
        assert res["supersede_edges"] == 0 and res["contradict_edges"] == 0
        assert conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == 0
        conn.close()

    def test_dry_run_no_writes(self):
        conn = create_test_db()
        _band_pair(conn)
        with patch("haingt_brain.contradiction.classify_pair",
                   return_value={"verdict": "supersedes", "confidence": 0.9}):
            res = supersede_pass(conn, dry_run=True)
        assert res["supersede_edges"] == 1  # counted
        assert conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == 0  # but not written
        conn.close()

    def test_low_confidence_skipped(self):
        conn = create_test_db()
        _band_pair(conn)
        with patch("haingt_brain.contradiction.classify_pair",
                   return_value={"verdict": "supersedes", "confidence": 0.5}):
            res = supersede_pass(conn, dry_run=False)
        assert res["supersede_edges"] == 0
        conn.close()

    def test_idempotent_skips_existing_edge(self):
        conn = create_test_db()
        _band_pair(conn)
        conn.execute("INSERT INTO relations (source_id,target_id,relation_type) VALUES ('newer','older','supersedes')")
        conn.commit()
        with patch("haingt_brain.contradiction.classify_pair",
                   return_value={"verdict": "supersedes", "confidence": 0.9}) as m:
            res = supersede_pass(conn, dry_run=False)
        assert res["supersede_edges"] == 0  # pre-existing edge → skipped
        m.assert_not_called()
        conn.close()


class TestNotInSafeStrategies:
    def test_supersede_excluded_from_safe(self):
        assert "supersede" not in SAFE_STRATEGIES

    def test_default_run_does_not_invoke_supersede(self):
        conn = create_test_db()
        _band_pair(conn)
        with patch.object(consolidate, "supersede_pass") as m:
            consolidate_all(conn, dry_run=True)  # default strategies = SAFE
            m.assert_not_called()
        conn.close()
