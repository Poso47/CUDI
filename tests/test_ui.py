"""Tests für das neue Hauptfenster (laufen ohne Bildschirm im Offscreen-Modus)."""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from conftest import FakeProvider, tool_call  # noqa: E402
from ui.chat_view import to_html  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def wait_idle(qt_app, window, timeout=5.0):
    deadline = time.time() + timeout
    while window.busy and time.time() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    qt_app.processEvents()
    assert not window.busy, "Antwort des Kerns kam nicht an"


def bubble_texts(window):
    return [label.text() for bubble in window.chat.view._bubbles for label, _ in bubble._parts]


def test_html_is_escaped_and_code_blocks_are_rendered():
    html = to_html("<script>x</script>\n```python\nprint('a < b')\n```\nfertig")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<pre" in html and "a &lt; b" in html


def test_chat_roundtrip_and_all_pages_render(qt_app, make_app):
    app = make_app({"fake": FakeProvider(["Hallo! Woran arbeiten wir heute?"])})
    window = MainWindow(app)
    window.resize(1280, 720)
    window.show()
    window.send("Hallo CUDI.")
    wait_idle(qt_app, window)
    assert any("Woran arbeiten wir heute?" in t for t in bubble_texts(window))
    assert "fake" in window.chat.status.text()
    for key in window.pages:
        window.show_page(key)
        qt_app.processEvents()
    window.close()


def test_confirmation_dialog_approves_file_write(qt_app, make_app, monkeypatch):
    fake = FakeProvider([tool_call("write_file", path="notiz.txt", content="Hallo"), "Gespeichert."])
    app = make_app({"fake": fake})
    window = MainWindow(app)
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda self: QtWidgets.QMessageBox.StandardButton.Yes)
    window.send("Schreib Hallo in die Datei notiz.txt")
    wait_idle(qt_app, window)   # Antwort mit Freigabefrage -> Dialog -> Ja
    wait_idle(qt_app, window)   # Ausführung nach Freigabe
    assert (app.settings.workspace_dir / "notiz.txt").read_text() == "Hallo"
    window.close()


def test_bubbles_fit_text_and_window(qt_app, make_app):
    window = MainWindow(make_app())
    window.resize(1600, 900)
    window.show()
    qt_app.processEvents()
    window.chat.view.add_user("Kurz")
    window.chat.view.add_cudi("Ein deutlich längerer Text " * 40)
    qt_app.processEvents()
    short, long_ = window.chat.view._bubbles[-2], window.chat.view._bubbles[-1]
    assert short.width() < 250                       # kurze Nachricht = schmale Blase
    assert 500 < long_.width() <= 820                # lange Nachricht = begrenzte, lesbare Breite
    label = long_._parts[-1][0]
    assert long_.height() >= label.heightForWidth(label.width())  # nichts abgeschnitten
    window.close()


def test_settings_page_saves_without_api_keys(qt_app, make_app):
    app = make_app()
    window = MainWindow(app)
    page = window.pages["settings"]
    page.user_name.setText("Can")
    page.address.setCurrentText("Sie")
    page.save()
    stored = app.settings.settings_file.read_text(encoding="utf-8")
    assert '"user_name": "Can"' in stored and '"address": "Sie"' in stored
    assert "api_key" not in stored
    window.close()
