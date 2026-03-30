"""SQLite database with sqlite-vec vector search and FTS5 full-text search."""

import json
import sqlite3
from pathlib import Path

import sqlite_vec

# Default DB location: ~/.local/share/haingt-brain/brain.db
DEFAULT_DB_DIR = Path.home() / ".local" / "share" / "haingt-brain"
VECTOR_DIMENSIONS = 3072


def get_db_path() -> Path:
    db_dir = DEFAULT_DB_DIR
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "brain.db"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Create a connection with sqlite-vec loaded."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript("""
        -- Core memories table
        CREATE TABLE IF NOT EXISTS memories (
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

        -- Knowledge graph edges
        CREATE TABLE IF NOT EXISTS relations (
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL CHECK(relation_type IN (
                'causes', 'fixes', 'contradicts', 'relates_to',
                'used_in', 'part_of', 'supersedes'
            )),
            weight REAL DEFAULT 1.0,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (source_id, target_id, relation_type),
            FOREIGN KEY (source_id) REFERENCES memories(id) ON DELETE CASCADE,
            FOREIGN KEY (target_id) REFERENCES memories(id) ON DELETE CASCADE
        );

        -- Session tracking
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            project TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            ended_at TEXT,
            summary TEXT,
            memory_ids TEXT DEFAULT '[]'
        );

        -- Key-value store for system metadata (consolidation timestamps, etc.)
        CREATE TABLE IF NOT EXISTS brain_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        -- Indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
        CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
        CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
        CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
        CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
    """)

    # Vector table (sqlite-vec) — separate because it uses special syntax
    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
            memory_id TEXT PRIMARY KEY,
            embedding FLOAT[{VECTOR_DIMENSIONS}]
        )
    """)

    # FTS5 full-text search with unicode61 tokenizer + aggressive diacritic removal
    # remove_diacritics=2 handles Vietnamese compound diacritics (ắ→a, ối→oi, ưu→uu)
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                content, tags, project, memory_id UNINDEXED,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
    except sqlite3.OperationalError:
        pass  # Already exists

    conn.commit()

    # Migration: add importance column if missing (existing databases)
    try:
        conn.execute("ALTER TABLE memories ADD COLUMN importance REAL DEFAULT 0.5")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Backfill importance for existing memories
    # Triggers when: memories with default 0.5 that have access history OR source metadata
    needs_backfill = conn.execute(
        """SELECT COUNT(*) FROM memories
           WHERE importance = 0.5
             AND (access_count > 0 OR json_extract(metadata, '$.source') IS NOT NULL)"""
    ).fetchone()[0]
    if needs_backfill:
        _backfill_importance(conn)


def serialize_embedding(embedding: list[float]) -> bytes:
    """Convert float list to bytes for sqlite-vec."""
    import struct
    return struct.pack(f"{len(embedding)}f", *embedding)


def _backfill_importance(conn: sqlite3.Connection) -> None:
    """Backfill: set importance from type + source + access_count for existing memories."""
    from .importance import compute_access_boost, compute_initial_importance

    rows = conn.execute(
        """SELECT id, type, access_count, metadata FROM memories
           WHERE importance = 0.5
             AND (access_count > 0 OR json_extract(metadata, '$.source') IS NOT NULL)"""
    ).fetchall()
    for row in rows:
        source = None
        try:
            meta = json.loads(row["metadata"]) if row["metadata"] else {}
            source = meta.get("source")
        except Exception:
            pass
        base = compute_initial_importance(row["type"], source)
        importance = compute_access_boost(base, row["access_count"])
        conn.execute("UPDATE memories SET importance = ? WHERE id = ?", (importance, row["id"]))
    conn.commit()
