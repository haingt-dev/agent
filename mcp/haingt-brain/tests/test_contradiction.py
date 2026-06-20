"""Tests for contradiction.py (D5) — anti-series guard + escalation gate."""

import json
from unittest.mock import patch

from haingt_brain import contradiction
from haingt_brain.judge import STATUS_OK, STATUS_TIMEOUT


def _resp(verdict, confidence):
    return (
        {"choices": [{"message": {"content": json.dumps({"verdict": verdict, "confidence": confidence})}}]},
        STATUS_OK,
    )


class TestAntiSeriesGuard:
    def test_phase_logs_blocked_without_llm(self):
        """The headline safety test: formulaic phase-logs must NEVER reach the LLM."""
        a = "Iron Cradle P-Combat-b EXECUTED + GREEN (2026-06-04, ADR-0020)"
        b = "Iron Cradle P-Combat-a EXECUTED + GREEN (2026-06-03, ADR-0019)"
        with patch.object(contradiction, "_chat_completion") as m:
            res = contradiction.classify_pair(a, b)
            m.assert_not_called()
        assert res["verdict"] == "unrelated"

    def test_tier_progress_logs_blocked(self):
        a = "PROGRESS — aseprite-mcp Tier 2a LANDED. 117 tools, 108 tests green"
        b = "PROGRESS — aseprite-mcp Tier 1 LANDED. 110 tools, 99 tests green"
        with patch.object(contradiction, "_chat_completion") as m:
            res = contradiction.classify_pair(a, b)
            m.assert_not_called()
        assert res["verdict"] == "unrelated"

    def test_dated_measurement_series_blocked(self):
        a = "Sa weight on 2026-04-16 was 3600 g at birth"
        b = "Sa weight on 2026-05-16 was 5200 g at one month"
        with patch.object(contradiction, "_chat_completion") as m:
            res = contradiction.classify_pair(a, b)
            m.assert_not_called()
        assert res["verdict"] == "unrelated"

    def test_is_series_pair_helper(self):
        assert contradiction.is_series_pair("P-Combat-a EXECUTED", "P-Combat-b GREEN")
        assert not contradiction.is_series_pair("ate banana", "ate apple")


class TestEscalationGate:
    def test_reversal_language_allows_supersede(self):
        a = "Wednesday: ate banana"
        b = "Wednesday: couldn't buy banana, ate apple instead"
        with patch.object(contradiction, "_chat_completion", return_value=_resp("supersedes", 0.9)):
            res = contradiction.classify_pair(a, b)
        assert res["verdict"] == "supersedes"
        assert res["confidence"] == 0.9

    def test_no_reversal_downgrades_to_contradicts(self):
        a = "prefer dark theme for the editor"
        b = "prefer light theme for the editor"
        with patch.object(contradiction, "_chat_completion", return_value=_resp("supersedes", 0.9)):
            res = contradiction.classify_pair(a, b)
        assert res["verdict"] == "contradicts"  # downgraded: no reversal language

    def test_contradicts_passes_through(self):
        a = "end-Sep reserves projected 170M"
        b = "end-Sep reserves projected 210M after windfall"
        with patch.object(contradiction, "_chat_completion", return_value=_resp("contradicts", 0.7)):
            res = contradiction.classify_pair(a, b)
        assert res["verdict"] == "contradicts"


class TestSoftFail:
    def test_timeout_returns_unrelated(self):
        with patch.object(contradiction, "_chat_completion", return_value=(None, STATUS_TIMEOUT)):
            res = contradiction.classify_pair("foo fact one", "bar fact two")
        assert res["verdict"] == "unrelated"
        assert res["confidence"] == 0.0

    def test_parse_error_returns_unrelated(self):
        bad = ({"choices": [{"message": {"content": "not json at all"}}]}, STATUS_OK)
        with patch.object(contradiction, "_chat_completion", return_value=bad):
            res = contradiction.classify_pair("foo fact one", "bar fact two")
        assert res["verdict"] == "unrelated"

    def test_confidence_clamped(self):
        with patch.object(contradiction, "_chat_completion", return_value=_resp("contradicts", 5.0)):
            res = contradiction.classify_pair("foo fact one", "bar fact two")
        assert res["confidence"] == 1.0
