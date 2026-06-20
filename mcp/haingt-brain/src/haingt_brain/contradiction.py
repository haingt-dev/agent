"""Belief-revision classifier: decide if memory B corrects / contradicts memory A.

Shared engine for the write-time guard (save.py) and the batch supersede_pass
(consolidate.py). Two deterministic guards bracket a small LLM call so the model
is never trusted blindly:

  1. ANTI-SERIES GUARD (runs BEFORE the LLM): formulaic progress/phase logs and
     dated measurement series (IronCradle "P-Combat-b EXECUTED + GREEN", aseprite
     "Tier 2a LANDED", Sa weight 3600g→6500g) look like corrections to a similarity
     metric AND to gpt-5.4-nano (measured over-call), but are DISTINCT TRUE siblings.
     If both sides look like a series, return `unrelated` without calling the LLM.

  2. ESCALATION GATE (runs AFTER the LLM): only allow the hard `supersedes` verdict
     (which hides the target via SUPERSEDED_FILTER) when explicit reversal language
     is present. Otherwise downgrade to `contradicts` (surface both, hide nothing).

Transport: reuses judge._chat_completion (pure urllib HTTP). It does NOT import
judge_relevance or the judge SYSTEM_PROMPT — judge is contractually recall-only;
only the stateless HTTP function is borrowed.
"""

import json
import os
import re

from .embeddings import _load_env
from .judge import (
    STATUS_API_ERROR,
    STATUS_OK,
    STATUS_RATE_LIMIT,
    STATUS_TIMEOUT,
    _chat_completion,
    _service_tier,
)

_load_env()

# Formulaic progress / phase / ADR / tier markers → distinct-true siblings.
SERIES_RE = re.compile(
    r"EXECUTED|GREEN|ADR-?\d+|Tier ?\d|\bP-?\d|P\dc|LANDED|milestone|\bGUT\b|✅",
    re.I,
)
# A numeric measurement token (weight/balance/count): part of a time-series sample.
MEASURE_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:g\b|kg|cm|gib|mib|gb|mb|chỉ|chi\b|%|tools?|tests?|commits?|triệu|M\b)",
    re.I,
)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{4}|\d{1,2}/\d{1,2}/\d{2,4}")

# Explicit reversal / correction language → eligible to HIDE (supersedes).
REVERSAL_RE = re.compile(
    r"\binstead\b|no longer|\bsai\b|reversed|RETIRED|now corrected|\bwrong\b"
    r"|deprecated|superseded|thay vì|đảo chiều|không còn|hủy bỏ",
    re.I,
)

CONTRADICTION_SYSTEM_PROMPT = """You decide the relationship between TWO memories from a personal knowledge base. Output STRICT JSON only: {"verdict": "supersedes"|"contradicts"|"unrelated", "confidence": <0.0-1.0>}.

Definitions:
- "supersedes": one memory makes the other FACTUALLY WRONG or stale — a value changed and the old statement is now incorrect, or a decision was reversed ("ate banana" → "couldn't buy banana, ate apple instead"; "use X" → "no longer using X"). The newer is correct; the older should be hidden.
- "contradicts": the two diverge but BOTH may legitimately hold — a state changed over time (a balance, a weight, a plan vs its outcome), or they describe the same subject from different angles. Keep both; just flag the tension.
- "unrelated": same topic words but NOT a correction — sequential progress/phase logs (e.g. "P-Combat-a EXECUTED" vs "P-Combat-b EXECUTED"), version/tier series, dated measurement samples, or genuinely different facts.

Rules:
- Phase logs, ADR entries, tier/progress series, and dated measurements are NEVER "supersedes" — they are distinct true records. Prefer "unrelated".
- Default to "contradicts" over "supersedes" unless one memory plainly invalidates the other.
- confidence reflects how sure you are of the verdict.
No prose. JSON object only."""

_VALID = {"supersedes", "contradicts", "unrelated"}


def is_series_pair(a: str, b: str) -> bool:
    """True when both memories look like distinct-true siblings (protect history).

    Conservative: when in doubt, return True so the LLM is never asked to judge a
    pair it is known to over-call as a correction.
    """
    a = a or ""
    b = b or ""
    if SERIES_RE.search(a) and SERIES_RE.search(b):
        return True
    if (DATE_RE.search(a) and DATE_RE.search(b)) and (MEASURE_RE.search(a) and MEASURE_RE.search(b)):
        return True
    return False


def has_reversal_language(content: str) -> bool:
    return bool(REVERSAL_RE.search(content or ""))


def _model() -> str:
    return os.environ.get("BRAIN_CONTRADICTION_MODEL", os.environ.get("JUDGE_MODEL", "gpt-5.4-nano"))


def _timeout() -> float:
    try:
        return float(os.environ.get("BRAIN_CONTRADICTION_TIMEOUT_S", "6.0"))
    except ValueError:
        return 6.0


def classify_pair(a_content: str, b_content: str) -> dict:
    """Classify the relationship between two memory contents.

    Returns {"verdict": "supersedes"|"contradicts"|"unrelated", "confidence": float}.
    Fail-safe: returns unrelated/0.0 on the anti-series guard, any LLM error, or a
    parse failure — the pipeline never auto-acts on an unclassified pair.
    """
    # Guard 1 — anti-series (deterministic, no LLM)
    if is_series_pair(a_content, b_content):
        return {"verdict": "unrelated", "confidence": 0.0, "reason": "series_guard"}

    msgs = [
        {"role": "system", "content": CONTRADICTION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Memory A:\n{(a_content or '')[:800]}\n\nMemory B:\n{(b_content or '')[:800]}"},
    ]
    timeout = _timeout()
    used_flex = _service_tier() == "flex"
    resp, status = _chat_completion(messages=msgs, timeout=timeout, model=_model())
    if status in (STATUS_API_ERROR, STATUS_TIMEOUT, STATUS_RATE_LIMIT) and used_flex:
        resp, status = _chat_completion(messages=msgs, timeout=timeout, model=_model(), force_tier="default")

    if status != STATUS_OK or not resp:
        return {"verdict": "unrelated", "confidence": 0.0, "reason": status}

    try:
        content = resp["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        verdict = str(parsed.get("verdict", "unrelated")).lower().strip()
        confidence = float(parsed.get("confidence", 0.0))
    except (KeyError, IndexError, ValueError, TypeError, json.JSONDecodeError):
        return {"verdict": "unrelated", "confidence": 0.0, "reason": "parse_error"}

    if verdict not in _VALID:
        verdict = "unrelated"
    confidence = max(0.0, min(1.0, confidence))

    # Guard 2 — escalation gate: only HIDE (supersedes) with explicit reversal language.
    if verdict == "supersedes" and not (
        has_reversal_language(a_content) or has_reversal_language(b_content)
    ):
        verdict = "contradicts"

    return {"verdict": verdict, "confidence": confidence}
