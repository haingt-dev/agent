"""Test that access_count is incremented ONLY on final top-n, not the oversampled pool.

This was a critical fix when adding the judge layer — previously hybrid_search
incremented access_count for all fetched candidates, which would distort
importance signals when oversampling (k*3) became the pool size.

Mocks hybrid_search directly — these tests target brain_recall's pipeline
(oversample → judge → access_count → format), not the SQL search itself.
"""

import sqlite3

import pytest


def _create_test_db() -> sqlite3.Connection:
    """Minimal brain DB — just memories + brain_meta, no vec/fts."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            type TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            project TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT,
            importance REAL DEFAULT 0.5
        );
        CREATE TABLE brain_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    return conn


def _seed_15(conn):
    """Insert 15 memories — pool size for tests."""
    for i in range(15):
        conn.execute(
            """INSERT INTO memories (id, content, type, importance)
               VALUES (?, ?, 'decision', ?)""",
            (f"m{i:02d}", f"godot memory {i}", 0.5 + i * 0.02),
        )
    conn.commit()


def _fake_pool(conn, ids):
    """Build a candidate pool list from existing memory rows."""
    pool = []
    for mid in ids:
        row = conn.execute(
            "SELECT * FROM memories WHERE id = ?", (mid,)
        ).fetchone()
        if row:
            d = dict(row)
            d["rrf_score"] = 0.5
            pool.append(d)
    return pool


@pytest.fixture
def db():
    conn = _create_test_db()
    _seed_15(conn)
    return conn


def test_access_count_only_on_final_top_n(db, monkeypatch):
    """When k=5, only 5 memories get access_count bumped — not the whole pool of 15."""
    from haingt_brain.tools import recall as recall_mod

    pool_ids = [f"m{i:02d}" for i in range(15)]
    monkeypatch.setattr(
        recall_mod,
        "hybrid_search",
        lambda conn, q, mt, p, k, time_range=None: _fake_pool(conn, pool_ids[:k]),
    )
    monkeypatch.setenv("JUDGE_ENABLED", "false")

    results = recall_mod.brain_recall(db, "godot", k=5)
    assert len(results) == 5

    rows = db.execute("SELECT id, access_count FROM memories ORDER BY id").fetchall()
    bumped = [r["id"] for r in rows if r["access_count"] > 0]
    not_bumped = [r["id"] for r in rows if r["access_count"] == 0]

    assert len(bumped) == 5, f"Expected 5 bumped, got {len(bumped)}"
    assert len(not_bumped) == 10


def test_judge_status_disabled(db, monkeypatch):
    from haingt_brain.tools import recall as recall_mod

    monkeypatch.setattr(
        recall_mod,
        "hybrid_search",
        lambda conn, q, mt, p, k, time_range=None: _fake_pool(conn, [f"m{i:02d}" for i in range(k)]),
    )
    monkeypatch.setenv("JUDGE_ENABLED", "false")

    results = recall_mod.brain_recall(db, "godot", k=5)
    assert results
    assert results[0].get("_judge_status") == "fallback:disabled"


def test_budget_gate_blocks_judge(db, monkeypatch):
    """When judge_cost_today exceeds budget, judge skipped → STATUS_BUDGET."""
    from datetime import date

    today = date.today().isoformat()
    db.execute("INSERT INTO brain_meta (key, value) VALUES ('judge_cost_date', ?)", (today,))
    db.execute("INSERT INTO brain_meta (key, value) VALUES ('judge_cost_today', '0.99')")
    db.commit()

    from haingt_brain.tools import recall as recall_mod
    monkeypatch.setattr(
        recall_mod,
        "hybrid_search",
        lambda conn, q, mt, p, k, time_range=None: _fake_pool(conn, [f"m{i:02d}" for i in range(k)]),
    )
    monkeypatch.setenv("JUDGE_ENABLED", "true")
    monkeypatch.setenv("JUDGE_DAILY_BUDGET_USD", "0.50")

    results = recall_mod.brain_recall(db, "godot", k=5)
    assert results[0].get("_judge_status") == "fallback:budget"


def test_oversample_pool_size(db, monkeypatch):
    """Verify _oversample_k is respected — for k=5, pool should be 15 not 5."""
    captured_k = {}

    def capture(conn, q, mt, p, k, time_range=None):
        captured_k["k"] = k
        return _fake_pool(conn, [f"m{i:02d}" for i in range(k)])

    from haingt_brain.tools import recall as recall_mod
    monkeypatch.setattr(recall_mod, "hybrid_search", capture)
    monkeypatch.setenv("JUDGE_ENABLED", "false")

    recall_mod.brain_recall(db, "godot", k=5)
    assert captured_k["k"] == 15  # 5 * 3

    recall_mod.brain_recall(db, "godot", k=1)
    assert captured_k["k"] == 10  # floor at 10

    recall_mod.brain_recall(db, "godot", k=10)
    assert captured_k["k"] == 20  # ceiling at 20


def test_judge_telemetry_updates_brain_meta(db, monkeypatch):
    """When judge runs (even disabled fallback), calls_total bumps."""
    from haingt_brain.tools import recall as recall_mod

    monkeypatch.setattr(
        recall_mod,
        "hybrid_search",
        lambda conn, q, mt, p, k, time_range=None: _fake_pool(conn, [f"m{i:02d}" for i in range(k)]),
    )
    monkeypatch.setenv("JUDGE_ENABLED", "false")

    recall_mod.brain_recall(db, "godot", k=5)
    recall_mod.brain_recall(db, "godot", k=5)

    row = db.execute(
        "SELECT value FROM brain_meta WHERE key = 'judge_calls_total'"
    ).fetchone()
    assert row is not None
    assert int(row["value"]) == 2

    fallback_row = db.execute(
        "SELECT value FROM brain_meta WHERE key = 'judge_fallback_total'"
    ).fetchone()
    assert fallback_row is not None
    assert int(fallback_row["value"]) == 2  # both went through disabled fallback
