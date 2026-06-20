"""Tests for brain_unlink — the manual brake for belief-revision edges."""

from brain_test_utils import create_test_db, insert_memory

from haingt_brain.tools.unlink import brain_unlink


def _add_edge(conn, src, tgt, rtype, weight=1.0):
    conn.execute(
        "INSERT INTO relations (source_id, target_id, relation_type, weight) VALUES (?, ?, ?, ?)",
        (src, tgt, rtype, weight),
    )
    conn.commit()


class TestBrainUnlink:
    def test_unlink_removes_edge(self):
        conn = create_test_db()
        insert_memory(conn, "new1", "current fact", embedding_seed=1)
        insert_memory(conn, "old1", "stale fact", embedding_seed=2)
        _add_edge(conn, "new1", "old1", "supersedes")

        res = brain_unlink(conn, "new1", "old1", "supersedes")
        assert res["status"] == "unlinked"
        gone = conn.execute(
            "SELECT 1 FROM relations WHERE source_id='new1' AND target_id='old1' AND relation_type='supersedes'"
        ).fetchone()
        assert gone is None
        conn.close()

    def test_unlink_not_found(self):
        conn = create_test_db()
        insert_memory(conn, "a", "x", embedding_seed=1)
        insert_memory(conn, "b", "y", embedding_seed=2)
        res = brain_unlink(conn, "a", "b", "supersedes")
        assert res["status"] == "not_found"
        conn.close()

    def test_unlink_restores_importance(self):
        conn = create_test_db()
        insert_memory(conn, "new1", "current", embedding_seed=1)
        insert_memory(conn, "old1", "stale", embedding_seed=2, importance=0.25)  # demoted state
        _add_edge(conn, "new1", "old1", "supersedes")

        res = brain_unlink(conn, "new1", "old1", "supersedes", restore_importance=True)
        assert res["status"] == "unlinked"
        assert res["importance_restored"] == 0.5  # 0.25 * 2
        imp = conn.execute("SELECT importance FROM memories WHERE id='old1'").fetchone()[0]
        assert abs(imp - 0.5) < 1e-6
        conn.close()

    def test_unlink_restore_caps_at_one(self):
        conn = create_test_db()
        insert_memory(conn, "new1", "current", embedding_seed=1)
        insert_memory(conn, "old1", "stale", embedding_seed=2, importance=0.8)
        _add_edge(conn, "new1", "old1", "supersedes")
        res = brain_unlink(conn, "new1", "old1", "supersedes")
        assert res["importance_restored"] == 1.0  # min(1.0, 0.8*2)
        conn.close()

    def test_unlink_no_restore_when_disabled(self):
        conn = create_test_db()
        insert_memory(conn, "new1", "current", embedding_seed=1)
        insert_memory(conn, "old1", "stale", embedding_seed=2, importance=0.25)
        _add_edge(conn, "new1", "old1", "supersedes")
        res = brain_unlink(conn, "new1", "old1", "supersedes", restore_importance=False)
        assert res["importance_restored"] is False
        imp = conn.execute("SELECT importance FROM memories WHERE id='old1'").fetchone()[0]
        assert abs(imp - 0.25) < 1e-6  # untouched
        conn.close()

    def test_unlink_invalid_type(self):
        conn = create_test_db()
        res = brain_unlink(conn, "a", "b", "bogus_type")
        assert res["status"] == "invalid_relation_type"
        conn.close()

    def test_unlink_contradicts_no_importance_change(self):
        conn = create_test_db()
        insert_memory(conn, "a", "x", embedding_seed=1, importance=0.5)
        insert_memory(conn, "b", "y", embedding_seed=2, importance=0.5)
        _add_edge(conn, "a", "b", "contradicts")
        res = brain_unlink(conn, "a", "b", "contradicts")
        assert res["status"] == "unlinked"
        assert res["importance_restored"] is False  # only supersedes restores
        conn.close()
