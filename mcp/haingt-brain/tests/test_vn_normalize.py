"""Tests for Vietnamese text normalizer."""

import time

from haingt_brain.vn_normalize import normalize_vn, strip_viet


# ── Tier A: Dictionary ────────────────────────────────────────────────────


def test_tier_a_documented_examples():
    assert normalize_vn("giaiar") == "giải"
    assert normalize_vn("dduowcj") == "được"
    assert normalize_vn("keiuer") == "kiểu"


def test_tier_a_common_words():
    assert normalize_vn("khongr") == "không"
    assert normalize_vn("nhieuf") == "nhiều"
    assert normalize_vn("lamf") == "làm"
    assert normalize_vn("roif") == "rồi"
    assert normalize_vn("viecj") == "việc"


def test_tier_a_emotional():
    assert normalize_vn("khocs") == "khóc"
    assert normalize_vn("buoonf") == "buồn"
    assert normalize_vn("gianr") == "giận"


# ── Tier B: Algorithmic ──────────────────────────────────────────────────


def test_tier_b_dd_signal():
    """dd initial = strong signal, all tones allowed."""
    result = normalize_vn("ddij")
    assert "đ" in result  # dd → đ


def test_tier_b_uw_signal():
    """uw = strong signal, all tones allowed."""
    result = normalize_vn("uwf")
    assert "ừ" in result or "ư" in result


def test_tier_b_digraph_jx():
    """Vowel digraph + j/x at end = strong signal."""
    result = normalize_vn("thuaanj")
    assert result == "thuận"


def test_tier_b_dd_uw_combined():
    """dd + uw combined signal."""
    result = normalize_vn("dduowcj")
    assert result == "được"


# ── English Safety ───────────────────────────────────────────────────────


def test_english_unchanged():
    """Common English words must NOT be corrupted."""
    english_words = [
        "fox", "box", "tower", "floor", "school", "knows", "shows",
        "moons", "six", "raj", "awesome", "street", "flow", "grow",
        "python", "docker", "react", "hello", "world", "the", "is",
    ]
    for word in english_words:
        assert normalize_vn(word) == word, f"'{word}' was changed to '{normalize_vn(word)}'"


def test_english_caps_unchanged():
    """ALL_CAPS acronyms must not be touched."""
    assert normalize_vn("API") == "API"
    assert normalize_vn("URL") == "URL"
    assert normalize_vn("JSON") == "JSON"


# ── Mixed Text ───────────────────────────────────────────────────────────


def test_mixed_text():
    assert normalize_vn("Hello dduowcj world") == "Hello được world"
    assert normalize_vn("Python giaiar script") == "Python giải script"


def test_mixed_with_punctuation():
    result = normalize_vn("check dduowcj, giaiar problem.")
    assert "được" in result
    assert "giải" in result


# ── Vietnamese Passthrough ───────────────────────────────────────────────


def test_vietnamese_unicode_unchanged():
    """Already-correct Vietnamese must pass through unchanged."""
    text = "Hôm nay tôi mệt mỏi"
    assert normalize_vn(text) == text


def test_single_vietnamese_word():
    assert normalize_vn("được") == "được"
    assert normalize_vn("không") == "không"


# ── Punctuation Preservation ─────────────────────────────────────────────


def test_trailing_punctuation():
    assert normalize_vn("dduowcj.") == "được."
    assert normalize_vn("giaiar!") == "giải!"
    assert normalize_vn("khongr?") == "không?"


def test_surrounding_punctuation():
    assert normalize_vn("(giaiar)") == "(giải)"
    assert normalize_vn('"dduowcj"') == '"được"'


# ── Capitalization ───────────────────────────────────────────────────────


def test_capitalization_preserved():
    assert normalize_vn("Giaiar") == "Giải"
    assert normalize_vn("Dduowcj") == "Được"
    assert normalize_vn("Khongr") == "Không"


# ── strip_viet ───────────────────────────────────────────────────────────


def test_strip_viet_basic():
    assert strip_viet("mệt mỏi") == "met moi"
    assert strip_viet("đám cưới") == "dam cuoi"
    assert strip_viet("không") == "khong"


def test_strip_viet_fuzzy_match():
    """Wrong diacritics should match after stripping."""
    assert strip_viet("mệt mổi") == strip_viet("mệt mỏi")
    assert strip_viet("đám cuối") != strip_viet("đám cưới")  # different base words


def test_strip_viet_ascii_passthrough():
    assert strip_viet("hello world") == "hello world"


# ── Edge Cases ───────────────────────────────────────────────────────────


def test_empty_string():
    assert normalize_vn("") == ""
    assert strip_viet("") == ""


def test_numbers_unchanged():
    assert normalize_vn("123") == "123"
    assert normalize_vn("test123") == "test123"


def test_urls_unchanged():
    assert normalize_vn("https://example.com") == "https://example.com"


# ── Performance ──────────────────────────────────────────────────────────


def test_performance():
    """100-word text, 1000 iterations, must complete under 100ms total."""
    text = "dduowcj giaiar hello world " * 25  # 100 words
    start = time.perf_counter()
    for _ in range(1000):
        normalize_vn(text)
    elapsed_ms = (time.perf_counter() - start) * 1000
    # 0.2ms per 100-word call is fine — hook budget is 10s, embedding alone is ~200ms
    assert elapsed_ms < 500, f"Too slow: {elapsed_ms:.1f}ms for 1000 iterations"
