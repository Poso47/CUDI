"""Projektgedächtnis: Ziele, Entscheidungen, Probleme, Lösungen, nächste Schritte, Aufgaben."""

from __future__ import annotations

from typing import Dict, List, Optional

from .database import Database, now_iso

ENTRY_KINDS = {
    "goal": "Ziel",
    "requirement": "Anforderung",
    "decision": "Entscheidung",
    "issue": "Offenes Problem",
    "solution": "Getestete Lösung",
    "next_step": "Nächster Schritt",
    "note": "Notiz",
    "insight": "Erkenntnis",
    "file": "Relevante Datei",
    "status": "Stand",
}
TASK_STATUS = ("offen", "in_arbeit", "erledigt", "fehlgeschlagen")


class ProjectStore:
    def __init__(self, db: Database):
        self.db = db

    # ---------------------------------------------------------- Projekte
    def create(self, name: str, purpose: str = "") -> Dict:
        name = name.strip()
        if not name:
            raise ValueError("Projektname fehlt")
        existing = self.find(name)
        if existing:
            return existing
        ts = now_iso()
        cur = self.db.execute(
            "INSERT INTO projects (name, purpose, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (name, purpose.strip(), ts, ts),
        )
        return self.get(cur.lastrowid)

    def get(self, project_id: int) -> Optional[Dict]:
        row = self.db.query_one("SELECT * FROM projects WHERE id = ?", (project_id,))
        return dict(row) if row else None

    def find(self, name: str) -> Optional[Dict]:
        row = self.db.query_one("SELECT * FROM projects WHERE name = ? COLLATE NOCASE", (name.strip(),))
        return dict(row) if row else None

    def list(self) -> List[Dict]:
        return [dict(r) for r in self.db.query("SELECT * FROM projects ORDER BY updated_at DESC")]

    def set_active(self, project_id: Optional[int]) -> None:
        self.db.set_state("active_project", str(project_id) if project_id else None)

    def active(self) -> Optional[Dict]:
        value = self.db.get_state("active_project")
        return self.get(int(value)) if value else None

    def touch(self, project_id: int) -> None:
        self.db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now_iso(), project_id))

    # ---------------------------------------------------------- Einträge
    def add_entry(self, project_id: int, kind: str, content: str, source: str = "nutzer") -> Dict:
        if kind not in ENTRY_KINDS:
            raise ValueError(f"Unbekannte Eintragsart: {kind} (erlaubt: {', '.join(ENTRY_KINDS)})")
        cur = self.db.execute(
            "INSERT INTO project_entries (project_id, kind, content, source, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, kind, content.strip(), source, now_iso()),
        )
        self.touch(project_id)
        return dict(self.db.query_one("SELECT * FROM project_entries WHERE id = ?", (cur.lastrowid,)))

    def close_entry(self, entry_id: int, status: str = "erledigt") -> bool:
        return self.db.execute(
            "UPDATE project_entries SET status = ? WHERE id = ?", (status, entry_id)
        ).rowcount > 0

    def entries(self, project_id: int, kind: Optional[str] = None, only_open: bool = False,
                limit: int = 50) -> List[Dict]:
        sql = "SELECT * FROM project_entries WHERE project_id = ?"
        params: list = [project_id]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if only_open:
            sql += " AND status = 'offen'"
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.query(sql, params)]

    def summary(self, project_id: int, per_kind: int = 5) -> str:
        project = self.get(project_id)
        if not project:
            return "Projekt nicht gefunden."
        lines = [f"Projekt: {project['name']} ({project['status']})"]
        if project["purpose"]:
            lines.append(f"Zweck: {project['purpose']}")
        for kind in ("status", "goal", "requirement", "decision", "issue", "solution", "next_step",
                     "insight", "file", "note"):
            only_open = kind in ("issue", "next_step")
            items = self.entries(project_id, kind, only_open=only_open, limit=per_kind)
            if items:
                lines.append(f"{ENTRY_KINDS[kind]}:")
                lines.extend(f"  - [#{e['id']}] {e['content']} ({e['created_at'][:10]})" for e in items)
        tasks = self.tasks(project_id=project_id, statuses=("offen", "in_arbeit"))
        if tasks:
            lines.append("Offene Aufgaben:")
            lines.extend(f"  - [#{t['id']}] {t['title']} ({t['status']})" for t in tasks[:per_kind])
        return "\n".join(lines)

    # ----------------------------------------------------------- Aufgaben
    def add_task(self, title: str, project_id: Optional[int] = None) -> Dict:
        ts = now_iso()
        cur = self.db.execute(
            "INSERT INTO tasks (title, project_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title.strip(), project_id, ts, ts),
        )
        return dict(self.db.query_one("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)))

    def update_task(self, task_id: int, status: str, result: Optional[str] = None) -> Optional[Dict]:
        if status not in TASK_STATUS:
            raise ValueError(f"Ungültiger Aufgabenstatus: {status} (erlaubt: {', '.join(TASK_STATUS)})")
        changed = self.db.execute(
            "UPDATE tasks SET status = ?, result = COALESCE(?, result), updated_at = ? WHERE id = ?",
            (status, result, now_iso(), task_id),
        ).rowcount
        if not changed:
            return None
        return dict(self.db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,)))

    def tasks(self, project_id: Optional[int] = None, statuses=TASK_STATUS, limit: int = 100) -> List[Dict]:
        placeholders = ",".join("?" for _ in statuses)
        sql = f"SELECT * FROM tasks WHERE status IN ({placeholders})"
        params: list = list(statuses)
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.query(sql, params)]

    def export(self) -> Dict[str, List[Dict]]:
        return {
            "projects": [dict(r) for r in self.db.query("SELECT * FROM projects ORDER BY id")],
            "project_entries": [dict(r) for r in self.db.query("SELECT * FROM project_entries ORDER BY id")],
            "tasks": [dict(r) for r in self.db.query("SELECT * FROM tasks ORDER BY id")],
        }
