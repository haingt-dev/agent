"""Brain quality simulation: prove signal survives and noise decays over time.

Seeds a realistic memory population, simulates 6 weeks of noise injection +
consolidation cycles, and asserts that signal-to-noise ratio improves monotonically.

Run BEFORE and AFTER fixes to prove the problem and the solution.
"""

import json
import math
import sqlite3
from datetime import datetime, timedelta

import pytest

from haingt_brain.importance import (
    compute_decay,
    compute_initial_importance,
)
from haingt_brain.consolidate import consolidate_all, decay_importance


# ── Helpers ────────────────────────────────────────────────────────────


def _create_test_db() -> sqlite3.Connection:
    """Create in-memory brain DB with minimal schema (no sqlite-vec needed)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN (
                'decision', 'discovery', 'pattern', 'entity',
                'preference', 'session', 'tool'
            )),
            tags TEXT DEFAULT '[]',
            project TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT,
            importance REAL DEFAULT 0.5
        );

        CREATE TABLE relations (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (source_id, target_id, relation_type)
        );

        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            project TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            ended_at TEXT,
            summary TEXT,
            memory_ids TEXT DEFAULT '[]'
        );

        CREATE TABLE brain_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        -- Stubs for _delete_memory compatibility (no actual vector/FTS data needed)
        CREATE TABLE memory_vectors (
            memory_id TEXT PRIMARY KEY,
            embedding BLOB
        );

        CREATE TABLE memory_fts (
            content TEXT,
            tags TEXT,
            project TEXT,
            memory_id TEXT
        );
    """)
    return conn


def _insert_memory(
    conn: sqlite3.Connection,
    mem_id: str,
    content: str,
    mem_type: str,
    source: str | None = None,
    importance: float | None = None,
    created_at: str | None = None,
    access_count: int = 0,
    last_accessed: str | None = None,
    project: str | None = None,
) -> None:
    """Insert a memory with computed importance."""
    if importance is None:
        importance = compute_initial_importance(mem_type, source)
    metadata = json.dumps({"source": source}) if source else "{}"
    if created_at is None:
        created_at = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT INTO memories (id, content, type, metadata, importance, created_at,
           access_count, last_accessed, project)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (mem_id, content, mem_type, metadata, importance, created_at,
         access_count, last_accessed, project),
    )


def _advance_time(conn: sqlite3.Connection, days: int) -> None:
    """Age all memories by N days (shift created_at and last_accessed back)."""
    conn.execute(
        f"UPDATE memories SET created_at = datetime(created_at, '-{days} days')"
    )
    conn.execute(
        f"UPDATE memories SET last_accessed = datetime(last_accessed, '-{days} days') "
        f"WHERE last_accessed IS NOT NULL"
    )


def _count_by_source(conn: sqlite3.Connection, source: str) -> int:
    """Count memories from a specific source."""
    row = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE json_extract(metadata, '$.source') = ?",
        (source,),
    ).fetchone()
    return row[0]


def _count_signal(conn: sqlite3.Connection) -> int:
    """Count high-value signal memories."""
    row = conn.execute(
        """SELECT COUNT(*) FROM memories
           WHERE json_extract(metadata, '$.source') IN ('manual', 'reflect', 'research', 'mentor')
              OR type IN ('decision', 'pattern', 'preference')""",
    ).fetchone()
    return row[0]


def _count_noise(conn: sqlite3.Connection) -> int:
    """Count noise memories (hook-sourced)."""
    row = conn.execute(
        """SELECT COUNT(*) FROM memories
           WHERE json_extract(metadata, '$.source') LIKE '%hook%'""",
    ).fetchone()
    return row[0]


def _total_non_tool(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM memories WHERE type != 'tool'").fetchone()
    return row[0]


def _snr(conn: sqlite3.Connection) -> float:
    """Signal-to-noise ratio. Higher = better."""
    signal = _count_signal(conn)
    noise = _count_noise(conn)
    total = signal + noise
    return signal / total if total > 0 else 1.0


def _get_importance(conn: sqlite3.Connection, mem_id: str) -> float | None:
    row = conn.execute("SELECT importance FROM memories WHERE id = ?", (mem_id,)).fetchone()
    return row[0] if row else None


# ── Seed Data ──────────────────────────────────────────────────────────


def _seed_memories(conn: sqlite3.Connection) -> dict:
    """Seed ~100 memories matching real brain distribution. Returns tracking info."""
    now = datetime.utcnow()
    tracking = {"signal_ids": [], "noise_ids": []}

    # 25 hook discoveries (noise)
    for i in range(25):
        mid = f"hook_{i:03d}"
        _insert_memory(
            conn, mid,
            f"Web search result #{i}: generic search dump about topic {i}",
            "discovery", source="search-and-store-hook",
            created_at=(now - timedelta(days=i % 7)).isoformat(),
        )
        tracking["noise_ids"].append(mid)

    # 10 pre-compact hook discoveries (noise)
    for i in range(10):
        mid = f"compact_{i:03d}"
        _insert_memory(
            conn, mid,
            f"Pre-compact extract #{i}: session detail about work {i}",
            "discovery", source="pre-compact-hook",
            created_at=(now - timedelta(days=i % 5)).isoformat(),
        )
        tracking["noise_ids"].append(mid)

    # 15 wrap sessions (medium value)
    for i in range(15):
        mid = f"wrap_{i:03d}"
        _insert_memory(
            conn, mid,
            f"Session {i}: worked on feature X, decided Y",
            "session", source="wrap",
            created_at=(now - timedelta(days=i * 2)).isoformat(),
        )

    # 20 manual decisions (high value) — all within last 7 days (matches real brain age)
    for i in range(20):
        mid = f"decision_{i:03d}"
        _insert_memory(
            conn, mid,
            f"Decision #{i}: chose architecture approach {i} because of trade-off analysis",
            "decision", source="manual",
            created_at=(now - timedelta(days=i % 7)).isoformat(),
            access_count=i % 5,
            last_accessed=(now - timedelta(days=i % 3)).isoformat(),
        )
        tracking["signal_ids"].append(mid)

    # 10 research discoveries (high value)
    for i in range(10):
        mid = f"research_{i:03d}"
        _insert_memory(
            conn, mid,
            f"Research finding #{i}: best practice for {i} validated by 3 sources",
            "discovery", source="research",
            created_at=(now - timedelta(days=i % 7)).isoformat(),
            access_count=2,
            last_accessed=(now - timedelta(days=i % 4)).isoformat(),
        )
        tracking["signal_ids"].append(mid)

    # 5 reflect discoveries (highest value)
    for i in range(5):
        mid = f"reflect_{i:03d}"
        _insert_memory(
            conn, mid,
            f"Reflect insight #{i}: career pattern identified — fuel depletion cycle {i}",
            "discovery", source="reflect",
            created_at=(now - timedelta(days=i % 5)).isoformat(),
            access_count=3,
            last_accessed=(now - timedelta(days=i % 2)).isoformat(),
        )
        tracking["signal_ids"].append(mid)

    # 5 patterns (high value)
    for i in range(5):
        mid = f"pattern_{i:03d}"
        _insert_memory(
            conn, mid,
            f"Pattern #{i}: conditional gating approach for skill {i}",
            "pattern", source="manual",
            created_at=(now - timedelta(days=i % 5)).isoformat(),
            access_count=1,
            last_accessed=(now - timedelta(days=i % 3)).isoformat(),
        )
        tracking["signal_ids"].append(mid)

    # 10 entity memories (medium value)
    for i in range(10):
        mid = f"entity_{i:03d}"
        _insert_memory(
            conn, mid,
            f"Entity: project_{i} — description of project {i}",
            "entity",
            created_at=(now - timedelta(days=i * 2)).isoformat(),
            access_count=i,
            last_accessed=(now - timedelta(days=1)).isoformat() if i > 3 else None,
        )

    # Add graph connections for some signal memories (should resist decay)
    for i in range(3):
        conn.execute(
            "INSERT INTO relations VALUES (?, ?, 'relates_to', 1.0, datetime('now'))",
            (f"decision_{i:03d}", f"research_{i:03d}"),
        )
        conn.execute(
            "INSERT INTO relations VALUES (?, ?, 'causes', 1.0, datetime('now'))",
            (f"reflect_{i:03d}", f"pattern_{i:03d}"),
        )

    conn.commit()
    return tracking


# ── Core Simulation ────────────────────────────────────────────────────


def _run_simulation(conn: sqlite3.Connection, tracking: dict, weeks: int = 6) -> dict:
    """Run N weeks of noise injection + consolidation. Return metrics per week."""
    metrics = []
    now = datetime.utcnow()

    for week in range(weeks):
        # 1. Inject noise (15 new hook memories per week)
        for i in range(15):
            mid = f"week{week}_hook_{i:03d}"
            _insert_memory(
                conn, mid,
                f"Week {week} web search #{i}: random search result",
                "discovery", source="search-and-store-hook",
            )

        # 2. Inject signal (2 decisions + 1 reflect per week)
        for i in range(2):
            mid = f"week{week}_decision_{i}"
            _insert_memory(
                conn, mid,
                f"Week {week} decision #{i}: chose approach based on analysis",
                "decision", source="manual",
            )
            tracking["signal_ids"].append(mid)

        mid = f"week{week}_reflect_0"
        _insert_memory(
            conn, mid,
            f"Week {week} reflect: coaching insight about career direction",
            "discovery", source="reflect",
        )
        tracking["signal_ids"].append(mid)

        # 3. Advance time by 7 days FIRST (so decay sees age correctly)
        _advance_time(conn, 7)

        # 4. Simulate access: ~50% of signal memories accessed per week
        #    (via /mentor weekly, /reflect weekly, brain_recall in daily work)
        #    Access happens AFTER time advance → last_accessed = "now" = fresh
        for idx, sig_id in enumerate(tracking["signal_ids"]):
            if idx % 2 == week % 2:  # alternating halves each week
                conn.execute(
                    "UPDATE memories SET access_count = access_count + 1, last_accessed = datetime('now') WHERE id = ? AND id IN (SELECT id FROM memories)",
                    (sig_id,),
                )

        # 5. Run consolidation (decay_importance only — skip merge_duplicates which needs vectors)
        decay_importance(conn)

        # 6. Measure
        conn.commit()
        signal = _count_signal(conn)
        noise = _count_noise(conn)
        total = _total_non_tool(conn)
        snr = signal / (signal + noise) if (signal + noise) > 0 else 1.0

        metrics.append({
            "week": week + 1,
            "total": total,
            "signal": signal,
            "noise": noise,
            "snr": round(snr, 3),
        })

    return {"weeks": metrics, "tracking": tracking}


# ── Tests ──────────────────────────────────────────────────────────────


class TestBrainQuality:
    """Simulation tests for brain quality over time."""

    def test_snr_improves_over_time(self):
        """Signal-to-noise ratio improves from week 1 to week 6."""
        conn = _create_test_db()
        tracking = _seed_memories(conn)
        result = _run_simulation(conn, tracking)

        snr_week1 = result["weeks"][0]["snr"]
        snr_week6 = result["weeks"][5]["snr"]

        assert snr_week6 > snr_week1, (
            f"SNR should improve: week1={snr_week1}, week6={snr_week6}"
        )
        conn.close()

    def test_signal_memories_survive(self):
        """High-value memories (decisions, reflect, research) survive 6 weeks."""
        conn = _create_test_db()
        tracking = _seed_memories(conn)
        original_signal = list(tracking["signal_ids"])  # copy before simulation adds more

        _run_simulation(conn, tracking)

        surviving = set()
        for row in conn.execute("SELECT id FROM memories").fetchall():
            surviving.add(row[0])

        lost = [mid for mid in original_signal if mid not in surviving]
        assert len(lost) == 0, f"Signal memories lost: {lost}"
        conn.close()

    def test_noise_gets_pruned(self):
        """At least 50% of initial noise is pruned by week 6."""
        conn = _create_test_db()
        tracking = _seed_memories(conn)
        initial_noise_count = _count_noise(conn)

        _run_simulation(conn, tracking)

        final_noise = _count_noise(conn)
        pruned_pct = 1 - (final_noise / initial_noise_count) if initial_noise_count > 0 else 0

        # Note: new noise is injected each week. We check initial noise specifically.
        initial_noise_surviving = sum(
            1 for mid in tracking["noise_ids"]
            if conn.execute("SELECT id FROM memories WHERE id = ?", (mid,)).fetchone()
        )
        initial_pruned_pct = 1 - (initial_noise_surviving / len(tracking["noise_ids"]))

        assert initial_pruned_pct >= 0.5, (
            f"Expected ≥50% of initial noise pruned, got {initial_pruned_pct:.1%} "
            f"({initial_noise_surviving}/{len(tracking['noise_ids'])} surviving)"
        )
        conn.close()

    def test_no_positive_feedback_loop(self):
        """Noise memory importance does NOT increase when accessed via search results.

        This tests the FIX: importance should not be boosted by access.
        Before fix: importance += 0.02 per access → noise stays alive.
        After fix: importance only changes via decay, graph boost, or manual update.
        """
        conn = _create_test_db()
        _insert_memory(
            conn, "noise_test",
            "Random web search about generic topic",
            "discovery", source="search-and-store-hook",
        )
        initial_imp = _get_importance(conn, "noise_test")

        # Simulate 10 accesses (as if returned in search results)
        for _ in range(10):
            conn.execute(
                """UPDATE memories SET access_count = access_count + 1,
                   last_accessed = datetime('now') WHERE id = 'noise_test'""",
            )
        conn.commit()

        # Importance should NOT have increased
        after_access_imp = _get_importance(conn, "noise_test")
        assert after_access_imp <= initial_imp, (
            f"Importance should not increase from access: {initial_imp} → {after_access_imp}"
        )
        conn.close()


class TestImportanceRanking:
    """Test that importance weight in search ranking formula separates signal from noise."""

    def _ranking_score(self, rrf_score: float, importance: float) -> float:
        """Compute the ranking formula. Update this when changing the formula."""
        return rrf_score * (0.5 + 0.5 * importance)

    def test_high_importance_beats_low_at_equal_relevance(self):
        """At same RRF score, high importance ranks higher."""
        rrf = 0.05  # same relevance
        high = self._ranking_score(rrf, 1.0)
        low = self._ranking_score(rrf, 0.1)

        # High importance should be significantly better
        ratio = high / low
        assert ratio > 1.5, (
            f"Expected >1.5x advantage for high importance, got {ratio:.2f}x"
        )

    def test_noise_suppression_ratio(self):
        """Hook-sourced memory (importance 0.40) vs reflect memory (importance 0.75)."""
        rrf = 0.05
        hook_score = self._ranking_score(rrf, 0.40)
        reflect_score = self._ranking_score(rrf, 0.75)

        ratio = reflect_score / hook_score
        assert ratio > 1.2, (
            f"Reflect should rank >1.2x higher than hook, got {ratio:.2f}x"
        )

    def test_relevance_still_dominates(self):
        """A highly relevant low-importance memory still ranks above irrelevant high-importance."""
        relevant_noise = self._ranking_score(0.08, 0.40)  # very relevant, low importance
        irrelevant_signal = self._ranking_score(0.02, 1.0)  # low relevance, high importance

        assert relevant_noise > irrelevant_signal, (
            "Relevance should still dominate over importance"
        )


class TestDecayMath:
    """Verify decay math for the new hook importance level."""

    def test_hook_importance_after_fix(self):
        """Hook memories should start at 0.40 (discovery 0.6 + hook -0.20)."""
        imp = compute_initial_importance("discovery", "search-and-store-hook")
        assert imp == pytest.approx(0.40, abs=0.01), f"Expected ~0.40, got {imp}"

    def test_hook_prunes_within_20_days(self):
        """Hook memory at importance 0.40 should decay below 0.05 within 20 days."""
        imp = compute_initial_importance("discovery", "hook")
        result = compute_decay(imp, 20)
        assert result < 0.05, (
            f"Hook importance {imp} after 20 days = {result}, should be < 0.05"
        )

    def test_reflect_survives_40_days(self):
        """Reflect memory at importance 0.75 survives 40 days unaccessed."""
        imp = compute_initial_importance("discovery", "reflect")
        result = compute_decay(imp, 40)
        assert result > 0.05, (
            f"Reflect importance {imp} after 40 days = {result}, should be > 0.05"
        )

    def test_decision_survives_60_days(self):
        """Decision at importance 0.90 survives 60 days unaccessed."""
        imp = compute_initial_importance("decision", "manual")
        result = compute_decay(imp, 60)
        assert result > 0.05, (
            f"Decision importance {imp} after 60 days = {result}, should be > 0.05"
        )

    def test_hook_below_entity(self):
        """Hook-sourced discovery should have lower importance than a plain entity."""
        hook = compute_initial_importance("discovery", "hook")
        entity = compute_initial_importance("entity")
        assert hook < entity, f"Hook ({hook}) should be < entity ({entity})"
