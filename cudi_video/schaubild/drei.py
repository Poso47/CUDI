"""Echte 3D-Szenen für das Animationsstudio (kostenlos: three.js r128 im eingebauten Chromium, über Node + Playwright).

Die Zeitsteuerung bleibt in Python: `zeichnen.Buehne.zustand(t)` sagt für jedes Bild, wo was wie groß und wie sichtbar ist
(auch Kamera-Zoom und Figuren-Aktionen). `rendere()` schickt diese Zustände gebündelt an `drei/szene3d.html`, das sie mit
Licht, weichen Schatten, Glanz und leichter Kamerafahrt in 3D zeichnet, und bekommt PNG-Bilder + Bildschirmlage je Element
zurück (für die Beschriftungen, die Python wie bisher setzt). Fehlt Node/Chromium oder geht etwas schief, zeichnet der Aufrufer
die Szene in 2D (`CUDI_3D=0` schaltet 3D ab).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ORDNER = Path(__file__).resolve().parent / "drei"
THREE = Path(__file__).resolve().parent.parent / "data" / "three" / "three.min.js"
BILDRATE = 12                                     # 3D-Bilder je Sekunde (dazwischen wird gehalten) – spart Renderzeit
GROESSE = 600                                     # 3D-Kantenlänge; wird auf die Zielgröße skaliert
log = logging.getLogger(__name__)


def aktiv() -> bool:
    return os.environ.get("CUDI_3D", "1") != "0" and shutil.which("node") is not None and THREE.exists()


def _rgb(c) -> list[int]:
    return [int(v) for v in c][:3] if isinstance(c, (list, tuple)) else [200, 200, 200]


def _ref(v):
    return list(v) if isinstance(v, tuple) else v


def elemente(buehne) -> list[dict]:
    """Feste Angaben je Element (Anker schon aufgelöst) für die 3D-Bühne – Beschriftungen zeichnet Python."""
    out = []
    for eid in buehne.order:
        e = buehne.el[eid]
        if e["art"] == "beschriftung":
            continue
        d = {"id": eid, "art": e["art"], "farbe": _rgb(e.get("farbe")), "f": e.get("f", 0)}
        for k in ("form", "figur", "um", "anzahl", "durchsichtig", "blick", "streckung", "breite", "prozent", "objekt"):
            if e.get(k) is not None:
                d[k] = e[k]
        if e["art"] == "figur":
            from .zeichnen import figur_info
            plan = (figur_info(e.get("figur") or "") or {}).get("bauplan")
            if plan:
                d["bauplan"] = plan
        if e.get("punkte"):
            d["punkte"] = [list(p) for p in e["punkte"]]
        for k in ("von", "nach"):
            if e.get(k) is not None:
                d[k] = _ref(e[k])
        out.append(d)
    return out


def zustaende(buehne, zeiten: list[float]) -> list[dict]:
    from .zeichnen import KAMERA
    bilder = []
    for t in zeiten:
        st = buehne.zustand(t)
        bilder.append({"t": round(t, 3), "kamera": st[KAMERA], "st": {
            k: {"x": z["x"], "y": z["y"], "g": z["g"], "alpha": z["alpha"], "f": z["f"], "rot": z["rot"], "puls": z.get("puls", 0),
                "farbe": _rgb(z["farbe"]), "flattere": z.get("flattere", 0), "picke": z.get("picke", 0)}
            for k, z in st.items() if k != KAMERA}})
    return bilder


def rendere(buehne, zeiten: list[float], size: int = GROESSE, zeitlimit: int = 900) -> tuple[list[Path], list[dict], Path]:
    """3D-Bilder zu den Zeitpunkten. Rückgabe: (PNG-Pfade, Lage je Bild {id: [x, y, r]} in 0–100, Arbeitsordner)."""
    arbeit = Path(tempfile.mkdtemp(prefix="cudi3d_"))
    auftrag = arbeit / "auftrag.json"
    auftrag.write_text(json.dumps({"size": size, "elemente": elemente(buehne), "bilder": zustaende(buehne, zeiten),
                                   "dauer": max(zeiten) if len(zeiten) > 12 else 0}), "utf-8")
    lauf = subprocess.run(["node", str(ORDNER / "render3d.js"), str(auftrag), str(arbeit / "bilder")],
                          capture_output=True, text=True, timeout=zeitlimit)
    if lauf.returncode != 0:
        shutil.rmtree(arbeit, ignore_errors=True)
        raise RuntimeError((lauf.stderr or lauf.stdout or "3D-Renderer ohne Meldung").strip()[:400])
    lagen = json.loads((arbeit / "bilder" / "lage.json").read_text("utf-8"))
    pfade = [arbeit / "bilder" / f"b_{i:05d}.png" for i in range(len(zeiten))]
    return pfade, lagen, arbeit


PROTOKOLL = "_3d_protokoll.jsonl"


def _protokoll_datei() -> Path:
    from .. import config
    return config.OUTPUT_DIR / PROTOKOLL


def protokoll(ok: bool, grund: str = "") -> None:
    """Je Szene festhalten, ob sie in echtem 3D gerendert wurde (für die 3D-Abnahme im Ergebnis – nichts rutscht still durch)."""
    try:
        with open(_protokoll_datei(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ok": bool(ok), "grund": str(grund)[:160]}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def protokoll_nehmen() -> tuple[int, list[str]]:
    """(Anzahl 3D-Szenen, Gründe der flach gezeichneten Szenen) lesen und das Protokoll leeren."""
    datei, ok, fehl = _protokoll_datei(), 0, []
    try:
        for zeile in datei.read_text("utf-8").splitlines():
            eintrag = json.loads(zeile)
            if eintrag.get("ok"):
                ok += 1
            else:
                fehl.append(eintrag.get("grund") or "unbekannt")
        datei.unlink()
    except (OSError, ValueError):
        pass
    return ok, fehl


def abnahme() -> list[str]:
    """Hinweise der 3D-Abnahme: Ziel ist immer ein vollständiges 3D-Video."""
    ok, fehl = protokoll_nehmen()
    if not ok and not fehl:
        return []
    if not fehl:
        return [f"3D-Abnahme: alle {ok} animierten Szenen in echtem 3D."]
    gruende = "; ".join(sorted(set(fehl))[:3])
    return [f"3D-Abnahme NICHT vollständig: {len(fehl)} von {ok + len(fehl)} Szenen nur flach (2D) gezeichnet – {gruende}"]
