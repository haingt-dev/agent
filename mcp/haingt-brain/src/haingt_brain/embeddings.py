"""OpenAI embedding API wrapper for text-embedding-3-large with LRU cache."""

import os
from collections import OrderedDict
from pathlib import Path

from openai import OpenAI

_client: OpenAI | None = None
MODEL = "text-embedding-3-large"
DIMENSIONS = 3072

# LRU cache for embeddings — avoids redundant API calls within a session
_CACHE_MAX = 128
_embed_cache: OrderedDict[str, list[float]] = OrderedDict()

# Load .env from project root if OPENAI_API_KEY not already set
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


def _load_env() -> None:
    """Load .env file manually (no extra dependency needed)."""
    if os.environ.get("OPENAI_API_KEY"):
        return
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().strip().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _load_env()
        _client = OpenAI()
    return _client


def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a 3072-dim float vector. Cached per session."""
    if text in _embed_cache:
        _embed_cache.move_to_end(text)
        return _embed_cache[text]

    resp = _get_client().embeddings.create(input=text, model=MODEL, dimensions=DIMENSIONS)
    embedding = resp.data[0].embedding

    _embed_cache[text] = embedding
    if len(_embed_cache) > _CACHE_MAX:
        _embed_cache.popitem(last=False)

    return embedding


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in one API call (max 2048 per batch). Results cached."""
    if not texts:
        return []

    # Split into cached vs uncached
    results: dict[int, list[float]] = {}
    uncached: list[tuple[int, str]] = []
    for i, text in enumerate(texts):
        if text in _embed_cache:
            _embed_cache.move_to_end(text)
            results[i] = _embed_cache[text]
        else:
            uncached.append((i, text))

    if uncached:
        uncached_texts = [t for _, t in uncached]
        resp = _get_client().embeddings.create(input=uncached_texts, model=MODEL, dimensions=DIMENSIONS)
        for item in sorted(resp.data, key=lambda x: x.index):
            orig_idx, orig_text = uncached[item.index]
            results[orig_idx] = item.embedding
            _embed_cache[orig_text] = item.embedding
            if len(_embed_cache) > _CACHE_MAX:
                _embed_cache.popitem(last=False)

    return [results[i] for i in range(len(texts))]
