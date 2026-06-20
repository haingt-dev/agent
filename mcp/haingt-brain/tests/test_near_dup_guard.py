"""Tests for write-time near-dup guard + auto-supersede gating (D4)."""

from unittest.mock import patch

from brain_test_utils import create_test_db, insert_memory, make_embedding, blend_embedding

from haingt_brain.tools import save as save_mod


def _count_memories(conn):
    return conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]


def _save(conn, content, mtype="decision", seed=42, project=None):
    """Call brain_save with embed_text mocked to a deterministic vector."""
    with patch.object(save_mod, "embed_text", return_value=make_embedding(seed)):
        return save_mod.brain_save(conn, content, mtype, project=project)


class TestNearDupGuard:
    def test_near_dup_skipped(self):
        conn = create_test_db()
        insert_memory(conn, "orig", "side-view camera locked for the game", "decision",
                      embedding=make_embedding(42))
        before = _count_memories(conn)
        res = _save(conn, "side-view perspective locked", "decision", seed=42)  # cosine 1.0
        assert res["status"] == "skipped_near_duplicate"
        assert res["matched"] == "orig"
        assert _count_memories(conn) == before  # no new row
        conn.close()

    def test_distinct_saved_normally(self):
        conn = create_test_db()
        insert_memory(conn, "orig", "combat AI design", "decision", embedding=make_embedding(1))
        before = _count_memories(conn)
        res = _save(conn, "finance tax model", "decision", seed=2)  # orthogonal
        assert res["status"] == "saved"
        assert _count_memories(conn) == before + 1
        conn.close()

    def test_cross_type_not_deduped(self):
        conn = create_test_db()
        insert_memory(conn, "orig", "same vector", "decision", embedding=make_embedding(42))
        before = _count_memories(conn)
        res = _save(conn, "same vector different type", "discovery", seed=42)  # same emb, diff type
        assert res["status"] == "saved"  # guard is same-type only
        assert _count_memories(conn) == before + 1
        conn.close()

    def test_guard_disabled_allows_dup(self, monkeypatch):
        conn = create_test_db()
        insert_memory(conn, "orig", "x", "decision", embedding=make_embedding(42))
        monkeypatch.setenv("BRAIN_NEAR_DUP_GUARD", "false")
        before = _count_memories(conn)
        res = _save(conn, "x again", "decision", seed=42)
        assert res["status"] == "saved"
        assert _count_memories(conn) == before + 1
        conn.close()


class TestAutoSupersedeGating:
    def test_auto_supersede_off_no_edge_no_llm(self, monkeypatch):
        """Default: a band sibling exists but no edge is created and the LLM is never called."""
        conn = create_test_db()
        # sibling at ~0.88 cosine (in 0.80-0.97 band, below 0.92 near-dup) → would be a candidate
        insert_memory(conn, "old1", "thai san model v2: 2 chi gold", "decision",
                      embedding=blend_embedding(10, 20, 0.65), project="finance")
        monkeypatch.delenv("BRAIN_AUTO_SUPERSEDE", raising=False)
        with patch("haingt_brain.contradiction.classify_pair") as m:
            with patch.object(save_mod, "embed_text", return_value=make_embedding(10)):
                res = save_mod.brain_save(conn, "thai san model v3: 0 chi gold instead", "decision",
                                          project="finance")
            m.assert_not_called()
        assert res["status"] == "saved"
        assert "auto_revision" not in res
        n_edges = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        assert n_edges == 0
        conn.close()

    def test_auto_supersede_on_creates_edge(self, monkeypatch):
        conn = create_test_db()
        insert_memory(conn, "old1", "use library A for the parser", "decision",
                      embedding=blend_embedding(10, 20, 0.65), project="proj")
        monkeypatch.setenv("BRAIN_AUTO_SUPERSEDE", "true")
        fake = {"verdict": "supersedes", "confidence": 0.95}
        with patch("haingt_brain.contradiction.classify_pair", return_value=fake):
            with patch.object(save_mod, "embed_text", return_value=make_embedding(10)):
                res = save_mod.brain_save(conn, "no longer using library A, switched to B instead",
                                          "decision", project="proj")
        assert res.get("auto_revision", {}).get("relation") == "supersedes"
        edge = conn.execute(
            "SELECT 1 FROM relations WHERE target_id='old1' AND relation_type='supersedes'"
        ).fetchone()
        assert edge is not None
        # target demoted
        imp = conn.execute("SELECT importance FROM memories WHERE id='old1'").fetchone()[0]
        assert imp < 0.5
        conn.close()
