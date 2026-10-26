"""Fenster „Digitales Gehirn“: zeigt den tatsächlichen Inhalt der CUDI-Datenbank."""

from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QPlainTextEdit, QPushButton, QTabWidget,
                               QVBoxLayout)

from cudi.brain.memory import STATUS_LABELS
from cudi.diagnostics.health import report


class BrainDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("🧠 Digitales Gehirn")
        self.resize(900, 650)
        self.tabs = QTabWidget()
        self.views = {}
        for key, title in (("memories", "Erinnerungen"), ("projects", "Projekte"), ("tasks", "Aufgaben"),
                           ("documents", "Dokumente"), ("history", "Verlauf"), ("models", "Modelle"),
                           ("diagnosis", "Diagnose")):
            view = QPlainTextEdit()
            view.setReadOnly(True)
            self.views[key] = view
            self.tabs.addTab(view, title)

        refresh = QPushButton("Aktualisieren")
        refresh.clicked.connect(self.refresh)
        close = QPushButton("Schließen")
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(refresh)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addLayout(buttons)
        self.setStyleSheet("QPlainTextEdit { font-family: Consolas, 'DejaVu Sans Mono', monospace; font-size: 12px; }")
        self.refresh()

    def refresh(self) -> None:
        app = self.app
        memories = app.memory.active(limit=500)
        conflicts = app.memory.conflicts()
        lines = [f"{len(memories)} gültige Erinnerungen"]
        if conflicts:
            lines.append("⚠️ Widersprüche: " + "; ".join(" / ".join(m.content for m in group) for group in conflicts))
        for m in memories:
            lines.append(f"#{m.id} [{m.category}, {STATUS_LABELS.get(m.status, m.status)}] {m.content}\n"
                         f"      Quelle: {m.source} · geändert {m.updated_at.replace('T', ' ')}")
        lines.append("\nKorrigieren: /korrigiere ID NEUER TEXT · Löschen: vergiss #ID · Export: /export")
        self.views["memories"].setPlainText("\n".join(lines))

        projects = app.projects.list()
        active = app.projects.active()
        self.views["projects"].setPlainText("\n\n".join(
            ("→ AKTIV\n" if active and p["id"] == active["id"] else "") + app.projects.summary(p["id"])
            for p in projects) or "Noch keine Projekte. Anlegen mit: /projekt neu NAME | ZWECK")

        tasks = app.projects.tasks()
        self.views["tasks"].setPlainText("\n".join(
            f"#{t['id']} [{t['status']}] {t['title']}" + (f" → {t['result']}" if t["result"] else "")
            for t in tasks) or "Keine Aufgaben. Anlegen mit: /aufgabe TEXT")

        docs = app.knowledge.documents()
        self.views["documents"].setPlainText("\n".join(
            f"#{d['id']} {d['name']} ({d['file_type']}, {d['chunk_count']} Abschnitte) – importiert "
            f"{d['imported_at'].replace('T', ' ')}\n      {d['path']}" for d in docs)
            or f"Noch keine Dokumente. Dateien in den Ordner {app.settings.import_dir} legen und /importordner "
               f"eingeben – oder im Menü „Gehirn → Dokument importieren…“.")

        episodes = app.episodes.recent(80)
        self.views["history"].setPlainText("\n".join(
            f"{e['created_at'].replace('T', ' ')}  {'✅' if e['ok'] == 1 else '❌' if e['ok'] == 0 else '•'} "
            f"[{e['kind']}] {e['summary']}" for e in episodes) or "Noch keine Einträge.")

        self.views["models"].setPlainText(app.orchestrator.models_text())
        self.views["diagnosis"].setPlainText(report(app))
