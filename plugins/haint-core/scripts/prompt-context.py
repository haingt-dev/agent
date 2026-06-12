#!/usr/bin/env python3
"""UserPromptSubmit: Inject relevant brain context per user prompt.

Architecture: FTS5 pre-filter for tools, embed once for general memories.
Phase 2 skips the embedding API call when FTS5 returns enough tool results (~80%
of prompts), saving ~$0.001/prompt and ~300ms latency.

Dedup: tracks injected memory IDs in /tmp cache file. Only injects NEW
memories not already in the conversation's context window. Prevents
duplicate system-reminders accumulating tokens across prompts.

Over-fetch + post-filter dedup: searches return more results than needed
(FETCH_K > MAX_RESULTS), then dedup filters already-seen IDs, then top-K
selects from remaining. This ensures deduped slots get filled by next-best
results instead of being wasted.

Token cap: tracks cumulative injected chars across session. Stops injecting
when budget (MAX_INJECTED_CHARS) is exhausted, preventing context bloat
in long conversations. Resets with cache TTL (2 hours).

Phase 1: Hybrid search (FTS5 + vector RRF) for general memories
  - Project-scoped: (project = ? OR project IS NULL)
  - Type-weighted: decisions/discoveries/patterns rank before sessions
  - Over-fetch 8, output max 3

Phase 2: Semantic Toolbox (type='tool' only)
  - FTS5 first (~1ms, free): if 3+ results → skip embedding
  - Fall back to vector search only when FTS5 returns <3 results
  - Output max 3

Returns hookSpecificOutput JSON with additionalContext for Claude's context window.
"""

import hashlib
import json
import os
import re
import sqlite3
import struct
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "haingt-brain" / "brain.db"
BRAIN_ENV = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / ".env"

# General memory config
FETCH_K_GENERAL = 8  # over-fetch to compensate for dedup filtering
MAX_GENERAL_RESULTS = 3  # max results after dedup
MAX_CONTENT_LEN = 200
MIN_PROMPT_LENGTH = 10

# Tool search config
FETCH_K_TOOLS = 10  # over-fetch for dedup-free re-ranking
MAX_TOOL_RESULTS = 3  # top-3 tools per prompt
TOOL_VEC_FETCH_K = 400  # KNN cannot pre-filter type='tool' (~7% of vectors) —
                        # k=50 starved the filter to 0-2 rows (audit 2026-06-12)
TOOL_MIN_COSINE = 0.35  # relevance floor — calibrated 2026-06-12: true matches
                        # measured 0.435-0.438, observed noise <= 0.312
MAX_SUGGESTED_TOOLS = 40  # session-level once-per-tool suggestion cap

# Token budget caps
MAX_INJECTED_CHARS = 3000  # ~750 tokens, general memories across session
MAX_TOOL_INJECTED_CHARS = 6000  # ~1500 tokens, safety net for tool injections

# Embedding config
EMBED_MODEL = "text-embedding-3-large"
EMBED_DIMS = 3072
EMBED_TIMEOUT = 3  # seconds

# RRF config
RRF_K = 60  # balances FTS5 and vector scores
VEC_FETCH_K = 50  # over-fetch for post-filter

# Dedup + multi-turn config
CACHE_DIR = Path("/tmp")
CACHE_MAX_AGE = 7200  # 2 hours — reset after stale session or compaction
CACHE_MAX_IDS = 100  # cap tracked IDs to prevent unbounded growth
CACHE_MAX_KEYWORDS = 30  # max accumulated context words from recent prompts
CURRENT_PROMPT_MAX_CHARS = 1000  # current prompt keeps full text for embedding
MIN_WORD_LEN = 3  # filter very short words (articles, particles)

# Type priority: lower = higher priority in results.
# preference = highest-value type (curated feedback on how to work with Hải);
# entity demoted one tier — auto-extracted entities proved the stalest type
# in the 2026-06-12 audit (IronCradle "center of gravity" injected 200+ times
# post-pivot).
TYPE_PRIORITY = {
    "decision": 0,
    "discovery": 0,
    "pattern": 0,
    "preference": 0,
    "entity": 1,
    "session": 2,
}

# Emotional signal detection — expand query when personal/emotional context detected
# Only unambiguous signals. Avoid short Vietnamese words that appear in technical contexts.
EMOTIONAL_WORD_SIGNALS = {
    "khóc", "buồn", "giận", "tức", "stress", "anxious",
    "crying", "funeral", "grieving", "depressed",
}
EMOTIONAL_PHRASE_SIGNALS = [
    "mệt mỏi", "tâm lý", "cảm xúc", "lo lắng", "đau lòng",
    "ổn định lại", "đám tang", "đám cưới",
    "nói chuyện với vợ", "nói chuyện với duyên",
]
EMOTIONAL_EXPANSION = "emotional family relationships personal reflect"


def detect_emotional_signals(text: str) -> bool:
    """Check if prompt contains emotional/personal signals.
    Uses strip_viet() for fuzzy phrase matching (handles diacritic typos).
    """
    lower = text.lower()
    stripped_text = _strip_viet(text)
    # Phrase-level check (exact + fuzzy via diacritic stripping)
    for phrase in EMOTIONAL_PHRASE_SIGNALS:
        if phrase in lower:
            return True
        if _strip_viet(phrase) in stripped_text:
            return True
    # Single-word check (only unambiguous words)
    words = set(lower.split())
    stripped = {w.strip(",.!?;:'\"()[]{}") for w in words}
    return bool((words | stripped) & EMOTIONAL_WORD_SIGNALS)


# sqlite-vec: optional, enables vector search
try:
    import sqlite_vec

    HAS_VEC = True
except ImportError:
    HAS_VEC = False

# Vietnamese normalizer — imported from brain package (same pattern as entity-extract.py)
_BRAIN_SRC = Path.home() / "Projects" / "agent" / "mcp" / "haingt-brain" / "src"
try:
    sys.path.insert(0, str(_BRAIN_SRC))
    from haingt_brain.vn_normalize import normalize_vn as _normalize_vn
    from haingt_brain.vn_normalize import strip_viet as _strip_viet
except Exception:
    _normalize_vn = lambda x: x  # no-op fallback
    _strip_viet = lambda x: x.lower()  # fallback: just lowercase

# Output gate: LLM judge for retrieved memories.
# Shares JUDGE_ENABLED env toggle with brain_recall (Path A) so both paths
# turn on together. Soft-fails to RRF order on import/api error.
try:
    from haingt_brain.judge import judge_relevance as _judge_relevance
    _HAS_JUDGE = True
except Exception:
    _HAS_JUDGE = False
    _judge_relevance = None

# Near-duplicate dedup for the retrieved pool (same fact saved 2-3x eats
# injection slots). Soft-fails to the raw pool on import error.
try:
    from haingt_brain.search import dedup_pool as _dedup_pool
    _HAS_DEDUP = True
except Exception:
    _HAS_DEDUP = False
    _dedup_pool = None


# ── Input ─────────────────────────────────────────────────────────────────

def get_prompt() -> str | None:
    """Extract user prompt from hook stdin JSON."""
    try:
        data = json.loads(sys.stdin.read())
        return data.get("prompt", "")
    except Exception:
        return None


# ── Path C: skip gate ─────────────────────────────────────────────────────
# Bias HARD toward "include by default" — false positives (search when not needed)
# cost ~$0.001 + 300ms; false negatives (skip when memory would help) cost lost
# context and worse reasoning. Add patterns only when very confident.
#
# Continuation patterns are 5+ words because the ≤4-word gate already catches
# pure-ack prompts. These patterns target continuations/imperatives that bypass
# the word-count gate.
# Durable log dir — was /tmp (wiped on reboot → never accumulated a sample).
# ~/.local/state matches XDG; survives reboots so fire-rate/latency build up.
_LOG_DIR = Path.home() / ".local" / "state" / "haingt-brain"
try:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
SKIP_LOG = _LOG_DIR / "brain-skip.log"
LLM_TIEBREAK_LOG = _LOG_DIR / "brain-llm-tiebreak.log"
JUDGE_LOG = _LOG_DIR / "brain-judge.log"  # hook-side judge latency/outcome

# Hybrid Option 2: LLM tiebreaker config
LLM_CLASSIFIER_MODEL = "gpt-5.4-nano"
LLM_CLASSIFIER_TIMEOUT = 2.0  # synchronous pre-prompt gate — cap the tail, fall to heuristic
# (was 10.0: on a flex stall this blocked the prompt up to the 10s hook budget.
# Default-tier call measured ~1.2s from VN host, so 2.0s gives headroom to get
# the answer while capping worst-case stall 5x lower. Revisit from baseline ms= logs.)
# System prompt padded to ≥1024 tokens to trigger OpenAI prompt caching.
# Cached prefix billed at 10% standard rate; cache TTL 5-10 min in-memory.
LLM_CLASSIFIER_SYSTEM = (
    "You are a memory gatekeeper for an AI coding assistant. Each user prompt arrives "
    "and you must decide whether to inject relevant past memory context (prior decisions, "
    "patterns, discoveries, file/module knowledge) before the assistant responds. "
    "Memory injection is expensive — it costs tokens, consumes attention budget, and "
    "risks introducing irrelevant context that degrades reasoning quality. This effect "
    "is documented in the First Drop of Ink research (arXiv 2605.10828): even 10% hard "
    "distractors cause ~55% of total performance degradation in long-context reasoning. "
    "Your goal: be selective. Approve injection only when memory provides DECISIVE benefit. "
    "\n\n"
    "OUTPUT FORMAT (strict): exactly one token — 'yes' to allow injection, 'no' to reject. "
    "No punctuation, no explanation, no markdown, no quotes. Just yes or no.\n\n"
    "ALLOW (yes) when the prompt:\n"
    "- References past work, prior sessions, or earlier decisions ('the issue we discussed', 'remember when')\n"
    "- Mentions specific file paths, module names, or code identifiers (e.g., 'recall.py', 'judge_relevance')\n"
    "- Asks architecture/design questions ('how should we structure X', 'why did we choose Y')\n"
    "- Queries project state ('what's the current X', 'where is Y at')\n"
    "- Debugs in specific named code or systems\n"
    "- Names a specific concept, library, framework, or term unique to the project\n"
    "- Touches the user's LIFE domains where memory holds rich context: career direction, "
    "weekly scheduling/planning, family (Sa, Duyên), health/vaccines, finances, Upwork "
    "proposals/jobs, game-dev build (Chimera / The Ninth Bride). These are memory-HEAVY "
    "domains: prior decisions, preferences, and patterns exist for almost all of them.\n\n"
    "REJECT (no) when the prompt:\n"
    "- Is a trivial acknowledgment ('ok', 'thanks', 'got it')\n"
    "- Is conversational filler before next task ('alright let's continue')\n"
    "- Is a pure syntax lookup with no project context ('what's the syntax for async/await')\n"
    "- Asks a generic 'how do I X' question answerable from public knowledge alone\n"
    "- Is a code task that can be answered by reading the current open file\n"
    "- Mentions only common terms (variables, functions) without project-specific context\n\n"
    "DECISION HEURISTICS:\n"
    "- When uncertain between allow and reject, prefer ALLOW. Cost of false negative (lost "
    "context, worse reasoning) > cost of false positive (wasted tokens, mild distractor risk).\n"
    "- However, if the prompt is clearly a continuation phrase ('ok let me try that') with "
    "no anchor to specific past work, reject.\n"
    "- If the prompt mentions a proper noun or capitalized identifier, that's usually a "
    "strong signal to allow (project entity, file, concept).\n"
    "- Generic technical terms used in their dictionary meaning (e.g., 'database', 'function') "
    "without project anchor do not warrant injection.\n\n"
    "EDGE CASES:\n"
    "- Vietnamese-English mixed prompts: treat the same — judge on intent, not language.\n"
    "- Imperatives ('fix the bug', 'rename foo'): allow only if a specific named target is "
    "referenced; reject if vague.\n"
    "- Questions: allow if specific, reject if generic syntax/concept lookup.\n"
    "- Multi-sentence prompts: judge on the dominant intent.\n\n"
    "WORKED EXAMPLES:\n\n"
    "Prompt: 'ok let me try recall.py fix'\n"
    "Decision: yes — references specific file 'recall.py', indicates work continues on identified module\n\n"
    "Prompt: 'fix the typo in line 5'\n"
    "Decision: no — generic edit task, no project anchor, answerable from current open file\n\n"
    "Prompt: 'what's the syntax for async/await in Python'\n"
    "Decision: no — pure syntax lookup, public knowledge\n\n"
    "Prompt: 'why did we choose sqlite-vec over chromadb'\n"
    "Decision: yes — asks about a past architectural decision, names specific libraries\n\n"
    "Prompt: 'tiếp tục với cách đó nhé'\n"
    "Decision: no — pure conversational continuation, no anchor\n\n"
    "Prompt: 'the bug in parser.py is in line 42'\n"
    "Decision: yes — references specific file and location, project context useful\n\n"
    "Prompt: 'thanks that worked'\n"
    "Decision: no — pure acknowledgment\n\n"
    "Prompt: 'update database schema this morning'\n"
    "Decision: no — vague task with no specific anchor; 'database schema' is generic\n\n"
    "Prompt: 'check IronCradle GDD status'\n"
    "Decision: yes — names specific project entity and a specific document type\n\n"
    "Prompt: 'rename foo to bar everywhere'\n"
    "Decision: no — generic refactor, no project-specific context needed\n\n"
    "Prompt: 'how should we structure the judge layer error handling'\n"
    "Decision: yes — design question about a project-specific component\n\n"
    "Prompt: 'compare React and Vue for our use case'\n"
    "Decision: yes — strategic decision question with 'our use case' implying project context\n\n"
    "Prompt: 'ok continue but check the recall.py logic'\n"
    "Decision: yes — file reference plus contrastive 'but' marks substantive feedback\n\n"
    "Prompt: 'add a print statement at the top'\n"
    "Decision: no — trivial edit, no project context\n\n"
    "Prompt: 'verify the auth flow works after my changes'\n"
    "Decision: yes — references 'my changes' (past work) and a specific subsystem (auth flow)\n\n"
    "Prompt: 'remove the unused import'\n"
    "Decision: no — generic cleanup, no project context\n\n"
    "Prompt: 'làm sao để tích hợp Stripe webhook vào project hiện tại'\n"
    "Decision: yes — Vietnamese question that names specific service (Stripe) and 'project hiện tại'\n\n"
    "Prompt: 'mình đang phân vân về hướng đi career'\n"
    "Decision: yes — career direction is a memory-heavy life domain (prior decisions, roadmap, preferences)\n\n"
    "Prompt: 'lên lịch tuần này giúp mình'\n"
    "Decision: yes — scheduling pulls from stored commitments, family context, and work threads\n\n"
    "Prompt: 'viết proposal cho job Upwork về backend python'\n"
    "Decision: yes — Upwork proposals have stored style preferences and past patterns\n\n"
    "Prompt: 'hôm nay Sa tiêm vaccine gì'\n"
    "Decision: yes — family health question; vaccine history lives in memory\n\n"
    "REMEMBER: output exactly one token, either 'yes' or 'no'. Nothing else.\n\n"
    "Now output yes or no for this prompt."
)

# Contrast markers signal substantive content even after ack phrase
# (e.g., "ok continue but check abc", "tiếp tục nhưng sửa chỗ kia")
CONTRAST_MARKERS = {
    "but", "however", "though", "except", "actually", "wait",
    "nhưng", "tuy nhiên", "ngoại trừ", "thực ra", "khoan",
}

# Word count above which ack-prefix patterns DON'T trigger skip.
# Pure-ack continuations are typically 5-8 words ("ok let me try that approach").
# Anything longer likely contains substantive feedback/instructions.
SUBSTANTIVE_WORD_THRESHOLD = 8

# CONFIDENT patterns — 100% skip, no LLM consult needed.
# Slash commands invoke skills that load their own context. Bash escapes
# (!cmd) are shell pass-through, not user dialogue.
CONFIDENT_SKIP_PATTERNS = [
    (re.compile(r'^/[a-z][a-z0-9_-]*(\s|$)', re.I), "slash"),
    (re.compile(r'^!', re.I), "bash"),
]

# TENTATIVE patterns — heuristic guess only. LLM tiebreaker decides for
# real because these can fire on prompts like "ok let me try recall.py fix"
# where the ack prefix masks a real file-context need.
TENTATIVE_SKIP_PATTERNS = [
    # English continuations >4 words: "ok let me try that approach"
    (re.compile(r'^(ok|yes|sure|alright|right|got it|cool|nice|good|great)[,.]?\s+(let|let\'?s|just|then|now|go|please|do|make|try|run|continue|proceed)\b', re.I), "continuation_en"),
    # VN continuations >4 words: "ok tiếp tục với cách đó nhé", "ok làm theo cách đó nhé"
    (re.compile(r'^(ok|được|đúng|tiếp|làm|thử)\s+(rồi|đi|tiếp|nha|nhé|tục|theo|vậy|làm|thử|cứ|cách)\b', re.I), "continuation_vn"),
    # Pure imperative actions: "go ahead and proceed with it" "just do it now please"
    (re.compile(r'^(go ahead|just do|please do|now do|do that|làm đi|chạy đi)\b', re.I), "imperative"),
    # Pure thanks/closing >4 words: "thanks that worked perfectly now"
    (re.compile(r'^(thanks?|thank you|cảm ơn|cám ơn|tks)[,.\s]', re.I), "ack_thanks"),
]

# Backwards-compat alias for any external test referencing the old name
SKIP_PATTERNS = CONFIDENT_SKIP_PATTERNS + TENTATIVE_SKIP_PATTERNS


def llm_classify(prompt: str) -> str | None:
    """LLM tiebreaker via urllib (matches embed_prompt pattern).

    Returns 'skip' / 'include' / None (on error or no API key).
    Cost ~$0.00002/call, ~1.2s typical from VN host (2s hard timeout, default tier).
    """
    api_key = get_api_key()
    if not api_key:
        return None
    try:
        body = json.dumps({
            "model": LLM_CLASSIFIER_MODEL,
            "messages": [
                {"role": "system", "content": LLM_CLASSIFIER_SYSTEM},
                {"role": "user", "content": prompt[:500]},
            ],
            "temperature": 0,
            "seed": 42,
            "max_completion_tokens": 10,  # gpt-5.x outputs "Yes."/"No." ≈ 5 tokens
            # default tier (not flex): synchronous gate needs predictable latency;
            # cost delta ~$0.00001/call is noise at this volume.
        }).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        resp = urllib.request.urlopen(req, timeout=LLM_CLASSIFIER_TIMEOUT)
        data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"].strip().lower()
        if content.startswith("no"):
            return "skip"
        return "include"
    except Exception:
        return None


def _log_llm_tiebreak(
    decision: str, heuristic: str, prompt: str,
    elapsed_ms: int = -1, outcome: str = "ok",
) -> None:
    """Log LLM tiebreaker decision + latency for observability (skip/include/fail).

    Columns: ts, decision, heuristic=, outcome=, ms=, hash, preview.
    `outcome=fail` rows (API error/timeout) carry the latency tail we most
    need to see — log them too, not just successes.
    """
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        prompt_preview = prompt.strip().replace("\n", " ")[:60]
        with LLM_TIEBREAK_LOG.open("a") as f:
            f.write(
                f"{ts}\t{decision}\theuristic={heuristic}\toutcome={outcome}"
                f"\tms={elapsed_ms}\t{prompt_hash}\t{prompt_preview}\n"
            )
    except Exception:
        pass


def should_skip_brain(prompt: str) -> tuple[bool, str]:
    """Return (skip, reason). Hybrid Option 2: heuristic + LLM tiebreaker.

    Decision tree:
      1-5. Confident heuristics (too_short, too_long, trivial_short,
           substantive_length, contrast_marker) — never consult LLM.
      6. Ambiguous zone (5-8 words, no contrast): heuristic patterns + LLM
         tiebreaker. LLM wins on disagreement. LLM API failure → fall back
         to heuristic alone.

    Pattern matching is LAST among confident heuristics. Substantive-content
    signals (word count, contrast markers) all override patterns —
    "tiếp tục theo plan A nhưng chỉnh sửa abc" must INCLUDE despite starting
    with the "tiếp tục" continuation prefix.
    """
    stripped = prompt.strip()
    if len(stripped) < MIN_PROMPT_LENGTH:
        return True, "too_short"
    if len(stripped) > 5000:
        return False, "long_prompt"
    # Confident pattern skips — no LLM consult
    for pat, name in CONFIDENT_SKIP_PATTERNS:
        if pat.match(stripped):
            return True, f"confident:{name}"
    words = stripped.split()
    if len(words) <= 4 and "?" not in stripped:
        # Path/code tokens mark a real task, not an ack — 'fix bug trong
        # scripts/derive.sh' is 4 words but path-anchored (audit 2026-06-12).
        # Route those to the ambiguous zone instead of confidently skipping.
        has_code_token = any(
            "/" in w or "_" in w or "::" in w or "()" in w
            or ("." in w.strip(".,!") and not w.strip(".,!").replace(".", "").isdigit())
            for w in words
        )
        if not has_code_token:
            return True, "trivial_short"
    if len(words) > SUBSTANTIVE_WORD_THRESHOLD:
        return False, "substantive_length"
    lower = stripped.lower()
    for marker in CONTRAST_MARKERS:
        if f" {marker} " in f" {lower} " or lower.startswith(f"{marker} "):
            return False, f"contrast:{marker}"

    # ── Ambiguous zone (5-8 words, no contrast) ──
    # Heuristic provides first opinion via TENTATIVE patterns; LLM tiebreaks.
    heuristic_skip = False
    heuristic_name = "default_include"
    for pat, name in TENTATIVE_SKIP_PATTERNS:
        if pat.match(stripped):
            heuristic_skip = True
            heuristic_name = name
            break

    t0 = time.perf_counter()
    llm_decision = llm_classify(stripped)
    llm_ms = int((time.perf_counter() - t0) * 1000)

    if llm_decision is None:
        # API failed/timeout — trust heuristic alone. Log it: timeouts are
        # exactly the latency tail we need visibility into.
        _log_llm_tiebreak("fail", heuristic_name, prompt, llm_ms, outcome="fail")
        if heuristic_skip:
            return True, f"pattern:{heuristic_name}|llm_fail"
        return False, "default_include|llm_fail"

    # Log every LLM tiebreaker decision for analysis (with latency)
    _log_llm_tiebreak(llm_decision, heuristic_name, prompt, llm_ms, outcome="ok")

    # Both signals agree
    if heuristic_skip and llm_decision == "skip":
        return True, f"agree_skip:{heuristic_name}"
    if (not heuristic_skip) and llm_decision == "include":
        return False, "agree_include"

    # Disagreement — LLM wins (sees full context, not just prefix patterns)
    if heuristic_skip and llm_decision == "include":
        return False, f"llm_override_pattern:{heuristic_name}"
    if (not heuristic_skip) and llm_decision == "skip":
        return True, "llm_only_skip"

    return False, "include"  # defensive fallthrough


def _log_skip(reason: str, prompt: str) -> None:
    """Append skip event to /tmp/brain-skip.log for observability."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        prompt_preview = prompt.strip().replace("\n", " ")[:60]
        line = f"{ts}\t{reason}\t{prompt_hash}\t{prompt_preview}\n"
        with SKIP_LOG.open("a") as f:
            f.write(line)
    except Exception:
        pass  # observability never blocks the hook


def _log_judge(status: str, telemetry: dict, n_candidates: int) -> None:
    """Log hook-side judge outcome + latency.

    This path (memory-injection judging on every qualifying prompt) is the
    dominant judge-latency source yet is NOT captured by brain_meta telemetry,
    which only tracks the MCP brain_recall path. Columns: ts, status, ms=, cache=, n=.
    """
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ms = int(telemetry.get("latency_ms", 0))
        cache_hit = telemetry.get("cache_hit", False)
        with JUDGE_LOG.open("a") as f:
            f.write(f"{ts}\t{status}\tms={ms}\tcache={cache_hit}\tn={n_candidates}\n")
    except Exception:
        pass


def detect_project() -> str | None:
    """Detect project from cwd by walking up to ~/Projects."""
    cwd = Path.cwd()
    projects_dir = Path.home() / "Projects"
    try:
        return cwd.relative_to(projects_dir).parts[0]
    except (ValueError, IndexError):
        return None


def get_api_key() -> str | None:
    """Load OpenAI API key from env or brain's .env file."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    if BRAIN_ENV.exists():
        for line in BRAIN_ENV.read_text().strip().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line.startswith("OPENAI_API_KEY"):
                _, _, val = line.partition("=")
                return val.strip().strip('"').strip("'")
    return None


# ── Dedup ─────────────────────────────────────────────────────────────────

def _cache_path() -> Path:
    """Session-stable cache file path based on cwd."""
    cwd_hash = hashlib.md5(str(Path.cwd()).encode()).hexdigest()[:8]
    return CACHE_DIR / f"brain-prompt-ctx-{cwd_hash}.json"


def _extract_words(text: str) -> list[str]:
    """Extract unique words from text. No stop word filtering needed —
    embedding model handles semantic weighting, FTS5 BM25 handles term frequency.
    Only filters very short words (<3 chars) that are mostly particles/articles.
    """
    words = text.lower().split()
    seen = set()
    result = []
    for w in words:
        if len(w) >= MIN_WORD_LEN and w.isalnum() and w not in seen:
            seen.add(w)
            result.append(w)
    return result


def _load_cache() -> dict:
    """Load cache file (IDs + context keywords)."""
    path = _cache_path()
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("ts", 0) > CACHE_MAX_AGE:
            return {"ids": [], "keywords": []}
        return data
    except Exception:
        return {"ids": [], "keywords": []}


def load_injected_ids() -> set[str]:
    """Load previously injected memory IDs from cache."""
    return set(_load_cache().get("ids", []))


def load_context_keywords() -> list[str]:
    """Load accumulated keywords from recent prompts."""
    return _load_cache().get("keywords", [])


def load_injected_chars() -> int:
    """Load total injected chars from cache."""
    return _load_cache().get("total_chars", 0)


def load_last_tools() -> list[str]:
    """Load last injected tool names for skip-if-unchanged."""
    return _load_cache().get("last_tools", [])


def load_last_memory_ids() -> list[str]:
    """Load last injected general memory IDs for skip-if-unchanged."""
    return _load_cache().get("last_memory_ids", [])


def load_tool_chars() -> int:
    """Load total tool injected chars from cache."""
    return _load_cache().get("tool_chars", 0)


def load_suggested_tools() -> set[str]:
    """Session-level set of tool names already suggested (once per session —
    the same list was re-suggested up to 27x/session, audit 2026-06-12)."""
    return set(_load_cache().get("suggested_tools", []))


def _flatten_clip(text: str, limit: int = 200) -> str:
    """One line, word-boundary clip — raw multi-line tool bodies rendered
    nested markdown bullets as phantom sibling tools (audit 2026-06-12)."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat.rfind(" ", 0, limit)
    if cut < limit // 2:
        cut = limit
    return flat[:cut] + "…"


def _age_suffix(date_str: str | None) -> str:
    """' (Nd ago)' for memories 2+ days old — a 68-day-old 'weekend plan'
    injected dateless reads as current state (audit 2026-06-12)."""
    if not date_str:
        return ""
    try:
        age_days = (datetime.now() - datetime.fromisoformat(date_str)).days
        if age_days >= 2:
            return f" ({age_days}d ago)"
    except Exception:
        pass
    return ""


def save_cache(
    new_ids: set[str],
    current_prompt: str,
    new_chars: int = 0,
    tool_names: list[str] | None = None,
    new_tool_chars: int = 0,
    memory_ids: list[str] | None = None,
) -> None:
    """Save injected IDs + keywords + memory chars + tool state + last memory IDs."""
    path = _cache_path()
    try:
        cache = _load_cache()
        # Merge IDs
        all_ids = set(cache.get("ids", [])) | new_ids
        if len(all_ids) > CACHE_MAX_IDS:
            all_ids = set(list(all_ids)[-CACHE_MAX_IDS:])
        # Accumulate total injected chars (memories only)
        total_chars = cache.get("total_chars", 0) + new_chars
        # Tool state
        last_tools = tool_names if tool_names is not None else cache.get("last_tools", [])
        tool_chars = cache.get("tool_chars", 0) + new_tool_chars
        # Session-level suggested-tools set (once per session)
        suggested = cache.get("suggested_tools", [])
        for name in (tool_names or []):
            if name not in suggested:
                suggested.append(name)
        suggested = suggested[-MAX_SUGGESTED_TOOLS:]
        # General memory IDs for skip-if-unchanged
        last_memory_ids = memory_ids if memory_ids is not None else cache.get("last_memory_ids", [])
        # Extract and accumulate keywords (deduped, capped)
        existing_kw = cache.get("keywords", [])
        new_kw = _extract_words(current_prompt)
        # Merge: existing + new, deduplicate, keep most recent up to cap
        seen = set()
        merged = []
        for kw in existing_kw + new_kw:
            if kw not in seen:
                seen.add(kw)
                merged.append(kw)
        merged = merged[-CACHE_MAX_KEYWORDS:]  # keep most recent
        path.write_text(json.dumps({
            "ids": list(all_ids),
            "keywords": merged,
            "total_chars": total_chars,
            "last_tools": last_tools,
            "tool_chars": tool_chars,
            "suggested_tools": suggested,
            "last_memory_ids": last_memory_ids,
            "ts": time.time(),
        }))
    except Exception:
        pass


# ── Embedding ─────────────────────────────────────────────────────────────

def build_combined_query(current: str, context_keywords: list[str]) -> str:
    """Combine current prompt with accumulated keywords from recent prompts.

    Current prompt: full text (intent + detail).
    Context keywords: distilled signal from recent turns (no filler, no truncation loss).
    """
    query = current[:CURRENT_PROMPT_MAX_CHARS]
    if context_keywords:
        query += " " + " ".join(context_keywords)
    return query


def embed_prompt(text: str, api_key: str) -> list[float] | None:
    """Embed text via OpenAI API using urllib (no external deps beyond stdlib)."""
    try:
        body = json.dumps(
            {"input": text[:2000], "model": EMBED_MODEL, "dimensions": EMBED_DIMS}
        ).encode()
        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        resp = urllib.request.urlopen(req, timeout=EMBED_TIMEOUT)
        return json.loads(resp.read())["data"][0]["embedding"]
    except Exception:
        return None


# ── Database ──────────────────────────────────────────────────────────────

def connect_db(need_vec: bool = False) -> sqlite3.Connection | None:
    """Connect to brain.db, optionally loading sqlite-vec extension."""
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        if need_vec and HAS_VEC:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _bump_injected_access(conn: sqlite3.Connection, ids: list[str]) -> None:
    """Injection telemetry (audit 2026-06-12): hook injection is the brain's
    main consumption path but never marked memories as accessed, making
    access_count unusable for measuring utility. Bump on actual injection
    only (skip-if-unchanged prompts don't re-bump)."""
    if not ids:
        return
    try:
        conn.executemany(
            """UPDATE memories
               SET access_count = access_count + 1,
                   last_accessed = datetime('now')
               WHERE id = ?""",
            [(i,) for i in ids],
        )
        conn.commit()
    except Exception:
        pass


# ── Phase 1: General memories (hybrid FTS5 + vector RRF) ─────────────────

def _fts_search(
    conn: sqlite3.Connection, prompt: str, project: str | None
) -> list[dict]:
    """FTS5 keyword search for general memories with project scoping."""
    # Content words from the whole prompt (capped) — the old prompt[:100] +
    # first-5-words cut Vietnamese prompts down to function words and produced
    # keyword-bait matches like 'intro' -> Upwork-intro (audit 2026-06-12)
    words = prompt[:CURRENT_PROMPT_MAX_CHARS].split()
    words = [w.strip(",.!?;:'\"()[]{}") for w in words]
    query_words = [w for w in words if len(w) > 2 and w.isalnum()]
    if not query_words:
        return []

    fts_query = " OR ".join(query_words[:8])
    try:
        rows = conn.execute(
            """SELECT m.id, m.content, m.type, m.created_at, m.importance, rank
               FROM memory_fts f
               JOIN memories m ON m.id = f.memory_id
               WHERE memory_fts MATCH ?
                 AND m.type NOT IN ('tool', 'session')
                 AND COALESCE(m.importance, 0.5) >= 0.3
                 AND (m.project = ? OR m.project IS NULL)
               ORDER BY rank
               LIMIT 20""",
            (fts_query, project),
        ).fetchall()
        return [
            {"id": r["id"], "content": r["content"], "type": r["type"],
             "created_at": r["created_at"], "importance": r["importance"] or 0.5,
             "fts_rank": i}
            for i, r in enumerate(rows)
        ]
    except Exception:
        return []


def _vec_search_general(
    conn: sqlite3.Connection, embedding: list[float], project: str | None
) -> list[dict]:
    """Vector similarity search for general memories with project scoping."""
    emb_bytes = struct.pack(f"{len(embedding)}f", *embedding)
    try:
        rows = conn.execute(
            """WITH vec_results AS (
                SELECT memory_id, distance
                FROM memory_vectors
                WHERE embedding MATCH :embedding
                  AND k = :fetch_k
            )
            SELECT m.id, m.content, m.type, m.created_at, m.importance, v.distance
            FROM vec_results v
            JOIN memories m ON m.id = v.memory_id
            WHERE m.type NOT IN ('tool', 'session')
              AND COALESCE(m.importance, 0.5) >= 0.3
              AND (m.project = :project OR m.project IS NULL)
            ORDER BY v.distance
            LIMIT 20""",
            {"embedding": emb_bytes, "fetch_k": VEC_FETCH_K, "project": project},
        ).fetchall()
        return [
            {"id": r["id"], "content": r["content"], "type": r["type"],
             "created_at": r["created_at"], "importance": r["importance"] or 0.5,
             "vec_rank": i}
            for i, r in enumerate(rows)
        ]
    except Exception:
        return []


def search_general_hybrid(
    conn: sqlite3.Connection,
    prompt: str,
    embedding: list[float] | None,
    project: str | None,
) -> list[dict]:
    """Hybrid search with RRF fusion + type weighting. Returns results with IDs."""
    fts_results = _fts_search(conn, prompt, project)
    today_str = date.today().isoformat()

    if embedding is None:
        for r in fts_results:
            r["score"] = 1.0 / (RRF_K + r["fts_rank"])
            imp = r.get("importance", 0.5)
            r["score"] *= (0.7 + 0.3 * imp)
            r["score"] -= TYPE_PRIORITY.get(r["type"], 2) * 0.001
            if r.get("created_at", "")[:10] == today_str:
                r["score"] += 0.005
        fts_results.sort(key=lambda x: (-x["score"], -x.get("importance", 0.5)))
        return [
            {"id": r["id"], "content": r["content"][:MAX_CONTENT_LEN], "type": r["type"],
             "importance": r.get("importance", 0.5)}
            for r in fts_results[:FETCH_K_GENERAL]
        ]

    vec_results = _vec_search_general(conn, embedding, project)

    scores: dict[str, dict] = {}

    for r in fts_results:
        mid = r["id"]
        scores[mid] = {
            "id": mid,
            "content": r["content"],
            "type": r["type"],
            "created_at": r.get("created_at", ""),
            "importance": r.get("importance", 0.5),
            "score": 1.0 / (RRF_K + r["fts_rank"]),
        }

    for r in vec_results:
        mid = r["id"]
        vec_score = 1.0 / (RRF_K + r["vec_rank"])
        if mid in scores:
            scores[mid]["score"] += vec_score
        else:
            scores[mid] = {
                "id": mid,
                "content": r["content"],
                "type": r["type"],
                "created_at": r.get("created_at", ""),
                "importance": r.get("importance", 0.5),
                "score": vec_score,
            }

    for entry in scores.values():
        # Importance-weighted RRF: mild multiplier (0.7 at imp=0, 1.0 at imp=1)
        imp = entry.get("importance", 0.5)
        entry["score"] *= (0.7 + 0.3 * imp)
        entry["score"] -= TYPE_PRIORITY.get(entry["type"], 2) * 0.001
        # Same-day recency boost: today's memories are more likely relevant
        if entry.get("created_at", "")[:10] == today_str:
            entry["score"] += 0.005

    ranked = sorted(scores.values(), key=lambda x: (-x["score"], -x.get("importance", 0.5)))
    return [
        {"id": r["id"], "content": r["content"][:MAX_CONTENT_LEN], "type": r["type"],
         "importance": r.get("importance", 0.5), "created_at": r.get("created_at", "")}
        for r in ranked[:FETCH_K_GENERAL]
    ]


# ── Phase 2: Tool search (vector only) ───────────────────────────────────

def search_tools_vector(
    conn: sqlite3.Connection, embedding: list[float], project: str | None = None
) -> list[dict]:
    """Vector similarity search for tool memories (Semantic Toolbox).

    Oversamples the KNN heavily (TOOL_VEC_FETCH_K) because sqlite-vec cannot
    pre-filter by type and tool vectors are ~7% of the table, then applies a
    cosine relevance floor — suggesting nothing beats suggesting noise
    (measured 91% never-followed suggestions, audit 2026-06-12).
    """
    emb_bytes = struct.pack(f"{len(embedding)}f", *embedding)
    project_filter = "AND (m.project = :project OR m.project IS NULL)" if project else ""
    try:
        rows = conn.execute(
            f"""WITH vec_results AS (
                SELECT memory_id, distance
                FROM memory_vectors
                WHERE embedding MATCH :embedding
                  AND k = :fetch_k
            )
            SELECT m.id, m.content, m.metadata, v.distance
            FROM vec_results v
            JOIN memories m ON m.id = v.memory_id
            WHERE m.type = 'tool'
            {project_filter}
            ORDER BY v.distance
            LIMIT :limit""",
            {"embedding": emb_bytes, "fetch_k": TOOL_VEC_FETCH_K, "limit": FETCH_K_TOOLS, "project": project},
        ).fetchall()

        results = []
        for r in rows:
            # Normalized embeddings: cosine = 1 - L2distance^2 / 2
            cosine = 1.0 - (r["distance"] ** 2) / 2.0
            if cosine < TOOL_MIN_COSINE:
                continue
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
            results.append({
                "id": r["id"],
                "name": meta.get("name", "unknown"),
                "content": r["content"],
                "cosine": round(cosine, 3),
            })
        return results
    except Exception:
        return []


def _fts5_tool_search(
    conn: sqlite3.Connection, query: str, limit: int = 3, project: str | None = None
) -> list[dict]:
    """Fast FTS5 search for tools. Returns [] if no good matches or on error.

    Used as a pre-filter before the embedding API call — if FTS5 returns
    enough results (>= limit), the caller skips the vector search entirely,
    saving ~$0.001 per prompt and ~300ms of latency.
    """
    # Sanitize query for FTS5 (remove special chars that break MATCH syntax)
    safe_query = re.sub(r'[^\w\s]', ' ', query)
    # Content words from the WHOLE prompt — the old first-5-raw-words query
    # matched on function words and the word 'save' alone (audit 2026-06-12)
    words = [w for w in safe_query.split() if len(w) >= MIN_WORD_LEN]
    if not words:
        return []

    fts_query = " OR ".join(words[:8])

    project_filter = "AND (m.project = ? OR m.project IS NULL)" if project else ""
    params = [fts_query] + ([project] if project else []) + [limit]

    try:
        rows = conn.execute(
            f"""SELECT m.id, m.content, m.metadata, rank
               FROM memory_fts
               JOIN memories m ON m.id = memory_fts.memory_id
               WHERE memory_fts MATCH ?
                 AND m.type = 'tool'
                 {project_filter}
               ORDER BY rank
               LIMIT ?""",
            params,
        ).fetchall()

        results = []
        for r in rows:
            meta = json.loads(r["metadata"]) if r["metadata"] else {}
            results.append({
                "id": r["id"],
                "name": meta.get("name", "unknown"),
                "content": r["content"],
            })
        return results
    except Exception:
        return []  # FTS5 failure (syntax error, etc.) → fall back to vector


# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    prompt = get_prompt()
    if not prompt:
        sys.exit(0)

    # Path C: unified skip gate (consolidates length/slash/trivial-short checks
    # + adds continuation/imperative patterns). Logs skip reason for observability.
    skip, reason = should_skip_brain(prompt)
    if skip:
        _log_skip(reason, prompt)
        sys.exit(0)

    stripped = prompt.strip()
    # Normalize Vietnamese Telex leaks before search + embedding
    normalized = _normalize_vn(stripped)

    project = detect_project()
    injected = load_injected_ids()
    context_kw = load_context_keywords()
    budget_used = load_injected_chars()
    budget_remaining = max(0, MAX_INJECTED_CHARS - budget_used)
    sections = []
    new_ids: set[str] = set()
    new_chars = 0

    # Build combined query from normalized prompt + accumulated keywords
    combined = build_combined_query(normalized, context_kw)

    # Expand query when emotional/personal signals detected
    if detect_emotional_signals(normalized):
        combined += " " + EMOTIONAL_EXPANSION

    # Embed once — reuse for both phases
    embedding = None
    if HAS_VEC:
        api_key = get_api_key()
        if api_key:
            embedding = embed_prompt(combined, api_key)

    conn = connect_db(need_vec=(embedding is not None))
    memory_ids_to_save = None
    if conn and budget_remaining > 0:
        # Phase 1: General memories — over-fetch, dedup, judge, top-K, token cap
        general = search_general_hybrid(conn, combined, embedding, project)
        new_general = [r for r in general if r["id"] not in injected]
        if _HAS_DEDUP and len(new_general) > 1:
            try:
                new_general = _dedup_pool(conn, new_general)
            except Exception:
                pass
        # Output gate: LLM judge filters by intent before top-K slice. Shares
        # JUDGE_ENABLED env toggle with Path A. Soft-fails to RRF order on error.
        # Runs for small pools too (>= 2): irrelevant items used to survive
        # whenever the pool fit inside MAX_GENERAL_RESULTS (audit 2026-06-12);
        # JUDGE_MIN_CANDIDATES still gates the tiniest pools internally.
        if _HAS_JUDGE and len(new_general) >= 2:
            try:
                _n_cand = len(new_general)
                judged, _judge_status, _judge_tele = _judge_relevance(
                    combined, new_general, n=MAX_GENERAL_RESULTS
                )
                new_general = judged
                _log_judge(_judge_status, _judge_tele, _n_cand)
            except Exception:
                pass  # keep RRF order on any unexpected error
        new_general = new_general[:MAX_GENERAL_RESULTS]  # top-K after dedup+judge
        # Apply token cap
        capped_general = []
        capped_chars = 0
        for r in new_general:
            entry_len = len(r["content"]) + len(r["type"]) + 10  # overhead
            if capped_chars + entry_len > budget_remaining:
                break
            capped_general.append(r)
            capped_chars += entry_len

        # Skip-if-unchanged: avoid re-injecting same memories on consecutive prompts
        # Only skip after at least one previous injection (total_chars > 0) and
        # when the cache has a non-empty last_memory_ids (not the first prompt).
        prev_memory_ids = load_last_memory_ids()
        current_memory_ids = [r["id"] for r in capped_general]
        if current_memory_ids and current_memory_ids == prev_memory_ids and budget_used > 0:
            # Same memories as last prompt — skip injection, preserve existing context
            pass
        elif capped_general:
            lines = [
                f"- [{r['type']}] {r['content']}{_age_suffix(r.get('created_at'))}"
                for r in capped_general
            ]
            sections.append("Brain context:\n" + "\n".join(lines))
            new_ids.update(r["id"] for r in capped_general)
            new_chars += capped_chars
            memory_ids_to_save = current_memory_ids
            _bump_injected_access(conn, current_memory_ids)

        # Phase 2: Semantic Toolbox — vector PRIMARY when the embedding exists
        # (it is already computed for Phase 1, so the old FTS-first "savings"
        # were imaginary while junk FTS hits suppressed the semantic path —
        # measured 91% never-followed suggestions, audit 2026-06-12). FTS is
        # the no-embedding fallback only. Each tool suggested once per session.
        tool_names_to_save = None
        new_tool_chars = 0
        prev_tools = load_last_tools()
        already_suggested = load_suggested_tools()
        tool_budget_used = load_tool_chars()

        if embedding is not None:
            tools = search_tools_vector(conn, embedding, project=project)
        else:
            tools = _fts5_tool_search(conn, normalized, limit=MAX_TOOL_RESULTS, project=project)

        tools = [t for t in tools if t["name"] not in already_suggested][:MAX_TOOL_RESULTS]
        current_tool_names = [t["name"] for t in tools]
        # Skip if same tools as last prompt (avoid redundant system-reminders)
        if current_tool_names != prev_tools and tools:
            tool_text = "\n".join(f"- {t['name']}: {_flatten_clip(t['content'])}" for t in tools)
            new_tool_chars = len(tool_text)
            if tool_budget_used + new_tool_chars <= MAX_TOOL_INJECTED_CHARS:
                sections.append("Relevant tools:\n" + tool_text)
                # Toolbox telemetry — same blind spot as memories pre-audit
                _bump_injected_access(conn, [t["id"] for t in tools if t.get("id")])
        tool_names_to_save = current_tool_names

        conn.close()

    # Save IDs + normalized prompt + chars + tool state + memory IDs to cache
    save_cache(new_ids, normalized, new_chars, tool_names_to_save, new_tool_chars, memory_ids_to_save)

    if not sections:
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n\n".join(sections),
        }
    }
    print(json.dumps(output))
