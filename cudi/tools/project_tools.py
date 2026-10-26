"""Werkzeuge für Projekte und Aufgaben."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from ..brain.projects import ENTRY_KINDS, TASK_STATUS
from ..core.permissions import Level
from .registry import Tool, ToolOutput, ToolRegistry

if TYPE_CHECKING:  # pragma: no cover
    from ..core.application import Application


def register(registry: ToolRegistry, app: "Application") -> None:
    projects = app.projects

    def pick(name: Optional[str]) -> Optional[Dict]:
        return projects.find(name) if name else projects.active()

    def create_project(name: str, purpose: str = "") -> ToolOutput:
        existed = projects.find(name)
        project = projects.create(name, purpose)
        projects.set_active(project["id"])
        verb = "existiert bereits und ist jetzt aktiv" if existed else "angelegt und aktiv"
        return ToolOutput(True, f"Projekt „{project['name']}“ {verb}.", summary=f"Projekt „{project['name']}“ {verb}")

    def switch_project(name: str) -> ToolOutput:
        project = projects.find(name)
        if not project:
            names = ", ".join(p["name"] for p in projects.list()) or "keine"
            return ToolOutput(False, f"Projekt „{name}“ nicht gefunden. Vorhandene Projekte: {names}")
        projects.set_active(project["id"])
        return ToolOutput(True, projects.summary(project["id"]), summary=f"aktives Projekt: {project['name']}")

    def list_projects() -> ToolOutput:
        items = projects.list()
        if not items:
            return ToolOutput(True, "Es gibt noch keine Projekte.", summary="keine Projekte")
        active = projects.active()
        lines = [f"{'→ ' if active and p['id'] == active['id'] else '  '}{p['name']} ({p['status']}) – {p['purpose']}"
                 for p in items]
        return ToolOutput(True, "\n".join(lines), summary=f"{len(items)} Projekte")

    def project_status(project: Optional[str] = None) -> ToolOutput:
        p = pick(project)
        if not p:
            return ToolOutput(False, "Kein Projekt aktiv. Lege eins an oder nenne den Projektnamen.")
        return ToolOutput(True, projects.summary(p["id"]), summary=f"Projektstand „{p['name']}“")

    def add_project_entry(kind: str, content: str, project: Optional[str] = None) -> ToolOutput:
        p = pick(project)
        if not p:
            return ToolOutput(False, "Kein Projekt aktiv – bitte zuerst ein Projekt anlegen oder auswählen.")
        if kind not in ENTRY_KINDS:
            return ToolOutput(False, f"Unbekannte Art '{kind}'. Erlaubt: {', '.join(ENTRY_KINDS)}")
        entry = projects.add_entry(p["id"], kind, content)
        app.episodes.record("project_entry", f"{ENTRY_KINDS[kind]}: {content}", project_id=p["id"], ok=True)
        return ToolOutput(True, f"{ENTRY_KINDS[kind]} #{entry['id']} im Projekt „{p['name']}“ gespeichert.",
                          summary=f"{ENTRY_KINDS[kind]} gespeichert ({p['name']})")

    def add_task(title: str, project: Optional[str] = None) -> ToolOutput:
        p = pick(project)
        task = projects.add_task(title, p["id"] if p else None)
        return ToolOutput(True, f"Aufgabe #{task['id']} angelegt: {title}", summary=f"Aufgabe #{task['id']} angelegt")

    def list_tasks(status: Optional[str] = None) -> ToolOutput:
        statuses = (status,) if status in TASK_STATUS else ("offen", "in_arbeit")
        items = projects.tasks(statuses=statuses)
        if not items:
            return ToolOutput(True, "Keine passenden Aufgaben.", summary="keine Aufgaben")
        return ToolOutput(True, "\n".join(f"#{t['id']} [{t['status']}] {t['title']}" for t in items),
                          summary=f"{len(items)} Aufgaben")

    def update_task(task_id: int, status: str, result: Optional[str] = None) -> ToolOutput:
        if status not in TASK_STATUS:
            return ToolOutput(False, f"Ungültiger Status. Erlaubt: {', '.join(TASK_STATUS)}")
        task = projects.update_task(task_id, status, result)
        if not task:
            return ToolOutput(False, f"Aufgabe #{task_id} gibt es nicht.")
        return ToolOutput(True, f"Aufgabe #{task_id} ist jetzt „{status}“.", summary=f"Aufgabe #{task_id}: {status}")

    project_param = {"type": "string", "description": "Projektname; leer = aktives Projekt"}
    registry.register(Tool("create_project", "Legt ein neues Projekt an und macht es zum aktiven Projekt.",
                           {"type": "object", "properties": {"name": {"type": "string"},
                                                             "purpose": {"type": "string"}}, "required": ["name"]},
                           Level.SUGGEST, create_project))
    registry.register(Tool("switch_project", "Wechselt das aktive Projekt und zeigt dessen Stand.",
                           {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                           Level.SUGGEST, switch_project))
    registry.register(Tool("list_projects", "Listet alle Projekte.", {"type": "object", "properties": {}},
                           Level.READ, list_projects))
    registry.register(Tool("project_status", "Zeigt den gespeicherten Stand eines Projekts (Ziele, Entscheidungen, "
                           "offene Probleme, nächste Schritte, Aufgaben).",
                           {"type": "object", "properties": {"project": project_param}}, Level.READ, project_status))
    registry.register(Tool("add_project_entry",
                           "Speichert im Projektgedächtnis eine Entscheidung, ein Problem, eine getestete Lösung, "
                           "einen nächsten Schritt, ein Ziel, eine Anforderung, eine Erkenntnis oder Notiz.",
                           {"type": "object", "properties": {
                               "kind": {"type": "string", "enum": list(ENTRY_KINDS)},
                               "content": {"type": "string"}, "project": project_param},
                            "required": ["kind", "content"]},
                           Level.SUGGEST, add_project_entry))
    registry.register(Tool("add_task", "Legt eine Aufgabe an (optional zu einem Projekt).",
                           {"type": "object", "properties": {"title": {"type": "string"}, "project": project_param},
                            "required": ["title"]}, Level.SUGGEST, add_task))
    registry.register(Tool("list_tasks", "Listet Aufgaben (Standard: offene und laufende).",
                           {"type": "object", "properties": {"status": {"type": "string", "enum": list(TASK_STATUS)}}},
                           Level.READ, list_tasks))
    registry.register(Tool("update_task", "Ändert den Status einer Aufgabe.",
                           {"type": "object", "properties": {"task_id": {"type": "integer"},
                                                             "status": {"type": "string", "enum": list(TASK_STATUS)},
                                                             "result": {"type": "string"}},
                            "required": ["task_id", "status"]}, Level.SUGGEST, update_task))
