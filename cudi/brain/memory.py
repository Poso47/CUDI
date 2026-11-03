"""Langzeitgedächtnis des Digitalen Gehirns.

Regeln (siehe docs/decisions.md D-006):
* Dauerhaft gespeichert wird nur, was der Nutzer speichern lässt oder bestätigt.
* Jede Erinnerung hat Quelle, Zeitstempel, Status und Vertrauen.
* Gleicher Inhalt wird nicht doppelt gespeichert (Deduplizierung).
* Widerspricht eine neue Angabe einer bestätigten Erinnerung zum selben Thema,
  wird nicht überschrieben, sondern ein Konflikt gemeldet.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional

from .database import Database, fts_query, now_iso, search_terms

STATUS_LABELS = {"confirmed": "bestätigt", "tentative": "vorläufig", "outdated": "veraltet"}
CATEGORIES = ("fact", "preference", "goal", "profile", "knowledge", "procedure", "insight")


@dataclass
class Memory:
    id: int
    content: str
    subject: Optional[str]
    category: str
    status: str
    confidence: float
    source: str
    project_id: Optional[int]
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row) -> "Memory":
        return cls(
            id=row["id"], content=row["content"], subject=row["subject"],
            category=row["category"], status=row["status"], confidence=row["confidence"],
            source=row["source"], project_id=row["project_id"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def line(self) -> str:
        flag = "" if self.status == "confirmed" else f" ({STATUS_LABELS.get(self.status, self.status)})"
        return f"[#{self.id}] {self.content}{flag} – Quelle: {self.source}, {self.updated_at[:10]}"


@dataclass
class AddResult:
    status: str                       # "stored" | "duplicate" | "conflict"
    memory: Optional[Memory] = None
    conflicts: Optional[List[Memory]] = None


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text.rstrip(".!?;: ")


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


_SUBJECT_PATTERNS = [
    (re.compile(r"^(?:ich heiße|ich heisse|mein name ist|my name is|i am called)\s+(.+)$", re.I), "name"),
    (re.compile(r"^(?:ich wohne in|ich lebe in|i live in)\s+(.+)$", re.I), "wohnort"),
    (re.compile(r"^(?:ich arbeite als|ich bin von beruf|i work as)\s+(.+)$", re.I), "beruf"),
]
_MY_X_IS_Y = re.compile(
    r"^(?:mein|meine|meinen|meinem|meiner|my)\s+([\wäöüß\- ]{2,40}?)\s+"
    r"(?:ist|sind|heißt|heisst|lautet|is|are)\s+(.+)$",
    re.I,
)


def extract_subject(statement: str) -> Optional[str]:
    """Erkennt das Thema einer Aussage, z. B. 'Mein Lieblingseditor ist VS Code' -> 'lieblingseditor'."""
    text = statement.strip().rstrip(".!")
    for pattern, subject in _SUBJECT_PATTERNS:
        if pattern.match(text):
            return subject
    match = _MY_X_IS_Y.match(text)
    if match:
        return normalize(match.group(1))
    return None


_QUESTION_SUBJECT = re.compile(
    r"(?:was|wie|wer|wo|welche[rs]?|what|who|where|which)\s+(?:ist|sind|heißt|heisst|lautet|is|are)\s+"
    r"(?:mein|meine|meinen|meiner|my)\s+([\wäöüß\- ]{2,40}?)\s*\??$",
    re.I,
)


def subject_from_question(question: str) -> Optional[str]:
    text = question.strip()
    if re.match(r"^(?:wie heiße ich|wie heisse ich|what is my name|what's my name)", text, re.I):
        return "name"
    if re.match(r"^(?:wo wohne ich|where do i live)", text, re.I):
        return "wohnort"
    match = _QUESTION_SUBJECT.search(text)
    return normalize(match.group(1)) if match else None


class MemoryStore:
    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------- Lesen
    def get(self, memory_id: int) -> Optional[Memory]:
        row = self.db.query_one("SELECT * FROM memories WHERE id = ?", (memory_id,))
        return Memory.from_row(row) if row else None

    def active(self, category: Optional[str] = None, limit: int = 200) -> List[Memory]:
        sql = "SELECT * FROM memories WHERE status != 'outdated'"
        params: list = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params.append(limit)
        return [Memory.from_row(r) for r in self.db.query(sql, params)]

    def by_subject(self, subject: str, include_outdated: bool = False) -> List[Memory]:
        sql = "SELECT * FROM memories WHERE subject = ?"
        if not include_outdated:
            sql += " AND status != 'outdated'"
        sql += " ORDER BY updated_at DESC, id DESC"
        return [Memory.from_row(r) for r in self.db.query(sql, (normalize(subject),))]

    def search(self, text: str, limit: int = 8, include_outdated: bool = False) -> List[Memory]:
        status_filter = "" if include_outdated else "AND m.status != 'outdated'"
        query = fts_query(text)
        if not query:
            return []
        rows = []
        if self.db.fts_enabled:
            rows = self.db.query(
                f"""SELECT m.* FROM memories_fts f JOIN memories m ON m.id = f.rowid
                    WHERE memories_fts MATCH ? {status_filter}
                    ORDER BY bm25(memories_fts), m.updated_at DESC LIMIT ?""",
                (query, limit),
            )
        if len(rows) < limit:
            # Ergänzend Wortteile finden ("editor" in "Lieblingseditor")
            terms = search_terms(text)
            seen = {r["id"] for r in rows}
            like = " OR ".join("m.content LIKE ? OR m.subject LIKE ?" for _ in terms)
            params = [p for t in terms for p in (f"%{t}%", f"%{t}%")]
            extra = self.db.query(
                f"SELECT m.* FROM memories m WHERE ({like}) {status_filter} "
                "ORDER BY m.updated_at DESC LIMIT ?",
                params + [limit],
            )
            rows = list(rows) + [r for r in extra if r["id"] not in seen]
        return [Memory.from_row(r) for r in rows[:limit]]

    def touch(self, memories: List[Memory]) -> None:
        for m in memories:
            self.db.execute(
                "UPDATE memories SET use_count = use_count + 1, last_used_at = ? WHERE id = ?",
                (now_iso(), m.id),
            )

    def conflicts(self) -> List[List[Memory]]:
        """Themen mit mehreren gültigen, unterschiedlichen Erinnerungen."""
        rows = self.db.query(
            """SELECT subject FROM memories WHERE subject IS NOT NULL AND status != 'outdated'
               GROUP BY subject HAVING COUNT(DISTINCT content_hash) > 1"""
        )
        return [self.by_subject(r["subject"]) for r in rows]

    def count(self) -> int:
        return self.db.query_one("SELECT COUNT(*) FROM memories WHERE status != 'outdated'")[0]

    # ----------------------------------------------------------- Schreiben
    def add(
        self,
        content: str,
        source: str,
        category: str = "fact",
        subject: Optional[str] = None,
        status: str = "confirmed",
        confidence: float = 1.0,
        project_id: Optional[int] = None,
        check_conflicts: bool = True,
    ) -> AddResult:
        content = content.strip()
        if not content:
            raise ValueError("Leere Erinnerung")
        if category not in CATEGORIES:
            category = "fact"
        subject = normalize(subject) if subject else extract_subject(content)
        digest = content_hash(content)

        existing = self.db.query_one(
            "SELECT * FROM memories WHERE content_hash = ? AND status != 'outdated'", (digest,)
        )
        if existing:
            memory = Memory.from_row(existing)
            if status == "confirmed" and memory.status == "tentative":
                self.set_status(memory.id, "confirmed", source=source)
                memory = self.get(memory.id)
            return AddResult("duplicate", memory)

        if check_conflicts and subject:
            others = [m for m in self.by_subject(subject) if content_hash(m.content) != digest]
            if others:
                return AddResult("conflict", conflicts=others)

        ts = now_iso()
        cur = self.db.execute(
            """INSERT INTO memories (content, subject, category, status, confidence, source,
               project_id, content_hash, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (content, subject, category, status, confidence, source, project_id, digest, ts, ts),
        )
        return AddResult("stored", self.get(cur.lastrowid))

    def replace(self, old_ids: List[int], content: str, source: str, category: str = "fact",
                subject: Optional[str] = None) -> Memory:
        """Neue Angabe übernehmen, ältere als veraltet markieren (mit Verweis)."""
        result = self.add(content, source, category=category, subject=subject, check_conflicts=False)
        new = result.memory
        ts = now_iso()
        for old_id in old_ids:
            if old_id != new.id:
                self.db.execute(
                    "UPDATE memories SET status = 'outdated', replaced_by = ?, updated_at = ? WHERE id = ?",
                    (new.id, ts, old_id),
                )
        return new

    def correct(self, memory_id: int, new_content: str, source: str = "nutzer-korrektur") -> Optional[Memory]:
        old = self.get(memory_id)
        if not old:
            return None
        return self.replace([memory_id], new_content, source, category=old.category, subject=old.subject)

    def set_status(self, memory_id: int, status: str, source: Optional[str] = None) -> bool:
        if status not in STATUS_LABELS:
            raise ValueError(f"Ungültiger Status: {status}")
        sql = "UPDATE memories SET status = ?, updated_at = ?"
        params: list = [status, now_iso()]
        if source:
            sql += ", source = ?"
            params.append(source)
        sql += " WHERE id = ?"
        params.append(memory_id)
        return self.db.execute(sql, params).rowcount > 0

    def forget(self, memory_id: int) -> bool:
        """Löscht eine Erinnerung endgültig (auf ausdrücklichen Wunsch des Nutzers)."""
        return self.db.execute("DELETE FROM memories WHERE id = ?", (memory_id,)).rowcount > 0

    def export(self) -> List[dict]:
        return [dict(r) for r in self.db.query("SELECT * FROM memories ORDER BY id")]


_SUBORDINATE = re.compile(
    r"^(mein|meine|meinen|meinem|meiner)\s+([\wäöüß\-]+)\s+(.+?)\s+(ist|sind|heißt|heisst|lautet)$", re.I
)
_ICH_SUBORDINATE = re.compile(r"^ich\s+(.+?)\s+(heiße|heisse|bin|wohne|arbeite|mag|liebe|habe)$", re.I)


def canonical_statement(text: str) -> str:
    """Formt Nebensätze nach 'merke dir, dass …' in Hauptsätze um.

    'mein Lieblingseditor VS Code ist' -> 'Mein Lieblingseditor ist VS Code'
    'ich in Berlin wohne'             -> 'Ich wohne in Berlin'
    """
    t = text.strip().rstrip(".!")
    m = _SUBORDINATE.match(t)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)} {m.group(4)} {m.group(3)}"
    m = _ICH_SUBORDINATE.match(t)
    if m:
        return f"Ich {m.group(2)} {m.group(1)}"
    return t[:1].upper() + t[1:] if t else t
