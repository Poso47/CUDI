"""Einheitliches dunkles Design für CUDI.

Wichtig: Selektoren sind gezielt (Objektnamen/Klassen). Ein pauschales ``QFrame { padding… }``
würde in Qt auch jede Beschriftung (QLabel erbt von QFrame) treffen – genau das hat die alte
Oberfläche unlesbar gemacht.
"""

BG = "#0d1117"
PANEL = "#161b22"
PANEL_2 = "#1c2230"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#2f81f7"
ACCENT_DARK = "#1f6feb"
GREEN = "#3fb950"
ORANGE = "#d29922"
RED = "#f85149"
USER_BUBBLE = "#1f6feb"
CUDI_BUBBLE = "#21262d"

STYLESHEET = f"""
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ color: {TEXT}; font-size: 10.5pt; }}
QWidget#page, QScrollArea#chatScroll, QWidget#chatContainer {{ background: {BG}; }}

QListWidget#nav {{
    background: {PANEL}; border: none; border-right: 1px solid {BORDER};
    padding: 8px 6px; outline: 0;
}}
QListWidget#nav::item {{ padding: 10px 12px; margin: 2px 0; border-radius: 6px; color: {TEXT}; }}
QListWidget#nav::item:hover {{ background: {PANEL_2}; }}
QListWidget#nav::item:selected {{ background: {ACCENT_DARK}; color: white; }}

QLabel#pageTitle {{ font-size: 16pt; font-weight: 600; }}
QLabel#pageHint, QLabel#caption {{ color: {MUTED}; }}
QLabel#statusPill {{ border-radius: 10px; padding: 3px 10px; font-size: 9.5pt; }}

QFrame#bubbleUser {{ background: {USER_BUBBLE}; border-radius: 12px; }}
QFrame#bubbleCudi {{ background: {CUDI_BUBBLE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#bubbleUser QLabel, QFrame#bubbleCudi QLabel {{ background: transparent; border: none; }}
QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; }}

QPlainTextEdit, QTextEdit, QLineEdit, QComboBox, QSpinBox {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px;
    selection-background-color: {ACCENT_DARK};
}}
QPlainTextEdit:focus, QTextEdit:focus, QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QPlainTextEdit#chatInput {{ font-size: 11pt; }}
QPlainTextEdit#report {{ font-family: Consolas, "Cascadia Mono", "DejaVu Sans Mono", monospace; font-size: 10pt; }}

QPushButton {{
    background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 6px; padding: 7px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {MUTED}; }}
QPushButton#primary {{ background: {ACCENT_DARK}; border-color: {ACCENT_DARK}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT}; }}
QPushButton#chip {{ border-radius: 14px; padding: 5px 12px; color: {MUTED}; }}
QPushButton#chip:hover {{ color: {TEXT}; }}
QPushButton#danger:hover {{ border-color: {RED}; color: {RED}; }}

QTableWidget {{
    background: {PANEL}; alternate-background-color: {PANEL_2}; border: 1px solid {BORDER};
    border-radius: 6px; gridline-color: {BORDER};
}}
QTableWidget::item {{ padding: 4px; }}
QTableWidget::item:selected {{ background: {ACCENT_DARK}; }}
QHeaderView::section {{ background: {PANEL_2}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER}; padding: 6px; }}
QListWidget {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px; }}
QListWidget::item {{ padding: 6px; }}
QListWidget::item:selected {{ background: {ACCENT_DARK}; }}

QCheckBox {{ spacing: 8px; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolTip {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER}; }}
QMessageBox QLabel {{ min-width: 360px; }}
"""
