"""Neues Hauptfenster von CUDI: Navigation links, Inhalt rechts, nur echte Funktionen."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Dict

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QPlainTextEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from cudi.core.results import CONFIRM, ERROR, Result

from . import theme
from .chat_view import ChatView
from .pages import (DiagnosisPage, DocumentsPage, MemoryPage, ModelsPage, ProjectsPage, SettingsPage,
                    TasksPage, ToolsPage)

QUICK_PROMPTS = [
    ("Was kannst du?", "Was kannst du für mich tun?"),
    ("Projektstand", "/projektstand"),
    ("Offene Aufgaben", "/aufgaben"),
    ("Befehle", "/hilfe"),
]


class _Bridge(QObject):
    finished = Signal(object)


class ChatInput(QPlainTextEdit):
    """Mehrzeilige Eingabe: Enter sendet, Umschalt+Enter macht eine neue Zeile."""

    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class ChatPage(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__()
        self.setObjectName("page")
        self.window_ = window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("page")
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 14, 24, 10)
        title = QLabel(f"💬 {window.app.settings.assistant_name}")
        title.setObjectName("pageTitle")
        subtitle = QLabel("dein KI-Kollege")
        subtitle.setObjectName("pageHint")
        self.status = QLabel()
        self.status.setObjectName("statusPill")
        h.addWidget(title)
        h.addWidget(subtitle)
        h.addStretch(1)
        h.addWidget(self.status)
        new_chat = QPushButton("Neues Gespräch")
        new_chat.clicked.connect(window.new_conversation)
        h.addWidget(new_chat)
        layout.addWidget(header)

        self.view = ChatView()
        layout.addWidget(self.view, 1)

        chips = QHBoxLayout()
        chips.setContentsMargins(24, 6, 24, 0)
        for label, prompt in QUICK_PROMPTS:
            chip = QPushButton(label)
            chip.setObjectName("chip")
            chip.clicked.connect(lambda _=False, p=prompt: window.send(p))
            chips.addWidget(chip)
        chips.addStretch(1)
        layout.addLayout(chips)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(24, 8, 24, 16)
        bottom.setSpacing(8)
        self.input = ChatInput()
        self.input.setObjectName("chatInput")
        self.input.setPlaceholderText("Schreib CUDI eine Nachricht … (Enter = senden, Umschalt+Enter = neue Zeile)")
        self.input.setFixedHeight(72)
        self.input.submitted.connect(self.submit)
        self.send_button = QPushButton("Senden")
        self.send_button.setObjectName("primary")
        self.send_button.setMinimumHeight(40)
        self.send_button.clicked.connect(self.submit)
        bottom.addWidget(self.input, 1)
        bottom.addWidget(self.send_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(bottom)

    def submit(self) -> None:
        text = self.input.toPlainText().strip()
        if text:
            self.input.clear()
            self.window_.send(text)

    def refresh(self) -> None:
        self.input.setFocus()


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.busy = False
        self._bridge = _Bridge()
        self._bridge.finished.connect(self._on_result)
        self.setWindowTitle(f"{app.settings.assistant_name} – persönlicher KI-Kollege")
        self.setStyleSheet(theme.STYLESHEET)
        self._fit_to_screen()

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(200)
        self.stack = QStackedWidget()
        root.addWidget(self.nav)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.chat = ChatPage(self)
        self.pages: Dict[str, QWidget] = {}
        for key, label, page in (
            ("chat", "💬  Chat", self.chat),
            ("memory", "🧠  Gedächtnis", MemoryPage(self)),
            ("projects", "📁  Projekte", ProjectsPage(self)),
            ("tasks", "✅  Aufgaben", TasksPage(self)),
            ("documents", "📄  Dokumente", DocumentsPage(self)),
            ("models", "🤖  Modelle", ModelsPage(self)),
            ("tools", "🛠  Werkzeuge", ToolsPage(self)),
            ("diagnosis", "🩺  Diagnose", DiagnosisPage(self)),
            ("settings", "⚙️  Einstellungen", SettingsPage(self)),
        ):
            self.pages[key] = page
            self.stack.addWidget(page)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._switch)
        self.nav.setCurrentRow(0)

        self.update_model_status()
        self._welcome()

    # ------------------------------------------------------------ Aufbau
    def _fit_to_screen(self) -> None:
        """Startgröße passend zum Bildschirm (auch bei 125–150 % Skalierung)."""
        self.setMinimumSize(820, 560)
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1200, 800)
            return
        area = screen.availableGeometry()
        width = min(1400, int(area.width() * 0.85))
        height = min(900, int(area.height() * 0.85))
        self.resize(max(820, width), max(560, height))
        self.move(area.x() + (area.width() - self.width()) // 2, area.y() + (area.height() - self.height()) // 2)

    def _welcome(self) -> None:
        name = self.app.settings.user_name
        greeting = f"Hallo{(' ' + name) if name else ''}! Ich bin bereit."
        if self.app.models.has_model():
            text = f"{greeting} Sag mir einfach, woran wir arbeiten – ich erinnere mich an das, was du mir anvertraust."
        else:
            text = (f"{greeting} Es ist noch kein Sprachmodell verbunden – Gedächtnis, Projekte, Dokumente und "
                    "Befehle funktionieren trotzdem. Unter „🤖 Modelle“ steht, wie du in zwei Minuten eins anschließt.")
        project = self.app.projects.active()
        if project:
            text += f"\n\nAktives Projekt: **{project['name']}** – frag mich „Wo waren wir?“."
        self.chat.view.add_cudi(text, self.app.settings.assistant_name)

    def _switch(self, row: int) -> None:
        self.stack.setCurrentIndex(row)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def show_page(self, key: str) -> None:
        keys = list(self.pages)
        if key in keys:
            self.nav.setCurrentRow(keys.index(key))

    def update_model_status(self) -> None:
        available = [(n, info) for n, ok, info in self.app.models.status() if ok]
        if available:
            name = available[0][0]
            external = self.app.models.providers[name].external
            self.chat.status.setText(f"● {name} ({'extern' if external else 'lokal'})")
            self.chat.status.setStyleSheet(f"background: #12261e; color: {theme.GREEN};")
            self.chat.status.setToolTip(available[0][1])
        else:
            self.chat.status.setText("● kein Sprachmodell")
            self.chat.status.setStyleSheet(f"background: #2d230f; color: {theme.ORANGE};")
            self.chat.status.setToolTip("Unter „Modelle“ steht, wie du eins anschließt.")

    # --------------------------------------------------------- Kern-Aufrufe
    def send(self, text: str) -> None:
        if self.busy:
            self.notify("Einen Moment – ich arbeite noch an der vorherigen Anfrage.")
            return
        self.show_page("chat")
        self.chat.view.add_user(text)
        self._run(lambda: self.app.handle(text))

    def run_command(self, command: str) -> None:
        """Befehl aus einem Bereich ausführen; das Ergebnis erscheint im Chat und als Hinweis."""
        if self.busy:
            self.notify("Einen Moment – ich arbeite noch an der vorherigen Anfrage.")
            return
        self._run(lambda: self.app.handle(command))

    def run_tool(self, name: str, args: dict) -> None:
        if self.busy:
            self.notify("Einen Moment – ich arbeite noch an der vorherigen Anfrage.")
            return
        self._run(lambda: self.app.orchestrator.run_tool(name, args))

    def _run(self, job: Callable[[], Result]) -> None:
        self.busy = True
        self.chat.send_button.setEnabled(False)
        self.chat.view.set_typing(True, self.app.settings.assistant_name)

        def worker():
            try:
                result = job()
            except Exception as e:  # sichtbar machen, nie verschweigen
                result = Result(ERROR, f"Interner Fehler: {e}")
            self._bridge.finished.emit(result)

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, result: Result) -> None:
        self.busy = False
        self.chat.send_button.setEnabled(True)
        self.chat.view.set_typing(False)
        footer_lines = [a.line() for a in result.actions
                        if a.status != "ausgeführt" or a.summary.strip() not in result.text]
        if result.sources:
            footer_lines.append("Quellen: " + "; ".join(dict.fromkeys(result.sources)))
        if result.details:
            footer_lines.append(f"Technische Details: {result.details}")
        self.chat.view.add_cudi(result.text, self.app.settings.assistant_name, result.model, "\n".join(footer_lines))

        on_chat = self.stack.currentWidget() is self.chat
        if not on_chat:
            first_line = result.text.strip().splitlines()[0] if result.text.strip() else ""
            self.notify(first_line[:160])
            page = self.stack.currentWidget()
            if hasattr(page, "refresh"):
                page.refresh()
        if result.kind == CONFIRM and result.pending_id:
            self._confirm(result)

    def _confirm(self, result: Result) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Freigabe erforderlich")
        box.setIcon(QMessageBox.Icon.Question)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(result.text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText("Ja, ausführen")
        box.button(QMessageBox.StandardButton.No).setText("Nein")
        remember = QCheckBox("Dieses Werkzeug bis zum Neustart ohne Rückfrage erlauben")
        box.setCheckBox(remember)
        approved = box.exec() == QMessageBox.StandardButton.Yes
        if result.pending_id not in self.app.orchestrator.pending:
            return  # inzwischen per Chat beantwortet
        self.chat.view.add_user("Ja" if approved else "Nein")
        pending_id = result.pending_id
        self._run(lambda: self.app.resolve(pending_id, approved, remember.isChecked()))

    # ------------------------------------------------------------- Sonstiges
    def new_conversation(self) -> None:
        self.app.orchestrator.new_conversation()
        self.chat.view.clear()
        self.chat.view.add_notice("Neues Gespräch – Gedächtnis und Projekte bleiben erhalten.")

    def notify(self, text: str) -> None:
        self.statusBar().showMessage(text, 8000)

    @staticmethod
    def open_folder(path: Path) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def run(app=None) -> int:
    """Startet das Fenster (für main.py)."""
    import sys

    from PySide6.QtWidgets import QApplication

    from cudi.core.application import get_app

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setStyle("Fusion")
    window = MainWindow(app or get_app())
    window.show()
    return qt_app.exec()
