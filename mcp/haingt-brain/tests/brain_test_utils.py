"""Shared test helpers for haingt-brain (in-memory DB + deterministic embeddings).

Mirrors the harness in test_consolidation_p1_p4.py so new test files don't duplicate it.
"""

import json
import math
import struct
import sqlite3

VECTOR_DIM = 3072


def create_test_db() -> sqlite3.Connection:
    """In-memory brain DB with full schema including sqlite-vec + FTS."""
    import sqlite_vec

    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
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
    """)

    conn.execute(f"""
        CREATE VIRTUAL TABLE memory_vectors USING vec0(
            memory_id TEXT PRIMARY KEY,
            embedding FLOAT[{VECTOR_DIM}]
        )
    """)

    try:
        conn.execute("""
            CREATE VIRTUAL TABLE memory_fts USING fts5(
                content, tags, project, memory_id UNINDEXED,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
    except sqlite3.OperationalError:
        pass

    conn.commit()
    return conn


def make_embedding(seed: int) -> list[float]:
    """Deterministic L2-normalized embedding. Same seed → cosine 1.0; different → ~0."""
    import random
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(VECTOR_DIM)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


def blend_embedding(seed_a: int, seed_b: int, w: float) -> list[float]:
    """Blend two seed-embeddings: w*a + (1-w)*b, L2-normalized.

    Lets a test land a controlled cosine in the 0.80-0.985 conflict band
    (w near 1.0 → high sim to a; w near 0.5 → mid).
    """
    a = make_embedding(seed_a)
    b = make_embedding(seed_b)
    vec = [w * x + (1 - w) * y for x, y in zip(a, b)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def serialize(embedding: list[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)


def insert_memory(
    conn: sqlite3.Connection,
    mem_id: str,
    content: str,
    mem_type: str = "decision",
    embedding: list[float] | None = None,
    embedding_seed: int | None = None,
    source: str | None = None,
    project: str | None = None,
    created_days_ago: int = 0,
    importance: float | None = None,
) -> None:
    """Insert a memory + its embedding + FTS row. Pass either embedding or embedding_seed."""
    from haingt_brain.importance import compute_initial_importance

    if importance is None:
        importance = compute_initial_importance(mem_type, source)
    metadata = json.dumps({"source": source}) if source else "{}"
    tags = json.dumps(["auto-captured"] if source and "hook" in source else [])

    conn.execute(
        """INSERT INTO memories (id, content, type, tags, project, metadata, importance, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', ?))""",
        (mem_id, content, mem_type, tags, project, metadata, importance,
         f"-{created_days_ago} days"),
    )
    if embedding is None:
        embedding = make_embedding(embedding_seed if embedding_seed is not None else 0)
    conn.execute(
        "INSERT INTO memory_vectors (memory_id, embedding) VALUES (?, ?)",
        (mem_id, serialize(embedding)),
    )
    conn.execute(
        "INSERT INTO memory_fts (memory_id, content, tags, project) VALUES (?, ?, ?, ?)",
        (mem_id, content, tags, project or ""),
    )
    conn.commit()
