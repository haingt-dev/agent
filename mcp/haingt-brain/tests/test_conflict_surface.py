"""Tests for read-time conflict-surface (D2): cluster_conflicts annotation."""

from brain_test_utils import create_test_db, insert_memory, make_embedding, blend_embedding

from haingt_brain.search import cluster_conflicts


def _results(conn, ids):
    """Fetch rows as the dicts recall passes to cluster_conflicts."""
    rows = []
    for i in ids:
        r = conn.execute("SELECT * FROM memories WHERE id = ?", (i,)).fetchone()
        rows.append(dict(r))
    return rows


class TestConflictSurface:
    def test_divergent_pair_flagged(self):
        conn = create_test_db()
        # cosine(m1, m2) ≈ 0.83 — same subject, divergent (in band)
        insert_memory(conn, "new1", "thai san model v3: 0 chi gold", "decision",
                      embedding=make_embedding(10), created_days_ago=0, project="finance")
        insert_memory(conn, "old1", "thai san model v2: 2 chi gold", "decision",
                      embedding=blend_embedding(10, 20, 0.6), created_days_ago=14, project="finance")
        flags = cluster_conflicts(conn, _results(conn, ["new1", "old1"]))
        assert flags["new1"]["role"] == "current"
        assert flags["old1"]["role"] == "superseded_candidate"
        assert flags["old1"]["vs"] == "new1"
        assert "ago" in flags["old1"]["age"]
        conn.close()

    def test_unrelated_not_flagged(self):
        conn = create_test_db()
        insert_memory(conn, "a", "godot combat AI", "decision", embedding=make_embedding(1))
        insert_memory(conn, "b", "finance tax model", "decision", embedding=make_embedding(2))
        flags = cluster_conflicts(conn, _results(conn, ["a", "b"]))
        assert flags == {}
        conn.close()

    def test_near_dup_not_treated_as_conflict(self):
        conn = create_test_db()
        # identical embeddings → cosine 1.0 > sim_hi(0.985) → handled by dedup, not conflict
        insert_memory(conn, "a", "same fact", "decision", embedding=make_embedding(5))
        insert_memory(conn, "b", "same fact reworded", "decision", embedding=make_embedding(5))
        flags = cluster_conflicts(conn, _results(conn, ["a", "b"]))
        assert flags == {}
        conn.close()

    def test_cross_type_not_flagged(self):
        conn = create_test_db()
        # same embedding-ish (in band) but different type → not a conflict
        insert_memory(conn, "a", "x", "decision", embedding=make_embedding(10))
        insert_memory(conn, "b", "y", "discovery", embedding=blend_embedding(10, 20, 0.6))
        flags = cluster_conflicts(conn, _results(conn, ["a", "b"]))
        assert flags == {}
        conn.close()

    def test_existing_contradicts_edge_surfaced(self):
        conn = create_test_db()
        # orthogonal embeddings (NOT in geometric band) but an explicit contradicts edge
        insert_memory(conn, "new1", "current claim", "decision", embedding=make_embedding(1), created_days_ago=0)
        insert_memory(conn, "old1", "opposing claim", "decision", embedding=make_embedding(2), created_days_ago=5)
        conn.execute(
            "INSERT INTO relations (source_id, target_id, relation_type) VALUES ('new1','old1','contradicts')"
        )
        conn.commit()
        flags = cluster_conflicts(conn, _results(conn, ["new1", "old1"]))
        assert flags["new1"]["role"] == "current"
        assert flags["old1"]["role"] == "superseded_candidate"
        assert flags["old1"]["via"] == "edge"
        conn.close()

    def test_recency_tiebreak_is_local(self):
        conn = create_test_db()
        # conflict pair + an unrelated high-importance OLD memory that must NOT be touched
        insert_memory(conn, "new1", "model v3", "decision", embedding=make_embedding(10),
                      created_days_ago=0, project="finance")
        insert_memory(conn, "old1", "model v2", "decision", embedding=blend_embedding(10, 20, 0.6),
                      created_days_ago=30, project="finance")
        insert_memory(conn, "durable", "unrelated durable preference", "preference",
                      embedding=make_embedding(999), created_days_ago=90, importance=0.95)
        flags = cluster_conflicts(conn, _results(conn, ["new1", "old1", "durable"]))
        assert "durable" not in flags  # not in any conflict cluster → untouched
        assert flags["new1"]["role"] == "current"
        assert flags["old1"]["role"] == "superseded_candidate"
        conn.close()

    def test_series_pair_not_flagged(self):
        conn = create_test_db()
        # formulaic phase-logs in the conflict band but distinct-true → must NOT flag
        insert_memory(conn, "t2b", "aseprite Tier 2b LANDED. 117 tools, 113 tests green", "discovery",
                      embedding=make_embedding(10), project="chimera", created_days_ago=0)
        insert_memory(conn, "t1", "aseprite Tier 1 LANDED. 110 tools, 99 tests green", "discovery",
                      embedding=blend_embedding(10, 20, 0.6), project="chimera", created_days_ago=2)
        flags = cluster_conflicts(conn, _results(conn, ["t2b", "t1"]))
        assert flags == {}  # anti-series guard suppresses the geometric pair
        conn.close()

    def test_series_pair_with_explicit_edge_still_surfaced(self):
        conn = create_test_db()
        # even series-looking, an EXPLICIT contradicts edge is a deliberate judgment
        insert_memory(conn, "t2b", "aseprite Tier 2b LANDED 117 tools", "discovery",
                      embedding=make_embedding(10), project="chimera", created_days_ago=0)
        insert_memory(conn, "t1", "aseprite Tier 1 LANDED 110 tools", "discovery",
                      embedding=make_embedding(2), project="chimera", created_days_ago=2)
        conn.execute("INSERT INTO relations (source_id,target_id,relation_type) VALUES ('t2b','t1','contradicts')")
        conn.commit()
        flags = cluster_conflicts(conn, _results(conn, ["t2b", "t1"]))
        assert flags.get("t2b", {}).get("role") == "current"
        conn.close()

    def test_single_result_no_flags(self):
        conn = create_test_db()
        insert_memory(conn, "a", "lonely", "decision", embedding=make_embedding(1))
        flags = cluster_conflicts(conn, _results(conn, ["a"]))
        assert flags == {}
        conn.close()
