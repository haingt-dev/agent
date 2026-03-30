"""Tests for memory importance system."""

import math

from haingt_brain.importance import (
    BASE_IMPORTANCE,
    SOURCE_BOOST,
    compute_access_boost,
    compute_decay,
    compute_initial_importance,
)


# ── Initial Importance ──────────────────────────────────────────────────


def test_initial_importance_by_type():
    """Each type maps to its expected base importance."""
    assert compute_initial_importance("preference") == 0.9
    assert compute_initial_importance("decision") == 0.8
    assert compute_initial_importance("pattern") == 0.7
    assert compute_initial_importance("discovery") == 0.6
    assert compute_initial_importance("entity") == 0.5
    assert compute_initial_importance("tool") == 0.4
    assert compute_initial_importance("session") == 0.3


def test_initial_importance_unknown_type():
    """Unknown type defaults to 0.5."""
    assert compute_initial_importance("unknown") == 0.5


def test_initial_importance_with_source():
    """Source boost is additive to base importance."""
    # decision (0.8) + reflect (0.15) = 0.95
    assert abs(compute_initial_importance("decision", "reflect") - 0.95) < 1e-9
    # discovery (0.6) + manual (0.1) = 0.7
    assert abs(compute_initial_importance("discovery", "manual") - 0.7) < 1e-9
    # entity (0.5) + hook (-0.05) = 0.45
    assert abs(compute_initial_importance("entity", "hook") - 0.45) < 1e-9
    # session (0.3) + consolidation (-0.1) = 0.2
    assert abs(compute_initial_importance("session", "consolidation") - 0.2) < 1e-9


def test_initial_importance_clamped():
    """Result is clamped to [0.0, 1.0]."""
    # preference (0.9) + reflect (0.15) = 1.05 → clamped to 1.0
    assert compute_initial_importance("preference", "reflect") == 1.0
    # session (0.3) + consolidation (-0.1) = 0.2
    assert abs(compute_initial_importance("session", "consolidation") - 0.2) < 1e-9


def test_initial_importance_no_source():
    """None source gives zero boost."""
    assert compute_initial_importance("decision", None) == 0.8
    assert compute_initial_importance("decision") == 0.8


def test_initial_importance_unknown_source():
    """Unknown source gives zero boost."""
    assert compute_initial_importance("decision", "unknown_source") == 0.8


# ── Decay ───────────────────────────────────────────────────────────────


def test_decay_high_importance_slow():
    """High importance decays slowly."""
    # importance=1.0, 30 days → should retain significant value
    result = compute_decay(1.0, 30)
    assert result > 0.3, f"High importance decayed too fast: {result}"


def test_decay_low_importance_fast():
    """Low importance decays quickly."""
    # importance=0.3, 30 days → should be near zero
    result = compute_decay(0.3, 30)
    assert result < 0.1, f"Low importance didn't decay fast enough: {result}"


def test_decay_zero_days():
    """Zero days = no decay."""
    assert compute_decay(0.8, 0) == 0.8


def test_decay_zero_importance():
    """Zero importance stays zero."""
    assert compute_decay(0.0, 30) == 0.0


def test_decay_negative_days():
    """Negative days (future) = no decay."""
    assert compute_decay(0.8, -5) == 0.8


def test_decay_formula_correctness():
    """Verify the Ebbinghaus formula produces expected values."""
    importance = 0.8
    days = 10
    decay_rate = 0.16 * (1 - importance * 0.8)
    expected = importance * math.exp(-decay_rate * days)
    assert abs(compute_decay(importance, days) - expected) < 1e-10


def test_decay_half_life_high_importance():
    """importance=1.0 should have half-life around 22 days."""
    result = compute_decay(1.0, 22)
    # Should be roughly 0.5 (within 10%)
    assert 0.4 < result < 0.6, f"Half-life mismatch: {result} at 22 days"


def test_decay_half_life_low_importance():
    """importance=0.3 should have half-life around 5-6 days."""
    result = compute_decay(0.3, 6)
    # Should be roughly 0.15 (within 30%)
    assert 0.1 < result < 0.2, f"Half-life mismatch: {result} at 6 days"


# ── Access Boost ────────────────────────────────────────────────────────


def test_access_boost_zero_count():
    """Zero access = no boost."""
    assert compute_access_boost(0.5, 0) == 0.5


def test_access_boost_increases():
    """More access = higher importance."""
    base = 0.5
    assert compute_access_boost(base, 5) > base
    assert compute_access_boost(base, 10) > compute_access_boost(base, 5)
    assert compute_access_boost(base, 50) > compute_access_boost(base, 10)


def test_access_boost_capped():
    """Importance never exceeds 1.0."""
    assert compute_access_boost(0.9, 1000) == 1.0


def test_access_boost_logarithmic():
    """Boost is logarithmic — diminishing returns."""
    base = 0.5
    boost_10 = compute_access_boost(base, 10) - base
    boost_100 = compute_access_boost(base, 100) - base
    # 10x more access should give less than 2x more boost
    assert boost_100 < 2 * boost_10


# ── Prune Threshold ─────────────────────────────────────────────────────


def test_prune_threshold_reachable():
    """Low importance memories can decay below 0.05."""
    # importance=0.3 after 60 days should be < 0.05
    result = compute_decay(0.3, 60)
    assert result < 0.05, f"Should be prunable: {result}"


def test_prune_threshold_high_importance_safe():
    """High importance memories stay above 0.05 for a reasonable period."""
    # importance=0.8 after 30 days should still be > 0.05
    result = compute_decay(0.8, 30)
    assert result > 0.05, f"High importance shouldn't be pruned at 30 days: {result}"
    # importance=1.0 after 60 days should still be > 0.05
    result_max = compute_decay(1.0, 60)
    assert result_max > 0.05, f"Max importance shouldn't be pruned at 60 days: {result_max}"


# ── Edge Cases ──────────────────────────────────────────────────────────


def test_all_types_in_base():
    """Every valid memory type has a base importance."""
    for t in ["decision", "discovery", "pattern", "entity", "preference", "session", "tool"]:
        assert t in BASE_IMPORTANCE


def test_all_sources_in_boost():
    """Every documented source has a boost value."""
    for s in ["reflect", "manual", "mentor", "research", "wrap", "hook", "consolidation"]:
        assert s in SOURCE_BOOST


def test_importance_range():
    """All type × source combinations produce values in [0.0, 1.0]."""
    for t in BASE_IMPORTANCE:
        for s in SOURCE_BOOST:
            result = compute_initial_importance(t, s)
            assert 0.0 <= result <= 1.0, f"{t}×{s} = {result}"
