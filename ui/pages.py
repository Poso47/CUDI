"""Bereiche des Hauptfensters. Jeder Bereich zeigt echte Daten aus dem Kern (``refresh``).

Aktionen laufen über ``window.run_tool`` bzw. ``window.run_command`` – damit gelten dieselben
Berechtigungen, Freigaben und Protokolle wie im Chat.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from cudi.brain.knowledge import SUPPORTED
from cudi.brain.memory import STATUS_LABELS
from cudi.brain.projects import ENTRY_KINDS, TASK_STATUS
from cudi.core.permissions import LEVEL_LABELS, Level
from cudi.diagnostics.health import report

if TYPE_CHECKING:  # pragma: no cover
    from .main_window import MainWindow


def _button(text: str, slot, kind: str = "") -> QPushButton:
    btn = QPushButton(text)
    if kind:
        btn.setObjectName(kind)
    btn.clicked.connect(slot)
    return btn


def _table(headers: List[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.setWordWrap(True)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(False)
    return table


def _fill(table: QTableWidget, rows: List[List[str]], stretch_column: int) -> None:
    table.setRowCount(0)
    for values in rows:
        r = table.rowCount()
        table.insertRow(r)
        for c, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            table.setItem(r, c, item)
    table.horizontalHeader().setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
    table.resizeRowsToContents()


def _selected_id(table: QTableWidget) -> Optional[int]:
    rows = table.selectionModel().selectedRows()
    if not rows:
        return None
    text = table.item(rows[0].row(), 0).text().lstrip("#")
    return int(text) if text.isdigit() else None


class Page(QWidget):
    title = ""
    hint = ""

    def __init__(self, window: "MainWindow"):
        super().__init__()
        self.setObjectName("page")
        self.window_ = window
        self.app = window.app
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(24, 20, 24, 20)
        self.body.setSpacing(12)
        title = QLabel(self.title)
        title.setObjectName("pageTitle")
        self.body.addWidget(title)
        if self.hint:
            hint = QLabel(self.hint)
            hint.setObjectName("pageHint")
            hint.setWordWrap(True)
            self.body.addWidget(hint)

    def toolbar(self, *buttons: QPushButton) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for b in buttons:
            row.addWidget(b)
        row.addStretch(1)
        self.body.addLayout(row)
        return row

    def refresh(self) -> None:  # pragma: no cover - überschrieben
        pass


# ----------------------------------------------------------------- Gedächtnis
class MemoryPage(Page):
    title = "🧠 Gedächtnis"
    hint = ("Alles, was CUDI dauerhaft über dich weiß – mit Quelle und Status. Neues speicherst du im Chat "
            "mit „Merke dir: …“. Widersprüche erkennt CUDI selbst und fragt nach.")

    def __init__(self, window):
        super().__init__(window)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen …")
        self.search.textChanged.connect(self.refresh)
        row = self.toolbar(_button("Korrigieren", self.correct), _button("Löschen", self.delete, "danger"),
                           _button("Exportieren", lambda: window.run_tool("export_data", {})),
                           _button("Altes Wissen übernehmen", lambda: window.run_tool("import_legacy_knowledge", {})))
        row.insertWidget(0, self.search, 2)
        self.table = _table(["ID", "Inhalt", "Art", "Status", "Quelle", "Geändert"])
        self.body.addWidget(self.table, 1)
        self.conflicts = QLabel()
        self.conflicts.setWordWrap(True)
        self.conflicts.setStyleSheet("color: #d29922;")
        self.body.addWidget(self.conflicts)

    def refresh(self):
        query = self.search.text().strip()
        items = self.app.memory.search(query, limit=200) if query else self.app.memory.active(limit=500)
        _fill(self.table, [[m.id, m.content, m.category, STATUS_LABELS.get(m.status, m.status), m.source,
                            m.updated_at.replace("T", " ")[:16]] for m in items], 1)
        groups = self.app.memory.conflicts()
        self.conflicts.setText("⚠️ Widersprüche: " + "; ".join(" / ".join(m.content for m in g) for g in groups)
                               if groups else "")

    def correct(self):
        mem_id = _selected_id(self.table)
        if mem_id is None:
            self.window_.notify("Bitte zuerst eine Erinnerung auswählen.")
            return
        old = self.app.memory.get(mem_id)
        text, ok = QInputDialog.getText(self, "Erinnerung korrigieren", "Neuer Inhalt:", text=old.content if old else "")
        if ok and text.strip():
            self.window_.run_tool("replace_memory", {"memory_id": mem_id, "content": text.strip()})

    def delete(self):
        mem_id = _selected_id(self.table)
        if mem_id is None:
            self.window_.notify("Bitte zuerst eine Erinnerung auswählen.")
            return
        self.window_.run_tool("forget_memory", {"memory_id": mem_id})


# ------------------------------------------------------------------- Projekte
class ProjectsPage(Page):
    title = "📁 Projekte"
    hint = "Ziele, Entscheidungen, Probleme, Lösungen und nächste Schritte – CUDI setzt nach einem Neustart genau hier fort."

    def __init__(self, window):
        super().__init__(window)
        self.toolbar(_button("Neues Projekt", self.new_project, "primary"),
                     _button("Als aktiv setzen", self.activate),
                     _button("Eintrag hinzufügen", self.add_entry))
        split = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(lambda *_: self.show_selected())
        self.detail = QPlainTextEdit()
        self.detail.setObjectName("report")
        self.detail.setReadOnly(True)
        split.addWidget(self.list)
        split.addWidget(self.detail)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        self.body.addWidget(split, 1)

    def refresh(self):
        current = self._selected_name()
        active = self.app.projects.active()
        self.list.clear()
        for p in self.app.projects.list():
            label = ("● " if active and p["id"] == active["id"] else "   ") + p["name"]
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, p["name"])
            self.list.addItem(item)
            if p["name"] == current or (current is None and active and p["id"] == active["id"]):
                self.list.setCurrentItem(item)
        if self.list.count() and self.list.currentItem() is None:
            self.list.setCurrentRow(0)
        self.show_selected()

    def _selected_name(self) -> Optional[str]:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def show_selected(self):
        name = self._selected_name()
        project = self.app.projects.find(name) if name else None
        self.detail.setPlainText(self.app.projects.summary(project["id"], per_kind=20) if project else
                                 "Noch kein Projekt. Lege eins an – oder sag im Chat: „Neues Projekt …“.")

    def new_project(self):
        name, ok = QInputDialog.getText(self, "Neues Projekt", "Name:")
        if not ok or not name.strip():
            return
        purpose, _ = QInputDialog.getText(self, "Neues Projekt", "Zweck (optional):")
        self.window_.run_tool("create_project", {"name": name.strip(), "purpose": purpose.strip()})

    def activate(self):
        name = self._selected_name()
        if name:
            self.window_.run_tool("switch_project", {"name": name})

    def add_entry(self):
        name = self._selected_name()
        if not name:
            self.window_.notify("Bitte zuerst ein Projekt anlegen oder auswählen.")
            return
        labels = [f"{label} ({kind})" for kind, label in ENTRY_KINDS.items()]
        choice, ok = QInputDialog.getItem(self, "Eintrag hinzufügen", "Art:", labels, 2, False)
        if not ok:
            return
        kind = choice.rsplit("(", 1)[1].rstrip(")")
        text, ok = QInputDialog.getMultiLineText(self, "Eintrag hinzufügen", f"{choice.split(' (')[0]}:")
        if ok and text.strip():
            self.window_.run_tool("add_project_entry", {"kind": kind, "content": text.strip(), "project": name})


# ------------------------------------------------------------------- Aufgaben
class TasksPage(Page):
    title = "✅ Aufgaben"
    hint = "Offene, laufende, erledigte und fehlgeschlagene Aufgaben."

    def __init__(self, window):
        super().__init__(window)
        self.filter = QComboBox()
        self.filter.addItems(["offen + in Arbeit", "alle"] + list(TASK_STATUS))
        self.filter.currentIndexChanged.connect(self.refresh)
        row = self.toolbar(_button("Neue Aufgabe", self.add, "primary"),
                           _button("Erledigt", lambda: self.set_status("erledigt")),
                           _button("In Arbeit", lambda: self.set_status("in_arbeit")),
                           _button("Fehlgeschlagen", lambda: self.set_status("fehlgeschlagen")))
        row.addWidget(self.filter)
        self.table = _table(["ID", "Aufgabe", "Status", "Projekt", "Geändert"])
        self.body.addWidget(self.table, 1)

    def refresh(self):
        choice = self.filter.currentText()
        statuses = {"offen + in Arbeit": ("offen", "in_arbeit"), "alle": TASK_STATUS}.get(choice, (choice,))
        names = {p["id"]: p["name"] for p in self.app.projects.list()}
        _fill(self.table, [[t["id"], t["title"], t["status"], names.get(t["project_id"], "–"),
                            t["updated_at"].replace("T", " ")[:16]] for t in self.app.projects.tasks(statuses=statuses)], 1)

    def add(self):
        title, ok = QInputDialog.getText(self, "Neue Aufgabe", "Aufgabe:")
        if ok and title.strip():
            self.window_.run_tool("add_task", {"title": title.strip()})

    def set_status(self, status: str):
        task_id = _selected_id(self.table)
        if task_id is None:
            self.window_.notify("Bitte zuerst eine Aufgabe auswählen.")
            return
        self.window_.run_tool("update_task", {"task_id": task_id, "status": status})


# ------------------------------------------------------------------ Dokumente
class DocumentsPage(Page):
    title = "📄 Dokumente"
    hint = ("Importierte Dokumente sind Wissensquellen: CUDI beantwortet Fragen daraus und nennt die Fundstelle. "
            f"Unterstützt: {', '.join(SUPPORTED)}.")

    def __init__(self, window):
        super().__init__(window)
        self.toolbar(_button("Dokument importieren …", self.import_file, "primary"),
                     _button("Importordner einlesen", lambda: window.run_tool("import_folder", {})),
                     _button("Importordner öffnen", lambda: window.open_folder(self.app.settings.import_dir)))
        self.table = _table(["ID", "Name", "Typ", "Abschnitte", "Importiert", "Pfad"])
        self.body.addWidget(self.table, 2)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("In Dokumenten suchen …")
        self.search.returnPressed.connect(self.do_search)
        search_row.addWidget(self.search, 1)
        search_row.addWidget(_button("Suchen", self.do_search))
        self.body.addLayout(search_row)
        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        self.body.addWidget(self.results, 1)

    def refresh(self):
        _fill(self.table, [[d["id"], d["name"], d["file_type"], d["chunk_count"], d["imported_at"].replace("T", " ")[:16],
                            d["path"]] for d in self.app.knowledge.documents()], 5)

    def import_file(self):
        pattern = "Dokumente (" + " ".join(f"*{s}" for s in SUPPORTED) + ")"
        path, _ = QFileDialog.getOpenFileName(self, "Dokument importieren", "", pattern)
        if path:
            self.window_.run_tool("import_document", {"path": path})

    def do_search(self):
        query = self.search.text().strip()
        if not query:
            return
        hits = self.app.knowledge.search(query, limit=8)
        self.results.setPlainText("\n\n".join(f"📍 {h.source}\n{self.app.knowledge.snippet(h, query, 500)}"
                                              for h in hits) or f"Nichts zu „{query}“ gefunden.")


# -------------------------------------------------------------------- Modelle
class ModelsPage(Page):
    title = "🤖 Sprachmodelle"
    hint = ("CUDI versucht die Modelle in dieser Reihenfolge. Lokal (Ollama) bleiben deine Daten auf dem Rechner; "
            "externe Anbieter (Claude, OpenAI) werden in jeder Antwort als „extern“ gekennzeichnet.")

    def __init__(self, window):
        super().__init__(window)
        self.toolbar(_button("Erneut prüfen", self.recheck, "primary"),
                     _button("Einstellungen", lambda: window.show_page("settings")))
        self.text = QPlainTextEdit()
        self.text.setObjectName("report")
        self.text.setReadOnly(True)
        self.body.addWidget(self.text, 1)

    def recheck(self):
        for provider in self.app.models.providers.values():
            if hasattr(provider, "_status_cache"):
                provider._status_cache = None
        self.refresh()
        self.window_.update_model_status()

    def refresh(self):
        self.text.setPlainText(self.app.orchestrator.models_text())


# ------------------------------------------------------------------ Werkzeuge
class ToolsPage(Page):
    title = "🛠 Werkzeuge"
    hint = ("Diese Werkzeuge kann CUDI tatsächlich ausführen. Ab Stufe 3 fragt CUDI vorher um Erlaubnis; "
            "Stufe 5 (extern/irreversibel) immer.")

    def __init__(self, window):
        super().__init__(window)
        self.toolbar(_button("Für diese Sitzung ohne Rückfrage erlauben", self.grant),
                     _button("Alle Sitzungsfreigaben zurücknehmen", self.revoke))
        self.table = _table(["Werkzeug", "Beschreibung", "Stufe", "Status"])
        self.body.addWidget(self.table, 1)

    def refresh(self):
        grants = self.app.permissions.session_grants
        rows = []
        for tool, reason in self.app.tools.availability():
            level = Level(min(tool.level, 5))
            status = "nicht verfügbar: " + reason if reason else (
                "ohne Rückfrage (Sitzung)" if tool.name in grants else
                "mit Rückfrage" if self.app.permissions.needs_confirmation(tool.name, tool.level) else "automatisch")
            rows.append([tool.name, tool.description, f"{int(level)} – {LEVEL_LABELS[level]}", status])
        _fill(self.table, rows, 1)

    def grant(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.window_.notify("Bitte zuerst ein Werkzeug auswählen.")
            return
        self.window_.run_command(f"/erlauben {self.table.item(rows[0].row(), 0).text()}")

    def revoke(self):
        self.app.permissions.revoke_all()
        self.window_.notify("Alle Sitzungsfreigaben zurückgenommen.")
        self.refresh()


# ------------------------------------------------------------------- Diagnose
class DiagnosisPage(Page):
    title = "🩺 Diagnose"
    hint = "❌ kritisch · ⚠️ Warnung · ➖ optional/nicht vorhanden – jeweils mit Lösungsvorschlag."

    def __init__(self, window):
        super().__init__(window)
        self.toolbar(_button("Erneut prüfen", self.refresh, "primary"),
                     _button("Sicherung erstellen", lambda: window.run_tool("create_backup", {})),
                     _button("Protokollordner öffnen", lambda: window.open_folder(self.app.settings.log_dir)))
        self.text = QPlainTextEdit()
        self.text.setObjectName("report")
        self.text.setReadOnly(True)
        self.body.addWidget(self.text, 1)

    def refresh(self):
        recent = self.app.episodes.recent(25)
        history = "\n".join(f"{e['created_at'].replace('T', ' ')}  {'✅' if e['ok'] == 1 else '❌' if e['ok'] == 0 else '•'} "
                            f"{e['summary']}" for e in recent)
        self.text.setPlainText(report(self.app) + "\n\nLetzte Ereignisse:\n" + (history or "–"))


# -------------------------------------------------------------- Einstellungen
class SettingsPage(Page):
    title = "⚙️ Einstellungen"
    hint = ("Gespeichert in config/settings.json. API-Schlüssel gehören nicht hierher, sondern in die Datei .env "
            "(Vorlage .env.example) – sie werden nie in Einstellungen gespeichert.")

    def __init__(self, window):
        super().__init__(window)
        s = self.app.settings
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.user_name = QLineEdit(s.user_name)
        self.user_name.setPlaceholderText("z. B. dein Vorname")
        self.address = QComboBox()
        self.address.addItems(["du", "Sie"])
        self.address.setCurrentText(s.address)
        self.order = QLineEdit(", ".join(s.provider_order))
        self.ollama_model = QLineEdit(s.ollama_model)
        self.anthropic_model = QLineEdit(s.anthropic_model)
        self.openai_model = QLineEdit(s.openai_model)
        self.approve = QComboBox()
        self.approve.addItems([f"{int(l)} – {LEVEL_LABELS[l]}" for l in (Level.READ, Level.SUGGEST, Level.PREPARE, Level.CHANGE)])
        self.approve.setCurrentIndex(max(0, min(3, s.auto_approve_level - 1)))
        self.share_docs = QCheckBox("Passende Dokumentauszüge auch an externe Modelle senden")
        self.share_docs.setChecked(s.share_documents_with_external_models)
        form.addRow("Wie soll CUDI dich nennen?", self.user_name)
        form.addRow("Anrede", self.address)
        form.addRow("Modell-Reihenfolge", self.order)
        form.addRow("Ollama-Modell (lokal)", self.ollama_model)
        form.addRow("Claude-Modell", self.anthropic_model)
        form.addRow("OpenAI-Modell", self.openai_model)
        form.addRow("Ohne Rückfrage bis Stufe", self.approve)
        form.addRow("Datenschutz", self.share_docs)
        self.body.addLayout(form)
        note = QLabel("Name, Anrede, Freigabestufe und Datenschutz gelten sofort. Änderungen an Modellen gelten nach "
                      "einem Neustart von CUDI.")
        note.setObjectName("pageHint")
        note.setWordWrap(True)
        self.body.addWidget(note)
        self.toolbar(_button("Speichern", self.save, "primary"))
        self.body.addStretch(1)

    def refresh(self):
        pass

    def save(self):
        s = self.app.settings
        s.user_name = self.user_name.text().strip()
        s.address = self.address.currentText()
        s.provider_order = [p.strip() for p in self.order.text().split(",") if p.strip()]
        s.ollama_model = self.ollama_model.text().strip() or s.ollama_model
        s.anthropic_model = self.anthropic_model.text().strip() or s.anthropic_model
        s.openai_model = self.openai_model.text().strip() or s.openai_model
        s.auto_approve_level = self.approve.currentIndex() + 1
        s.share_documents_with_external_models = self.share_docs.isChecked()
        warnings = s.validate()
        path = s.save()
        self.app.permissions.auto_approve_level = s.auto_approve_level
        self.order.setText(", ".join(s.provider_order))
        self.window_.notify(f"Gespeichert in {path.name}." + (" Hinweis: " + "; ".join(warnings) if warnings else ""))
