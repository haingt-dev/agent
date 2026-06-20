"""Tests for P2 cleanup (D7): label unify + reversible dedup."""

import sys
from pathlib import Path

from brain_test_utils import create_test_db, insert_memory, make_embedding

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import cleanup_p2_dupes as cp  # noqa: E402

SUP_SUBQ = ("SELECT 1 FROM memories m WHERE m.id = ? AND m.id NOT IN "
            "(SELECT target_id FROM relations WHERE relation_type='supersedes')")


class TestUnifyLabels:
    def test_relabel(self):
        conn = create_test_db()
        insert_memory(conn, "a", "x", "decision", embedding_seed=1, project="the-ninth-bride")
        insert_memory(conn, "b", "y", "decision", embedding_seed=2, project="the-ninth-bride")
        insert_memory(conn, "c", "z", "decision", embedding_seed=3, project="chimera")
        n = cp.unify_labels(conn, dry_run=False)
        assert n == 2
        assert conn.execute("SELECT COUNT(*) FROM memories WHERE project='the-ninth-bride'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM memories WHERE project='chimera'").fetchone()[0] == 3
        conn.close()


class TestReversibleDedup:
    def test_cluster_keeps_newest_hides_rest(self):
        conn = create_test_db()
        # 3 near-identical (same embedding) decisions, different ages
        insert_memory(conn, "v1", "side-view locked", "decision", embedding=make_embedding(7),
                      project="chimera", created_days_ago=10)
        insert_memory(conn, "v2", "side-view perspective locked", "decision", embedding=make_embedding(7),
                      project="chimera", created_days_ago=5)
        insert_memory(conn, "v3", "side-view camera locked (newest)", "decision", embedding=make_embedding(7),
                      project="chimera", created_days_ago=0)
        clusters = cp.find_dup_clusters(conn, threshold=0.93)
        assert len(clusters) == 1
        canonical, dups = clusters[0]
        assert canonical == "v3" and set(dups) == {"v1", "v2"}  # newest is canonical
        cp.collapse_clusters(conn, clusters, dry_run=False)
        # canonical visible; dups hidden by SUPERSEDED_FILTER
        assert conn.execute(SUP_SUBQ, ("v3",)).fetchone() is not None
        assert conn.execute(SUP_SUBQ, ("v1",)).fetchone() is None
        assert conn.execute(SUP_SUBQ, ("v2",)).fetchone() is None
        conn.close()

    def test_distinct_not_clustered(self):
        conn = create_test_db()
        insert_memory(conn, "a", "combat AI", "decision", embedding=make_embedding(1), project="chimera")
        insert_memory(conn, "b", "art pipeline", "decision", embedding=make_embedding(2), project="chimera")
        clusters = cp.find_dup_clusters(conn, threshold=0.93)
        assert clusters == []
        conn.close()

    def test_inbound_relations_repointed(self):
        conn = create_test_db()
        insert_memory(conn, "v1", "side-view locked", "decision", embedding=make_embedding(7),
                      project="chimera", created_days_ago=10)
        insert_memory(conn, "v2", "side-view newest", "decision", embedding=make_embedding(7),
                      project="chimera", created_days_ago=0)
        insert_memory(conn, "ext", "some other memory", "decision", embedding=make_embedding(50),
                      project="chimera")
        # ext relates_to the OLD dup v1
        conn.execute("INSERT INTO relations (source_id,target_id,relation_type) VALUES ('ext','v1','relates_to')")
        conn.commit()
        clusters = cp.find_dup_clusters(conn, threshold=0.93)
        cp.collapse_clusters(conn, clusters, dry_run=False)
        # the relates_to edge now points at canonical v2, not the hidden v1
        assert conn.execute(
            "SELECT 1 FROM relations WHERE source_id='ext' AND target_id='v2' AND relation_type='relates_to'"
        ).fetchone() is not None
        conn.close()

    def test_dry_run_no_writes(self):
        conn = create_test_db()
        insert_memory(conn, "v1", "side-view locked", "decision", embedding=make_embedding(7),
                      project="chimera", created_days_ago=10)
        insert_memory(conn, "v2", "side-view newest", "decision", embedding=make_embedding(7),
                      project="chimera", created_days_ago=0)
        clusters = cp.find_dup_clusters(conn, threshold=0.93)
        cp.collapse_clusters(conn, clusters, dry_run=True)
        assert conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == 0
        conn.close()
