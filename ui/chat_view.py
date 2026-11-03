"""Chat-Ansicht mit Sprechblasen (umbrechend, auswählbar, Codeblöcke)."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from . import theme

_CODE_BLOCK = re.compile(r"```[\w+-]*\n?(.*?)```", re.S)


def to_html(text: str) -> str:
    """Einfache, sichere Umwandlung: Codeblöcke, Inline-Code, **fett**, Zeilenumbrüche."""
    parts: List[str] = []
    pos = 0
    for match in _CODE_BLOCK.finditer(text):
        parts.append(_inline(text[pos:match.start()].rstrip("\n")))
        code = html.escape(match.group(1).rstrip("\n"))
        parts.append(
            f"<pre style='background:{theme.BG}; color:{theme.TEXT}; padding:8px; "
            f"font-family:Consolas,\"DejaVu Sans Mono\",monospace; white-space:pre-wrap;'>{code}</pre>"
        )
        pos = match.end()
        while pos < len(text) and text[pos] == "\n":
            pos += 1
    parts.append(_inline(text[pos:]))
    return "".join(parts)


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`\n]+)`", r"<code style='background:#0d1117;'>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", escaped)
    return escaped.replace("\n", "<br>")


MAX_BUBBLE_WIDTH = 820  # gut lesbare Zeilenlänge, auch auf großen Bildschirmen
COLUMN_MAX_WIDTH = 1180  # Verlauf auf breiten Bildschirmen als zentrierte Spalte


class Bubble(QFrame):
    def __init__(self, text: str, from_user: bool, caption: str = "", footer: str = ""):
        super().__init__()
        self.setObjectName("bubbleUser" if from_user else "bubbleCudi")
        self._parts: List[tuple] = []  # (Label, Rohtext) – Rohtext zum Messen der natürlichen Breite
        self._has_code = "```" in text
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)
        if caption:
            self._add(layout, caption, f"color: {'#cfe1ff' if from_user else theme.MUTED}; font-size: 9pt;")
        self._add(layout, text, f"color: {'white' if from_user else theme.TEXT};")
        if footer:
            self._add(layout, footer, f"color: {theme.MUTED}; font-size: 9.5pt;")

    def _add(self, layout: QVBoxLayout, raw: str, style: str) -> None:
        label = QLabel(to_html(raw))
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet(style)
        layout.addWidget(label)
        self._parts.append((label, raw.replace("**", "").replace("`", "")))

    def natural_width(self) -> int:
        """Breite, die der Text ohne Umbruch bräuchte (plus Innenabstand und kleine Reserve)."""
        widest = 0
        for label, raw in self._parts:
            label.ensurePolished()  # Schriftgröße aus dem Stylesheet übernehmen
            metrics = label.fontMetrics()
            for line in raw.splitlines() or [""]:
                widest = max(widest, metrics.horizontalAdvance(line))
        return int(widest * 1.04) + 28 + 16

    def fit(self, available: int) -> None:
        """Breite an Text und Fenster anpassen, Höhe passend zur Breite setzen."""
        limit = max(220, min(MAX_BUBBLE_WIDTH, int(available * 0.82)))
        width = limit if self._has_code else min(limit, self.natural_width())
        self.setFixedWidth(width)
        height = self.layout().totalHeightForWidth(width)
        if height > 0:
            self.setFixedHeight(height)


class ChatView(QScrollArea):
    """Scrollbarer Verlauf. Nachrichten werden unten angehängt, Ansicht folgt automatisch."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("chatScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("chatContainer")
        outer = QHBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        column = QWidget()
        column.setObjectName("chatContainer")
        column.setMaximumWidth(COLUMN_MAX_WIDTH)
        outer.addStretch(1)
        outer.addWidget(column, 100)
        outer.addStretch(1)
        self._layout = QVBoxLayout(column)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)
        self._layout.addStretch(1)
        self.setWidget(container)
        self._typing: Optional[QWidget] = None
        self._bubbles: List[Bubble] = []
        self.verticalScrollBar().rangeChanged.connect(self._scroll_to_end)

    def _available(self) -> int:
        return max(300, min(self.viewport().width(), COLUMN_MAX_WIDTH) - 32)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt-Name)
        super().resizeEvent(event)
        available = self._available()
        for bubble in self._bubbles:
            bubble.fit(available)

    def _scroll_to_end(self, *_):
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def _row(self, widget: QWidget, from_user: bool) -> QWidget:
        row = QWidget()
        # Zeilen nie strecken – freier Platz gehört ans Ende, nicht zwischen die Nachrichten
        row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        if from_user:
            h.addStretch(1)
            h.addWidget(widget)
        else:
            h.addWidget(widget)
            h.addStretch(1)
        return row

    def _add_bubble(self, bubble: Bubble, from_user: bool) -> None:
        self._bubbles.append(bubble)
        self._insert(self._row(bubble, from_user))
        # Erst jetzt hängt die Blase im Fenster und kennt ihre endgültige Schrift (Stylesheet)
        bubble.fit(self._available())

    def add_user(self, text: str) -> None:
        self._add_bubble(Bubble(text, True, f"Du · {datetime.now():%H:%M}"), True)

    def add_cudi(self, text: str, name: str = "CUDI", model: Optional[str] = None,
                 footer: str = "") -> None:
        caption = f"{name} · {datetime.now():%H:%M}" + (f" · {model}" if model else "")
        self._add_bubble(Bubble(text, False, caption, footer), False)

    def add_notice(self, text: str) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {theme.MUTED}; font-size: 9.5pt; padding: 4px;")
        self._insert(label)

    def set_typing(self, active: bool, name: str = "CUDI") -> None:
        if active and self._typing is None:
            self._typing = QLabel(f"{name} denkt nach …")
            self._typing.setStyleSheet(f"color: {theme.MUTED}; font-style: italic; padding-left: 6px;")
            self._insert(self._typing)
        elif not active and self._typing is not None:
            self._typing.deleteLater()
            self._typing = None

    def clear(self) -> None:
        self._bubbles.clear()
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._typing = None

    def _insert(self, widget: QWidget) -> None:
        # vor dem Stretch am Ende einfügen; Tipp-Anzeige bleibt immer ganz unten
        index = self._layout.count() - 1
        if self._typing is not None and widget is not self._typing:
            index = self._layout.indexOf(self._typing)
        self._layout.insertWidget(index, widget)
        QTimer.singleShot(0, self._scroll_to_end)
