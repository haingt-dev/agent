"""Memory importance: deterministic scoring from type × source + access + decay."""

import math

# Base importance by memory type
BASE_IMPORTANCE: dict[str, float] = {
    "preference": 0.9,  # User's stated preferences = high value
    "decision": 0.8,  # Architectural decisions
    "pattern": 0.7,  # Reusable patterns
    "discovery": 0.6,  # Findings
    "entity": 0.5,  # Reference entities
    "tool": 0.4,  # Tool definitions (auto-discovered)
    "session": 0.3,  # Session summaries (lowest)
}

# Source boost (additive, from metadata.source)
SOURCE_BOOST: dict[str, float] = {
    "reflect": 0.15,  # /reflect outputs are validated
    "manual": 0.1,  # Intentional brain_save
    "mentor": 0.1,  # /mentor insights
    "research": 0.05,  # /research findings
    "wrap": 0.0,  # /wrap auto-save = baseline
    "hook": -0.05,  # Auto-captured by hooks
    "consolidation": -0.1,  # System-generated digests
}


def compute_initial_importance(memory_type: str, source: str | None = None) -> float:
    """Compute importance at creation time from type + source.

    Normalizes hook-specific sources (e.g. "search-and-store-hook" → "hook" boost).
    Returns a value in [0.0, 1.0].
    """
    base = BASE_IMPORTANCE.get(memory_type, 0.5)
    if source:
        boost = SOURCE_BOOST.get(source, 0.0)
        # Normalize hook-specific sources (anything containing "hook")
        if boost == 0.0 and "hook" in source:
            boost = SOURCE_BOOST.get("hook", 0.0)
    else:
        boost = 0.0
    return max(0.0, min(1.0, base + boost))


def compute_graph_boost(conn, memory_id: str) -> float:
    """Boost importance based on knowledge graph connectivity.

    A memory connected to 5+ other memories is a hub — inherently more important.
    Max boost: +0.2 (at 10+ connections).
    """
    count = conn.execute(
        "SELECT COUNT(*) FROM relations WHERE source_id = ? OR target_id = ?",
        (memory_id, memory_id),
    ).fetchone()[0]
    return 0.02 * min(count, 10)


def compute_decay(importance: float, days_since_access: float) -> float:
    """Ebbinghaus-inspired exponential decay.

    High importance decays slowly, low importance fades fast.
    importance=1.0 → decay_rate ≈ 0.032 → half-life ~22 days
    importance=0.3 → decay_rate ≈ 0.122 → half-life ~6 days
    importance=0.1 → decay_rate ≈ 0.147 → half-life ~5 days

    Returns decayed importance (can reach 0.0).
    """
    if importance <= 0 or days_since_access <= 0:
        return importance
    decay_rate = 0.16 * (1 - importance * 0.8)
    return importance * math.exp(-decay_rate * days_since_access)


def compute_access_boost(current_importance: float, access_count: int) -> float:
    """Mild logarithmic boost from access frequency.

    Each doubling of access_count adds ~0.02 importance.
    Capped at 1.0.
    """
    if access_count <= 0:
        return current_importance
    boost = 0.03 * math.log1p(access_count)
    return min(1.0, current_importance + boost)
