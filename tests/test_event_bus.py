"""Tests für cudi_event_bus: Start darf den aufrufenden (GUI-)Thread nicht blockieren."""

import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cudi_event_bus import CUDIEventBus  # noqa: E402


def _start_with_timeout(bus, timeout=5.0):
    """Ruft start_sync in einem Hilfsthread auf und meldet, ob es zurückkehrt."""
    done = threading.Event()

    def _call():
        bus.start_sync()
        done.set()

    threading.Thread(target=_call, daemon=True).start()
    return done.wait(timeout)


ROOT = Path(__file__).resolve().parent.parent


def test_start_sync_returns_in_main_thread():
    """Die GUI ruft start_sync() im Hauptthread auf – dort trat der Start-Hänger auf."""
    script = (
        "from cudi_event_bus import CUDIEventBus\n"
        "bus = CUDIEventBus()\n"
        "bus.start_sync()\n"
        "assert bus.running\n"
        "bus.stop_sync()\n"
        "print('OK')\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=ROOT,
            capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError("start_sync() blockiert den Hauptthread")
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_emit_sync_reaches_subscriber():
    bus = CUDIEventBus()
    received = []
    bus.subscribe("ACTION_*", lambda event: received.append(event.event_type))
    try:
        assert _start_with_timeout(bus)
        bus.emit_sync("ACTION_START", {"action": "test"})
        deadline = time.time() + 5
        while not received and time.time() < deadline:
            time.sleep(0.05)
        assert received == ["ACTION_START"]
    finally:
        bus.stop_sync()


def test_stop_sync_ends_worker_thread():
    bus = CUDIEventBus()
    assert _start_with_timeout(bus)
    bus.stop_sync()
    assert not bus.running
    assert bus._thread is None or not bus._thread.is_alive()
