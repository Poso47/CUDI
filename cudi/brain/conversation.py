"""Gesprächs- und Arbeitskontext (Arbeitsgedächtnis).

Gespräche werden in der Datenbank gehalten, damit CUDI nach einem Neustart den
Verlauf kennt. Offene Rückfragen/Bestätigungen leben nur im Arbeitsspeicher.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .database import Database, now_iso


@dataclass
class WorkingMemory:
    """Kurzlebiger Kontext der laufenden Sitzung."""

    current_goal: Optional[str] = None
    open_question: Optional[Dict[str, Any]] = None   # z. B. Konflikt, der auf "ja/nein" wartet
    completed_steps: List[str] = field(default_factory=list)
    active_files: List[str] = field(default_factory=list)

    def note_step(self, text: str) -> None:
        self.completed_steps.append(text)
        del self.completed_steps[:-20]

    def note_file(self, path: str) -> None:
        if path in self.active_files:
            self.active_files.remove(path)
        self.active_files.append(path)
        del self.active_files[:-10]


class ConversationStore:
    def __init__(self, db: Database):
        self.db = db

    def current_id(self) -> int:
        value = self.db.get_state("current_conversation")
        if value and self.db.query_one("SELECT 1 FROM conversations WHERE id = ?", (int(value),)):
            return int(value)
        return self.new_conversation()

    def new_conversation(self, title: str = "") -> int:
        ts = now_iso()
        cur = self.db.execute(
            "INSERT INTO conversations (title, started_at, last_active_at) VALUES (?, ?, ?)",
            (title, ts, ts),
        )
        self.db.set_state("current_conversation", str(cur.lastrowid))
        return cur.lastrowid

    def add(self, role: str, content: str, meta: Optional[dict] = None,
            conversation_id: Optional[int] = None) -> int:
        conv = conversation_id or self.current_id()
        ts = now_iso()
        cur = self.db.execute(
            "INSERT INTO messages (conversation_id, role, content, meta, created_at) VALUES (?, ?, ?, ?, ?)",
            (conv, role, content, json.dumps(meta, ensure_ascii=False) if meta else None, ts),
        )
        self.db.execute("UPDATE conversations SET last_active_at = ? WHERE id = ?", (ts, conv))
        return cur.lastrowid

    def history(self, limit: int, conversation_id: Optional[int] = None,
                before_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Letzte Nachrichten (älteste zuerst) als {'id','role','content'}."""
        if limit <= 0:
            return []
        conv = conversation_id or self.current_id()
        sql = "SELECT id, role, content FROM messages WHERE conversation_id = ?"
        params: list = [conv]
        if before_id:
            sql += " AND id < ?"
            params.append(before_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.db.query(sql, params)
        return [dict(r) for r in reversed(rows)]

    def last_assistant_message(self) -> Optional[Dict[str, Any]]:
        row = self.db.query_one(
            "SELECT id, content FROM messages WHERE conversation_id = ? AND role = 'assistant' "
            "ORDER BY id DESC LIMIT 1",
            (self.current_id(),),
        )
        return dict(row) if row else None

    def message_count(self) -> int:
        return self.db.query_one("SELECT COUNT(*) FROM messages")[0]
