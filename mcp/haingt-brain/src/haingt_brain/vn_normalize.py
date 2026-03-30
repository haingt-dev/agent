"""Vietnamese text normalizer — zero external dependencies.

Handles:
1. Telex leak (Type 1): IME failed, raw ASCII keystrokes in text
   - Tier A: Curated dictionary for garbled/ambiguous sequences
   - Tier B: Algorithmic decoder for structurally clear Telex patterns
2. Diacritic stripping (Type 2): strip_viet() for fuzzy phrase comparison

Deliberately NOT handled:
3. Context-dependent spell check (Type 3): too risky without Vietnamese word corpus

Design: word-level processing, conservative (zero false positives > high recall),
pure stdlib, <1ms per typical prompt.
"""

import re
import unicodedata
from typing import Final

# ── Tier A: Curated dictionary ────────────────────────────────────────────
# Keys: ASCII Telex-leaked form (lowercase).
# Values: correct Vietnamese Unicode (NFC).
# INVARIANT: no key is a valid common English word.
# Extend this dict as new Telex leaks are encountered.

TELEX_DICT: Final[dict[str, str]] = {
    # Documented examples from Hải
    "giaiar": "giải",
    "keiuer": "kiểu",
    "duocd": "được",
    # Common conversational words (s/f/r tones without dd/uw — Tier B can't catch)
    "khongr": "không",
    "nhieuf": "nhiều",
    "lamf": "làm",
    "roif": "rồi",
    "viecj": "việc",
    "caans": "cần",
    "hieurs": "hiểu",
    "moij": "mỗi",
    "voij": "với",
    "thoif": "thời",
    "cuoois": "cuối",
    "ngoaif": "ngoài",
    "laij": "lại",
    "moirs": "mỏi",
    "mejtj": "mệt",
    # Alternate dd/uw forms beyond what Tier B handles
    "dduocj": "được",
    # Emotional words (important for hook emotional detection)
    "khocs": "khóc",
    "buoonf": "buồn",
    "gianr": "giận",
}

# ── Tier B: Algorithmic decoder constants ─────────────────────────────────

# Tone mark → Unicode combining character (NFD)
_TONE_MARKS: Final[dict[str, str]] = {
    "s": "\u0301",  # sắc (acute)
    "f": "\u0300",  # huyền (grave)
    "r": "\u0309",  # hỏi (hook above)
    "x": "\u0303",  # ngã (tilde)
    "j": "\u0323",  # nặng (dot below)
}

# Vowel digraph transforms — ORDER MATTERS (longest first)
_VOWEL_DIGRAPHS: Final[list[tuple[str, str]]] = [
    ("uow", "ươ"),
    ("uw", "ư"),
    ("ow", "ơ"),
    ("aw", "ă"),
    ("aa", "â"),
    ("ee", "ê"),
    ("oo", "ô"),
]

# Vietnamese vowel characters (lowercase, after digraph conversion)
_VIET_VOWELS: Final[frozenset[str]] = frozenset("aăâeêioôơuưy")
_MODIFIED_VOWELS: Final[frozenset[str]] = frozenset("ăâêôơư")

# English consonant clusters that never start Vietnamese words
_INVALID_INIT_CLUSTERS: Final[frozenset[str]] = frozenset({
    "bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr",
    "pl", "pr", "sc", "sk", "sl", "sm", "sn", "sp", "st",
    "sw", "tw", "wh", "wr",
})

# Strong Telex signal patterns — compiled once at module load
_DD_OR_UW: Final[re.Pattern] = re.compile(r"^dd|uw", re.IGNORECASE)
_DIGRAPH_JX: Final[re.Pattern] = re.compile(
    r"(?:ow|aw|aa|ee|oo)[jx]$", re.IGNORECASE
)
_DIGRAPH_FINAL_JX: Final[re.Pattern] = re.compile(
    r"(?:ow|aw|aa|ee|oo)(?:ch|nh|ng|[cmnpt])[jx]$", re.IGNORECASE
)


# ── Public API ────────────────────────────────────────────────────────────


def strip_viet(text: str) -> str:
    """Strip all Vietnamese diacritics for fuzzy comparison (not for storage).

    Removes: tones, horn (ơ/ư→o/u), breve (ă→a), circumflex (â/ê/ô→a/e/o), đ→d.
    Returns lowercase string for substring matching.

    Used by: detect_emotional_signals() in prompt-context.py.
    NOT for: FTS5 (handled by remove_diacritics=2 tokenizer).
    """
    result = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", result)
    return "".join(c for c in nfd if unicodedata.category(c)[0] != "M").lower()


def normalize_vn(text: str) -> str:
    """Normalize Vietnamese text: fix Telex leaks, preserve everything else.

    Word-by-word processing. Only modifies words that are:
    1. All-ASCII (Vietnamese Unicode passes through unchanged)
    2. In TELEX_DICT (Tier A), OR
    3. Matching strong Telex signal patterns (Tier B: dd, uw, digraph+j/x)

    Preserves: English words, technical terms, punctuation, whitespace, capitalization.
    """
    if not text:
        return text
    return " ".join(_normalize_word(w) for w in text.split())


# ── Internal ──────────────────────────────────────────────────────────────


def _starts_with_invalid_cluster(word: str) -> bool:
    """True if word starts with an English-only consonant cluster."""
    for cluster in _INVALID_INIT_CLUSTERS:
        if word.startswith(cluster):
            return True
    return False


def _find_tone_target(word: str) -> int:
    """Find index of the vowel that should receive the tone mark.

    Rules:
    1. Modified vowel (ă, â, ê, ô, ơ, ư) takes priority (last one for ươ, uô)
    2. Three vowels → middle one
    3. Two vowels + final consonant → last vowel
    4. Two vowels, no final → first vowel
    5. One vowel → that vowel
    """
    vowels = [(i, c) for i, c in enumerate(word) if c in _VIET_VOWELS]
    if not vowels:
        return -1
    if len(vowels) == 1:
        return vowels[0][0]

    # Modified vowels take priority
    modified = [(i, c) for i, c in vowels if c in _MODIFIED_VOWELS]
    if modified:
        return modified[-1][0]

    # Standard positional rules
    last_v_idx = vowels[-1][0]
    has_final = any(
        c.isalpha() and c not in _VIET_VOWELS for c in word[last_v_idx + 1 :]
    )

    if len(vowels) >= 3:
        return vowels[1][0]
    elif has_final:
        return vowels[-1][0]
    else:
        return vowels[0][0]


def _apply_tone(word: str, combining: str, idx: int) -> str:
    """Apply a combining tone mark to char at idx, then NFC normalize."""
    char = word[idx]
    toned = unicodedata.normalize("NFC", char + combining)
    return word[:idx] + toned + word[idx + 1 :]


def _telex_decode(word: str) -> str | None:
    """Attempt algorithmic Telex decode of an all-ASCII word.

    Returns decoded Vietnamese, or None if word should not be decoded.
    Only triggers on strong, unambiguous signals to prevent English false positives.
    """
    if not word.isascii() or not word.isalpha() or len(word) < 2:
        return None

    wl = word.lower()

    if _starts_with_invalid_cluster(wl):
        return None

    # Require at least one strong Telex signal
    has_dd_uw = bool(_DD_OR_UW.search(wl))
    has_digraph_jx = bool(_DIGRAPH_JX.search(wl)) or bool(
        _DIGRAPH_FINAL_JX.search(wl)
    )

    if not has_dd_uw and not has_digraph_jx:
        return None

    w = wl

    # Step 1: initial consonant dd → đ
    if w.startswith("dd"):
        w = "đ" + w[2:]

    # Step 2: vowel digraphs (longest first via _VOWEL_DIGRAPHS order)
    for src, dst in _VOWEL_DIGRAPHS:
        w = w.replace(src, dst)

    # Step 3: extract tone from last character
    tone_combining = None
    if w and w[-1] in _TONE_MARKS:
        tone_key = w[-1]
        # s/f/r tones only safe with dd/uw signal (avoids "knows", "shows" etc.)
        if tone_key in "sfr" and not has_dd_uw:
            return None
        tone_combining = _TONE_MARKS[tone_key]
        w = w[:-1]

    if not w:
        return None

    # Must contain at least one vowel
    if not any(c in _VIET_VOWELS for c in w):
        return None

    # Step 4: apply tone to target vowel
    if tone_combining:
        target = _find_tone_target(w)
        if target < 0:
            return None
        w = _apply_tone(w, tone_combining, target)

    # Step 5: restore original capitalization
    if word[0].isupper():
        w = w[0].upper() + w[1:]

    return w


def _normalize_word(word: str) -> str:
    """Normalize a single word token. Preserves surrounding punctuation."""
    # Separate leading/trailing punctuation
    i = 0
    while i < len(word) and not word[i].isalnum():
        i += 1
    j = len(word)
    while j > i and not word[j - 1].isalnum():
        j -= 1

    prefix = word[:i]
    core = word[i:j]
    suffix = word[j:]

    if not core:
        return word

    # Skip: already contains Vietnamese Unicode (not a Telex leak)
    if not core.isascii():
        return word

    # Skip: non-alphabetic (numbers, mixed, ALL_CAPS acronyms)
    if not core.isalpha() or (len(core) > 1 and core.isupper()):
        return word

    lower = core.lower()

    # Tier A: dictionary lookup (O(1), zero false positives)
    if lower in TELEX_DICT:
        result = TELEX_DICT[lower]
        if core[0].isupper():
            result = result[0].upper() + result[1:]
        return prefix + result + suffix

    # Tier B: algorithmic decoder (strong signals only)
    decoded = _telex_decode(core)
    if decoded is not None:
        return prefix + decoded + suffix

    return word
