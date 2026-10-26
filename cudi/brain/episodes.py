"""Entscheidungs- und Verlaufsprotokoll, Feedback und Modellaufrufe."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .database import Database, now_iso


class EpisodeLog:
    def __init__(self, db: Database):
        self.db = db

    def record(self, kind: str, summary: str, data: Optional[Dict[str, Any]] = None,
               ok: Optional[bool] = None, signature: Optional[str] = None,
               project_id: Optional[int] = None) -> int:
        cur = self.db.execute(
            "INSERT INTO episodes (kind, summary, data, ok, signature, project_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kind, summary[:500], json.dumps(data, ensure_ascii=False, default=str) if data else None,
             None if ok is None else int(ok), signature, project_id, now_iso()),
        )
        return cur.lastrowid

    def recent(self, limit: int = 20, kind: Optional[str] = None) -> List[Dict]:
        sql = "SELECT * FROM episodes"
        params: list = []
        if kind:
            sql += " WHERE kind = ?"
            params.append(kind)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.query(sql, params)]

    def previous_failure(self, signature: str) -> Optional[str]:
        """Text, falls genau dieser Werkzeugaufruf schon einmal fehlgeschlagen ist."""
        row = self.db.query_one(
            "SELECT summary, created_at FROM episodes WHERE signature = ? AND ok = 0 "
            "ORDER BY id DESC LIMIT 1",
            (signature,),
        )
        if not row:
            return None
        return (f"Genau dieser Aufruf ist bereits am {row['created_at'][:16].replace('T', ' ')} "
                f"fehlgeschlagen ({row['summary']}). Bitte einen anderen Lösungsweg wählen.")

    # ------------------------------------------------------------ Feedback
    def add_feedback(self, rating: int, comment: str = "", message_id: Optional[int] = None) -> int:
        cur = self.db.execute(
            "INSERT INTO feedback (message_id, rating, comment, created_at) VALUES (?, ?, ?, ?)",
            (message_id, rating, comment, now_iso()),
        )
        return cur.lastrowid

    def feedback_stats(self) -> Dict[str, int]:
        row = self.db.query_one(
            "SELECT SUM(rating > 0) AS positiv, SUM(rating < 0) AS negativ FROM feedback"
        )
        return {"positiv": row["positiv"] or 0, "negativ": row["negativ"] or 0}

    # ------------------------------------------------------- Modellaufrufe
    def model_call(self, provider: str, model: Optional[str], ok: bool, latency_ms: int,
                   input_tokens: Optional[int] = None, output_tokens: Optional[int] = None,
                   error: Optional[str] = None) -> None:
        self.db.execute(
            "INSERT INTO model_calls (provider, model, ok, latency_ms, input_tokens, output_tokens, error, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (provider, model, int(ok), latency_ms, input_tokens, output_tokens, error, now_iso()),
        )

    def model_stats(self) -> List[Dict]:
        return [dict(r) for r in self.db.query(
            """SELECT provider, model, COUNT(*) AS aufrufe, SUM(ok) AS erfolgreich,
                      CAST(AVG(latency_ms) AS INTEGER) AS mittlere_ms,
                      SUM(COALESCE(input_tokens, 0)) AS input_tokens,
                      SUM(COALESCE(output_tokens, 0)) AS output_tokens
               FROM model_calls GROUP BY provider, model ORDER BY aufrufe DESC"""
        )]
