"""Eine SQLite-Datenbank für das Digitale Gehirn.

* Schema-Version in ``schema_version``; Migrationen laufen beim Öffnen automatisch.
* Volltextsuche über FTS5 (falls die SQLite-Version es nicht kann: LIKE-Suche).
* Sicherung/Wiederherstellung über die SQLite-Backup-API (konsistent im laufenden Betrieb).
"""

from __future__ import annotations

import logging
import re
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

log = logging.getLogger("cudi.brain.db")

SCHEMA_VERSION = 1

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    subject TEXT,
    category TEXT NOT NULL DEFAULT 'fact',
    status TEXT NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed', 'tentative', 'outdated')),
    confidence REAL NOT NULL DEFAULT 1.0,
    source TEXT NOT NULL,
    project_id INTEGER,
    content_hash TEXT NOT NULL,
    replaced_by INTEGER,
    use_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_memories_subject ON memories(subject);
CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    started_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    meta TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    purpose TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'aktiv',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    kind TEXT NOT NULL CHECK (kind IN ('goal', 'requirement', 'decision', 'issue',
        'solution', 'next_step', 'note', 'insight', 'file', 'status')),
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offen',
    source TEXT NOT NULL DEFAULT 'nutzer',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_project ON project_entries(project_id, kind);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offen'
        CHECK (status IN ('offen', 'in_arbeit', 'erledigt', 'fehlgeschlagen')),
    project_id INTEGER REFERENCES projects(id),
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    size INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    location TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id, ordinal);

CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    data TEXT,
    ok INTEGER,
    signature TEXT,
    project_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodes_sig ON episodes(signature);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    model TEXT,
    ok INTEGER NOT NULL,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

_FTS_V1 = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, subject, content='memories', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, subject) VALUES (new.id, new.content, new.subject);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, subject)
        VALUES ('delete', old.id, old.content, old.subject);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE OF content, subject ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, subject)
        VALUES ('delete', old.id, old.content, old.subject);
    INSERT INTO memories_fts(rowid, content, subject) VALUES (new.id, new.content, new.subject);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
"""

# Häufige Wörter, die bei der Suche ignoriert werden (DE/EN)
STOPWORDS = set("""
der die das den dem des ein eine einer eines einem einen und oder aber wie was wer wo
wann warum ist sind war waren bin bist sein hat habe haben hast ich du er sie es wir ihr
mir mich dir dich uns euch mein meine meinen meinem meiner dein deine kannst kann können
nicht kein keine auf aus bei mit nach von vor zu zum zur für über unter im in an am als
auch noch nur schon sehr so dass ob wenn dann denn doch mal bitte welche welcher welches
lautet heißt gibt steht this that the a an and or is are was were be to of in on for with
what who where when why how my your me you it do does can could please about
""".split())


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def search_terms(text: str, limit: int = 8) -> List[str]:
    words = re.findall(r"[\wäöüÄÖÜß\-]{3,}", text.lower())
    terms: List[str] = []
    for w in words:
        w = w.strip("-")
        if len(w) >= 3 and w not in STOPWORDS and w not in terms:
            terms.append(w)
    return terms[:limit]


def fts_query(text: str) -> Optional[str]:
    terms = search_terms(text)
    if not terms:
        return None
    return " OR ".join('"' + t.replace('"', "") + '"*' for t in terms)


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = self._connect(self.path)
        self.fts_enabled = False
        self._migrate()

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    # ------------------------------------------------------------------ Schema
    def _migrate(self) -> None:
        with self.lock:
            self.conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            row = self.conn.execute("SELECT version FROM schema_version").fetchone()
            current = row["version"] if row else 0
            if current > SCHEMA_VERSION:
                raise RuntimeError(
                    f"Datenbank {self.path} hat Schema-Version {current}, dieses Programm kennt nur "
                    f"{SCHEMA_VERSION}. Bitte CUDI aktualisieren."
                )
            if current < 1:
                self.conn.executescript(_SCHEMA_V1)
            try:
                self.conn.executescript(_FTS_V1)
                self.fts_enabled = True
            except sqlite3.OperationalError as e:
                log.warning("FTS5 nicht verfügbar, Suche nutzt LIKE: %s", e)
            if current < SCHEMA_VERSION:
                self.conn.execute("DELETE FROM schema_version")
                self.conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
                log.info("Datenbankschema auf Version %d gebracht", SCHEMA_VERSION)
            self.conn.commit()

    @property
    def schema_version(self) -> int:
        row = self.query_one("SELECT version FROM schema_version")
        return row["version"] if row else 0

    # --------------------------------------------------------------- Zugriffe
    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def execute(self, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
        with self.transaction() as conn:
            return conn.execute(sql, tuple(params))

    def query(self, sql: str, params: Iterable = ()) -> List[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, tuple(params)).fetchall()

    def query_one(self, sql: str, params: Iterable = ()) -> Optional[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, tuple(params)).fetchone()

    def get_state(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.query_one("SELECT value FROM state WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_state(self, key: str, value: Optional[str]) -> None:
        if value is None:
            self.execute("DELETE FROM state WHERE key = ?", (key,))
        else:
            self.execute(
                "INSERT INTO state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def integrity_ok(self) -> bool:
        row = self.query_one("PRAGMA integrity_check")
        return bool(row) and row[0] == "ok"

    # ---------------------------------------------------- Sicherung/Restore
    def backup(self, backup_dir: Path, keep: int = 10, label: str = "") -> Path:
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = backup_dir / f"cudi_brain_{stamp}{('_' + label) if label else ''}.db"
        with self.lock:
            dest = sqlite3.connect(str(target))
            try:
                self.conn.backup(dest)
            finally:
                dest.close()
        self._prune_backups(backup_dir, keep)
        log.info("Sicherung erstellt: %s", target)
        return target

    @staticmethod
    def _prune_backups(backup_dir: Path, keep: int) -> None:
        backups = sorted(backup_dir.glob("cudi_brain_*.db"))
        for old in backups[:-keep] if keep > 0 else []:
            try:
                old.unlink()
            except OSError:  # pragma: no cover
                pass

    def restore(self, backup_file: Path, backup_dir: Path) -> Path:
        """Stellt eine Sicherung wieder her. Vorher wird der aktuelle Stand gesichert."""
        backup_file = Path(backup_file)
        check = sqlite3.connect(f"file:{backup_file}?mode=ro", uri=True)
        try:
            ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            has_schema = check.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'schema_version'"
            ).fetchone()
        finally:
            check.close()
        if not ok or not has_schema:
            raise ValueError(f"{backup_file.name} ist keine gültige CUDI-Sicherung")
        safety = self.backup(backup_dir, keep=10_000, label="vor_wiederherstellung")
        with self.lock:
            src = sqlite3.connect(str(backup_file))
            try:
                src.backup(self.conn)
            finally:
                src.close()
            self._migrate()
        return safety

    def close(self) -> None:
        with self.lock:
            self.conn.close()


def copy_file_backup(path: Path, backup_dir: Path) -> Path:
    """Sicherungskopie einer Datei vor dem Überschreiben."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"{stamp}_{path.name}"
    shutil.copy2(path, target)
    return target
