"""Zeitmessung je Stufe (Tempo): ehrlich messen, bevor optimiert wird.

`with zeiten.stufe("render"):` misst die EIGENE Zeit einer Stufe (verschachtelte Stufen werden abgezogen,
nichts doppelt gezählt). Die Summe je Auftrag steht in `ergebnis.json["zeiten"]` und im Prüfbericht („Zeiten“).
Läuft ein Auftrag in mehreren Prozessen (Schreibaufgabe → `--weiter`), addiert `laden`/`speichern` über
`zeiten.json` im Auftragsordner. Messen kostet nichts und ändert nie ein Ergebnis."""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

FILE = "zeiten.json"
_lock = threading.Lock()
_totals: dict[str, float] = {}
_counts: dict[str, int] = {}
_stack = threading.local()

LABELS = {
    "pakete": "Pakete installieren", "planen": "Thema planen (Wikidata/Claude)", "pruefen": "Abgleich mit Quellen",
    "vorrecherche": "Vorrecherche lesen (Cache statt Wikidata/Quellen)",
    "bilder": "Bilder/Clips suchen + Bildprüfung", "schreiben": "Texte bauen/Regie/Wahrheit (ohne Wartezeit auf Claude)",
    "tts": "Stimme (TTS)", "render": "Bilder zeichnen + Encode", "ton": "Ton mischen", "encode": "Zusammensetzen/Endencode",
    "qa": "Endkontrolle (qa/loudnorm)", "app": "App-Fassung (≤ 19 MB)", "sonst": "Sonstiges",
}


def reset() -> None:
    with _lock:
        _totals.clear()
        _counts.clear()


def _frames() -> list:
    if not hasattr(_stack, "frames"):
        _stack.frames = []
    return _stack.frames


@contextmanager
def stufe(name: str):
    """Misst die eigene Zeit von `name` (ohne verschachtelte Stufen)."""
    frames = _frames()
    frame = [time.perf_counter(), 0.0]          # Start, Zeit der inneren Stufen
    frames.append(frame)
    try:
        yield
    finally:
        frames.pop()
        total = time.perf_counter() - frame[0]
        if frames:
            frames[-1][1] += total
        add(name, total - frame[1])


def add(name: str, seconds: float, count: int = 1) -> None:
    with _lock:
        _totals[name] = _totals.get(name, 0.0) + max(0.0, seconds)
        _counts[name] = _counts.get(name, 0) + count


def snapshot() -> dict:
    with _lock:
        return {k: round(v, 1) for k, v in sorted(_totals.items(), key=lambda kv: -kv[1])}


def counts() -> dict:
    with _lock:
        return dict(_counts)


def laden(folder: Path) -> None:
    """Früher gemessene Zeiten dieses Auftrags übernehmen (Fortsetzen nach einer Schreibaufgabe)."""
    try:
        old = json.loads((Path(folder) / FILE).read_text("utf-8"))
    except (OSError, ValueError):
        return
    with _lock:
        for k, v in (old.get("sekunden") or {}).items():
            _totals[k] = _totals.get(k, 0.0) + float(v)
        for k, v in (old.get("anzahl") or {}).items():
            _counts[k] = _counts.get(k, 0) + int(v)


def speichern(folder: Path) -> None:
    try:
        (Path(folder) / FILE).write_text(json.dumps({"sekunden": snapshot(), "anzahl": counts()}, ensure_ascii=False), "utf-8")
    except OSError:
        pass


def bericht(folder: Path | None = None) -> dict:
    """Block für ergebnis.json: Sekunden je Stufe, Summe und Anzahl Schreibrunden (Warten auf Claude steht nicht darin)."""
    secs = snapshot()
    rounds = 0
    if folder:
        try:
            rounds = sum(1 for p in Path(folder).glob("schreiben_*.json"))
        except OSError:
            rounds = 0
    return {"sekunden": secs, "summe": round(sum(secs.values()), 1), "schreibaufgaben": rounds,
            "anzahl": counts()}


def review_section(block: dict) -> str:
    """Prüfbericht-Abschnitt „Zeiten“."""
    secs = block.get("sekunden") or {}
    if not secs:
        return ""
    total = block.get("summe") or sum(secs.values()) or 1
    lines = ["## Zeiten", "", "| Stufe | Sekunden | Anteil |", "|---|---:|---:|"]
    for k, v in secs.items():
        lines.append(f"| {LABELS.get(k, k)} | {v:.1f} | {v / total:.0%} |")
    lines.append(f"| **Summe (eigene Rechenzeit)** | **{total:.1f}** | |")
    lines += ["", f"Schreibaufgaben an Claude: {block.get('schreibaufgaben', 0)} Datei(en) "
                  "(jede Runde = ein Neustart des Laufs; die Wartezeit auf Claude steht nicht in der Tabelle)."]
    return "\n".join(lines) + "\n"


def pakete_aus_umgebung() -> None:
    """Zeit fürs Installieren, die scripts/cudi_auftrag.sh in CUDI_ZEIT_PAKETE (Sekunden) meldet."""
    raw = os.environ.pop("CUDI_ZEIT_PAKETE", "")
    try:
        if raw and float(raw) > 0:
            add("pakete", float(raw))
    except ValueError:
        pass
