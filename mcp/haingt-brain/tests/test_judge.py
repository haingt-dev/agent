"""Tests for the LLM judge layer (Path A)."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from haingt_brain import judge


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure judge LRU cache is empty between tests."""
    judge._judge_cache.clear()
    yield
    judge._judge_cache.clear()


@pytest.fixture
def candidates():
    return [
        {"id": "a1", "content": "Decision about IronCradle navigation", "type": "decision",
         "tags": ["godot", "ironcradle"], "project": "IronCradle", "created_at": "2026-05-20T10:00:00"},
        {"id": "b2", "content": "Bookie video pipeline notes", "type": "discovery",
         "tags": ["video"], "project": "Bookie", "created_at": "2026-04-01T10:00:00"},
        {"id": "c3", "content": "Pattern for AI agent loops", "type": "pattern",
         "tags": ["ai"], "project": None, "created_at": "2026-05-15T10:00:00"},
        {"id": "d4", "content": "Godot script ECS pattern", "type": "pattern",
         "tags": ["godot"], "project": "IronCradle", "created_at": "2026-05-22T10:00:00"},
        {"id": "e5", "content": "Old godot deprecation note", "type": "discovery",
         "tags": ["godot"], "project": "IronCradle", "created_at": "2025-12-01T10:00:00"},
    ]


def _mock_chat_response(scores: list[dict], prompt_tokens: int = 200, completion_tokens: int = 50):
    """Build a mock OpenAI chat.completions.create response."""
    msg = MagicMock()
    msg.message.content = json.dumps({"scores": scores})
    resp = MagicMock()
    resp.choices = [msg]
    resp.usage.prompt_tokens = prompt_tokens
    resp.usage.completion_tokens = completion_tokens
    return resp


class TestDisabled:
    def test_returns_rrf_top_n_when_disabled(self, candidates):
        with patch.dict(os.environ, {"JUDGE_ENABLED": "false"}, clear=False):
            results, status, tel = judge.judge_relevance("query", candidates, n=3)
        assert status == judge.STATUS_DISABLED
        assert [r["id"] for r in results] == ["a1", "b2", "c3"]
        assert tel["cost_usd"] == 0.0


class TestMinCandidates:
    def test_skip_when_pool_below_threshold(self, candidates):
        with patch.dict(os.environ, {"JUDGE_ENABLED": "true", "JUDGE_MIN_CANDIDATES": "10"}, clear=False):
            results, status, _ = judge.judge_relevance("query", candidates, n=3)
        assert status == judge.STATUS_MIN_CANDIDATES
        assert [r["id"] for r in results] == ["a1", "b2", "c3"]


class TestReranking:
    def test_judge_reorders_by_score(self, candidates):
        # Mock: judge ranks d4 highest (project + topic match), then a1, then c3
        mock_scores = [
            {"id": "a1", "score": 7},
            {"id": "b2", "score": 1},  # wrong project, hard distractor
            {"id": "c3", "score": 4},
            {"id": "d4", "score": 9},
            {"id": "e5", "score": 3},
        ]
        with patch.dict(os.environ, {"JUDGE_ENABLED": "true", "JUDGE_MIN_CANDIDATES": "4"}, clear=False):
            with patch.object(judge, "_get_client") as mock_client_factory:
                mock_client = MagicMock()
                mock_client.with_options.return_value = mock_client
                mock_client.chat.completions.create.return_value = _mock_chat_response(mock_scores)
                mock_client_factory.return_value = mock_client

                results, status, tel = judge.judge_relevance(
                    "godot navigation IronCradle", candidates, n=3
                )

        assert status == judge.STATUS_OK
        assert [r["id"] for r in results] == ["d4", "a1", "c3"]
        # Hard distractor b2 (wrong project) should NOT be in top-3
        assert "b2" not in [r["id"] for r in results]
        assert tel["tokens_in"] == 200
        assert tel["tokens_out"] == 50
        assert tel["cost_usd"] > 0


class TestFallback:
    def test_timeout_falls_back_to_rrf(self, candidates):
        with patch.dict(os.environ, {"JUDGE_ENABLED": "true", "JUDGE_MIN_CANDIDATES": "4"}, clear=False):
            with patch.object(judge, "_get_client") as mock_client_factory:
                mock_client = MagicMock()
                mock_client.with_options.return_value = mock_client

                class FakeTimeoutError(Exception):
                    pass
                FakeTimeoutError.__name__ = "TimeoutError"
                mock_client.chat.completions.create.side_effect = FakeTimeoutError("timed out")
                mock_client_factory.return_value = mock_client

                results, status, _ = judge.judge_relevance("query", candidates, n=3)

        assert status == judge.STATUS_TIMEOUT
        assert [r["id"] for r in results] == ["a1", "b2", "c3"]  # RRF order preserved

    def test_rate_limit_falls_back(self, candidates):
        with patch.dict(os.environ, {"JUDGE_ENABLED": "true", "JUDGE_MIN_CANDIDATES": "4"}, clear=False):
            with patch.object(judge, "_get_client") as mock_client_factory:
                mock_client = MagicMock()
                mock_client.with_options.return_value = mock_client

                class FakeRateLimitError(Exception):
                    pass
                FakeRateLimitError.__name__ = "RateLimitError"
                mock_client.chat.completions.create.side_effect = FakeRateLimitError("429")
                mock_client_factory.return_value = mock_client

                results, status, _ = judge.judge_relevance("query", candidates, n=3)

        assert status == judge.STATUS_RATE_LIMIT
        assert [r["id"] for r in results] == ["a1", "b2", "c3"]

    def test_malformed_json_falls_back(self, candidates):
        with patch.dict(os.environ, {"JUDGE_ENABLED": "true", "JUDGE_MIN_CANDIDATES": "4"}, clear=False):
            with patch.object(judge, "_get_client") as mock_client_factory:
                mock_client = MagicMock()
                mock_client.with_options.return_value = mock_client
                bad_resp = MagicMock()
                bad_msg = MagicMock()
                bad_msg.message.content = "not json {"
                bad_resp.choices = [bad_msg]
                bad_resp.usage = None
                mock_client.chat.completions.create.return_value = bad_resp
                mock_client_factory.return_value = mock_client

                results, status, _ = judge.judge_relevance("query", candidates, n=3)

        assert status == judge.STATUS_PARSE_ERROR
        assert [r["id"] for r in results] == ["a1", "b2", "c3"]


class TestCache:
    def test_cache_hit_on_identical_set(self, candidates):
        mock_scores = [{"id": c["id"], "score": 10 - i} for i, c in enumerate(candidates)]
        with patch.dict(os.environ, {"JUDGE_ENABLED": "true", "JUDGE_MIN_CANDIDATES": "4"}, clear=False):
            with patch.object(judge, "_get_client") as mock_client_factory:
                mock_client = MagicMock()
                mock_client.with_options.return_value = mock_client
                mock_client.chat.completions.create.return_value = _mock_chat_response(mock_scores)
                mock_client_factory.return_value = mock_client

                _, status1, tel1 = judge.judge_relevance("godot query", candidates, n=3)
                _, status2, tel2 = judge.judge_relevance("godot query", candidates, n=3)

        assert status1 == judge.STATUS_OK
        assert status2 == judge.STATUS_OK
        assert tel1["cache_hit"] is False
        assert tel2["cache_hit"] is True
        # Should have called the API only once
        assert mock_client.chat.completions.create.call_count == 1

    def test_cache_key_order_independent(self, candidates):
        """Same candidates in different order → same cache key."""
        ids_a = [c["id"] for c in candidates]
        ids_b = list(reversed(ids_a))
        key_a = judge._cache_key("q", ids_a)
        key_b = judge._cache_key("q", ids_b)
        assert key_a == key_b


class TestOversamplePolicy:
    def test_oversample_k_floor(self):
        from haingt_brain.tools.recall import _oversample_k
        assert _oversample_k(1) == 10  # floor
        assert _oversample_k(3) == 10  # max(9, 10) = 10
        assert _oversample_k(4) == 12
        assert _oversample_k(5) == 15
        assert _oversample_k(7) == 20  # max(21, 10) capped at 20

    def test_oversample_k_ceiling(self):
        from haingt_brain.tools.recall import _oversample_k
        assert _oversample_k(20) == 20  # ceiling
        assert _oversample_k(100) == 20


class TestRecursionGuard:
    def test_judge_module_does_not_import_mcp_tools(self):
        """Judge must never import brain_recall or any MCP tool to avoid recursion."""
        import inspect
        src = inspect.getsource(judge)
        # Forbidden imports
        assert "from .tools.recall" not in src
        assert "import brain_recall" not in src
        assert "from .tools" not in src  # no tool imports at all
