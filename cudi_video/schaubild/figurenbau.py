"""Figuren-Abteilung: fehlende Figuren im Detail bauen – wie die Biene, nie aus Grundkörpern zusammengepuzzelt.

Ablauf (Anleitung für die Figuren-Sitzung: docs/gehirn/figurenbau.md):
  1. `python -m cudi_video figur-vorlage "Imker (beekeeper)"` – Crawler holt die beste Ganzkörper-Vorlage (nur zum Ansehen).
  2. Claude schreibt die Figur als three.js-Code (Funktionskörper, gleiche Helfer wie in szene3d.html) in eine .js-Datei.
  3. `python -m cudi_video figur-probe <name> <datei.js>` – Probe-Render aus 4 Richtungen + 2 Bewegungsmomenten neben der
     Vorlage, Ankerpunkte eingezeichnet. Nachbessern, bis Form, Farben und Teile zur Vorlage passen.
  4. `python -m cudi_video figur-ablegen <name> <datei.js> --anker '{...}'` – prüft und schreibt den Lernstand
     (Feld `figuren_code`); die Sitzung legt ihn per ArtifactData unter „studio/lernstand“ ab. Ab dann laden alle Video-Läufe
     die Figur automatisch (`zeichnen.figur_info` -> `drei.elemente` -> szene3d `ausCode`).
Fremde Fotos/Modelle sind nur Vorlage: Sie landen nie im Video oder im Repo.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import config

GROESSE = 400                                             # Figurenraum wie bei den handgebauten Figuren (fp: 0–400)
CODE_MAX = 60_000                                          # Zeichen je Figur (die Biene hat ~9 000)
MAX_FIGUREN = 40
MIN_ANKER = 3
VERBOTEN = re.compile(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|importScripts|require|eval|Function|localStorage|"
                      r"sessionStorage|indexedDB|navigator|postMessage|setTimeout|setInterval|location|cookie|"
                      r"document\.write)\b|\bimport\s*\(|\bwindow\s*\[")
PFLICHT = re.compile(r"\breturn\s*\{[^}]*\bg\b")
PROBE_ANSICHTEN = ((0, 2.0), (45, 2.0), (90, 2.0), (180, 2.0), (0, 2.6), (315, 3.1))   # (Winkel, Zeitpunkt)
MIN_RUNDEN = 3                                             # so oft muss die Figur geprobt und verglichen worden sein
MINDEST = {"teile": 35, "materialien": 5, "texturiert": 3, "organisch": 6}   # Detailgrad wie die Biene (nie gepuzzelt)


def ordner() -> Path:
    return config.OUTPUT_DIR / "figurenbau"


def _name(roh) -> str:
    from .werkstatt import _name as wname
    return wname(roh)


def pruefe_code(code: str) -> str | None:
    """Fehlertext oder None. Der Code ist ein Funktionskörper, der {g, teile, glieder} zurückgibt."""
    if not isinstance(code, str) or not code.strip():
        return "Code fehlt."
    if len(code) > CODE_MAX:
        return f"Code zu lang ({len(code)} > {CODE_MAX} Zeichen)."
    treffer = VERBOTEN.search(code)
    if treffer:
        return f"Nicht erlaubt im Figuren-Code: „{treffer.group(0)}“ (nur Geometrie, Materialien und Helfer der Bühne)."
    if not PFLICHT.search(code):
        return "Der Code muss mit „return { g, teile, glieder }“ enden (g = THREE.Group der Figur)."
    if shutil.which("node"):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write("(function () {\n" + code + "\n});\n")
        try:
            lauf = subprocess.run(["node", "--check", fh.name], capture_output=True, text=True, timeout=30)
        finally:
            Path(fh.name).unlink(missing_ok=True)
        if lauf.returncode != 0:
            zeilen = [z for z in (lauf.stderr or "").splitlines() if z.strip()]
            return "Syntaxfehler: " + " | ".join(zeilen[:4])[:300]
    return None


def pruefe_anker(anker) -> tuple[dict, str | None]:
    """Ankerpunkte {teil: [x, y]} im Figurenraum 0–400 (x nach rechts, y nach unten)."""
    if not isinstance(anker, dict):
        return {}, "Anker fehlen (JSON-Objekt {\"kopf\": [200, 90], …})."
    out = {}
    for k, v in anker.items():
        k = _name(k)
        if k and isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(z, (int, float)) and 0 <= z <= GROESSE for z in v):
            out[k] = [round(float(v[0]), 1), round(float(v[1]), 1)]
    if len(out) < MIN_ANKER:
        return out, f"Mindestens {MIN_ANKER} gültige Anker nötig (Werte 0–{GROESSE}), damit Beschriftungen genau zeigen."
    return out, None


def _lernstand() -> dict:
    from .. import animation
    return animation._lies(animation.lernstand_datei())


def _lokal(name: str) -> dict | None:
    datei = ordner() / "code" / f"{name}.json"
    try:
        return json.loads(datei.read_text("utf-8")) if datei.exists() else None
    except (OSError, ValueError):
        return None


def alle() -> dict[str, dict]:
    """Alle Code-Figuren: aus dem Lernstand früherer Läufe, in diesem Lauf abgelegte gewinnen."""
    out = {k: v for k, v in (_lernstand().get("figuren_code") or {}).items() if isinstance(v, dict)}
    code_dir = ordner() / "code"
    if code_dir.exists():
        for datei in sorted(code_dir.glob("*.json")):
            fig = _lokal(datei.stem)
            if fig:
                out[datei.stem] = fig
    return out


def info(name: str) -> dict | None:
    """Wie `zeichnen.figur_info`, für Code-Figuren (ohne Ebenen-Bilder, dafür mit „code“)."""
    n = _name(name)
    fig = _lokal(n) or (_lernstand().get("figuren_code") or {}).get(n) if n else None
    if not isinstance(fig, dict) or pruefe_code(fig.get("code", "")) or pruefe_anker(fig.get("anker"))[1]:
        return None
    return {"name": fig.get("name") or n, "ebenen": [], "groesse": GROESSE, "versteckt": [], "mit_kopf": [], "drehpunkte": {},
            "anker": fig["anker"], "nur3d": True, "code": fig["code"], "vorlage": fig.get("vorlage") or {}, "ordner": None}


def vorlage(wunsch: str) -> dict:
    """Crawler: beste Ganzkörper-Vorlage für einen Figur-Wunsch („Imker (beekeeper)“) in den Arbeitsordner kopieren."""
    from . import werkstatt

    name, anzeige, begriff = werkstatt.wunsch(wunsch)
    if not name or not begriff:
        raise ValueError("Figur-Wunsch unverständlich – Form „Deutsch (english)“, z. B. „Imker (beekeeper)“.")
    fund = werkstatt.vorlage_suchen(begriff)
    if not fund:
        raise RuntimeError(f"Keine passende Ganzkörper-Vorlage für „{begriff}“ gefunden – anderen englischen Begriff versuchen.")
    ziel = ordner() / "vorlagen" / name
    ziel.mkdir(parents=True, exist_ok=True)
    bild = ziel / ("vorlage" + (Path(fund["datei"]).suffix or ".jpg"))
    shutil.copyfile(fund["datei"], bild)
    fund = dict(fund, datei=str(bild), name=name, anzeige=anzeige)
    (ziel / "vorlage.json").write_text(json.dumps(fund, ensure_ascii=False, indent=1), "utf-8")
    return fund


def _vorlage_von(name: str) -> dict:
    try:
        return json.loads((ordner() / "vorlagen" / name / "vorlage.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _code_id(code: str) -> str:
    import hashlib
    return hashlib.sha1(code.encode("utf-8")).hexdigest()[:12]


def probe_stand(name: str) -> dict:
    try:
        return json.loads((ordner() / "proben" / f"{_name(name)}.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def maengel(stats: dict) -> list[str]:
    """Was der Figur zum Detailgrad der Biene fehlt (leer = genug)."""
    namen = {"teile": "Einzelteile", "materialien": "Materialien", "texturiert": "Materialien mit Textur/Relief",
             "organisch": "organische Formen (organ/koerper/Lathe/Tube)"}
    out = [f"zu wenige {namen[k]}: {stats.get(k, 0)} statt mindestens {v}" for k, v in MINDEST.items() if stats.get(k, 0) < v]
    if stats.get("grundkoerper", 0) > max(6, stats.get("teile", 0) * .3):
        out.append(f"zu viele Kästen/Zylinder/Kegel ({stats['grundkoerper']}) – wirkt gepuzzelt, organische Formen nehmen")
    return out


def probe(name: str, code: str, anker: dict | None = None, size: int = 380) -> Path:
    """Probe-Render der Code-Figur aus mehreren Richtungen neben der Vorlage -> Bilderbogen (JPG). Fehler im Code = Ausnahme
    mit der Meldung des Browsers (streng: kein stiller Ersatz)."""
    from PIL import Image, ImageDraw

    from . import drei

    fehler = pruefe_code(code)
    if fehler:
        raise ValueError(fehler)
    n = _name(name)
    arbeit = Path(tempfile.mkdtemp(prefix="cudifig_"))
    try:
        st = {"m": {"x": 50, "y": 50, "g": 70.0, "alpha": 1, "f": 0, "rot": 0, "puls": 0, "farbe": [200, 200, 200],
                    "flattere": .6, "picke": 0}}
        auftrag = {"size": size, "dauer": 0, "streng": True,
                   "elemente": [{"id": "m", "art": "figur", "figur": n, "farbe": [200, 200, 200], "f": 0, "figur_code": code,
                                 **({"anker_probe": anker} if anker else {})}],
                   "bilder": [{"t": t, "kamera": {"x": 50, "y": 50, "f": 1}, "st": st, "probe": w} for w, t in PROBE_ANSICHTEN]}
        kx, ky = (anker or {}).get("kopf") or (anker or {}).get("gesicht") or [200, 120]   # Nahaufnahme: Kopf/Gesicht im Detail
        auftrag["bilder"].append({"t": 2.0, "kamera": {"x": 50 + (kx / GROESSE - .5) * 70, "y": 50 + (ky / GROESSE - .5) * 70, "f": 2.6},
                                  "st": st, "probe": 0})
        (arbeit / "auftrag.json").write_text(json.dumps(auftrag), "utf-8")
        lauf = subprocess.run(["node", str(drei.ORDNER / "render3d.js"), str(arbeit / "auftrag.json"), str(arbeit / "bilder")],
                              capture_output=True, text=True, timeout=300)
        if lauf.returncode != 0:
            raise RuntimeError("Probe-Render fehlgeschlagen: " + (lauf.stderr or lauf.stdout or "ohne Meldung").strip()[:600])
        lagen = json.loads((arbeit / "bilder" / "lage.json").read_text("utf-8"))
        ansichten = [Image.open(arbeit / "bilder" / f"b_{i:05d}.png").convert("RGBA").copy() for i in range(len(auftrag["bilder"]))]
    finally:
        shutil.rmtree(arbeit, ignore_errors=True)
    if anker:                                               # Anker auf der Vorderansicht: zeigen Pfeile/Beschriftungen genau?
        d = ImageDraw.Draw(ansichten[0])
        for teil, (px, py) in (lagen[0].get("_anker") or {}).items():
            px, py = px / 100 * size, py / 100 * size
            d.ellipse((px - 5, py - 5, px + 5, py + 5), outline=(230, 30, 60, 255), width=2)
            d.text((px + 7, py - 7), teil, fill=(230, 30, 60, 255))
    stats = lagen[0].get("_stats") or {}
    alt = probe_stand(n)
    stand = {"runden": int(alt.get("runden", 0)) + 1, "code": _code_id(code), "stats": stats, "maengel": maengel(stats)}
    (ordner() / "proben").mkdir(parents=True, exist_ok=True)
    (ordner() / "proben" / f"{n}.json").write_text(json.dumps(stand, ensure_ascii=False), "utf-8")
    spalten, kante = 5, size
    vorlage_bild = None
    v = _vorlage_von(n)
    if v.get("datei") and Path(v["datei"]).exists():
        with Image.open(v["datei"]) as im:
            im = im.convert("RGB")
            im.thumbnail((kante, kante * 2))
            vorlage_bild = im.copy()
    breite = kante * spalten
    hoehe = kante * 2 + 34
    bogen = Image.new("RGB", (breite, hoehe), (238, 234, 226))
    d = ImageDraw.Draw(bogen)
    x0 = 0
    if vorlage_bild:
        bogen.paste(vorlage_bild, (0, 34 + (kante * 2 - vorlage_bild.height) // 2))
        d.text((8, 10), "Vorlage (nur zum Ansehen)", fill=(40, 40, 40))
        x0 = 1
    plaetze = [(c, r) for r in range(2) for c in range(x0, spalten)]
    titel = [f"{w}° · t={t}s" for w, t in PROBE_ANSICHTEN] + ["Nahaufnahme Kopf"]
    for (c, r), bild, beschr in zip(plaetze, ansichten, titel):
        feld = Image.new("RGBA", (kante, kante), (250, 248, 244, 255))
        feld.alpha_composite(bild.resize((kante, kante)))
        bogen.paste(feld.convert("RGB"), (c * kante, 34 + r * kante))
        d.text((c * kante + 8, 34 + r * kante + 6), beschr.replace("°", " Grad"), fill=(90, 90, 90))
    kurz = ", ".join(f"{k} {stats.get(k, 0)}" for k in ("teile", "materialien", "texturiert", "organisch", "grundkoerper"))
    d.text((x0 * kante + 8, 6), f"Figur '{n}' - Probe {stand['runden']} (Anker rot) - {kurz}", fill=(40, 40, 40))
    d.text((x0 * kante + 8, 20), ("FEHLT: " + "; ".join(stand["maengel"]))[:230] if stand["maengel"] else "Detailgrad erreicht",
           fill=(180, 30, 40) if stand["maengel"] else (30, 120, 60))
    ziel = ordner() / "proben" / f"{n}.jpg"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    bogen.save(ziel, quality=88)
    return ziel


def ablegen(name: str, code: str, anker: dict, anzeige: str = "", pruefen: bool = True) -> Path:
    """Geprüfte Figur ablegen: lokal (für diesen Lauf) und im Lernstand (für alle späteren Läufe) -> Pfad der Lernstand-Datei,
    die die Sitzung per ArtifactData unter „studio/lernstand“ speichert."""
    fehler = pruefe_code(code)
    anker, fehler_anker = pruefe_anker(anker)
    if fehler or fehler_anker:
        raise ValueError(fehler or fehler_anker)
    n = _name(name)
    if not n:
        raise ValueError("Figurname fehlt.")
    if pruefen:                                             # Qualitätsschleife: genug Runden, genau dieser Code geprobt, Detailgrad erreicht
        stand = probe_stand(n)
        if stand.get("code") != _code_id(code):
            raise ValueError("Genau dieser Code wurde noch nicht geprobt – erst figur-probe, ansehen, dann ablegen.")
        if int(stand.get("runden", 0)) < MIN_RUNDEN:
            raise ValueError(f"Erst {stand.get('runden', 0)} Probe-Runde(n) – mindestens {MIN_RUNDEN} mit Vergleich gegen die Vorlage.")
        if stand.get("maengel"):
            raise ValueError("Detailgrad nicht erreicht: " + "; ".join(stand["maengel"]))
    from datetime import datetime, timezone
    v = _vorlage_von(n)
    fig = {"name": anzeige or v.get("anzeige") or n, "code": code, "anker": anker,
           "vorlage": {k: v.get(k, "") for k in ("begriff", "quelle", "seite", "lizenz", "urheber")},
           "stand": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (ordner() / "code").mkdir(parents=True, exist_ok=True)
    (ordner() / "code" / f"{n}.json").write_text(json.dumps(fig, ensure_ascii=False), "utf-8")
    daten = dict(_lernstand())
    figs = dict(daten.get("figuren_code") or {})
    figs[n] = fig
    daten["figuren_code"] = dict(sorted(figs.items(), key=lambda kv: kv[1].get("stand", ""))[-MAX_FIGUREN:])
    ziel = ordner() / "lernstand.json"
    ziel.write_text(json.dumps(daten, ensure_ascii=False), "utf-8")
    return ziel


def gebaut() -> list[str]:
    """In diesem Lauf abgelegte Figuren."""
    d = ordner() / "code"
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def proben() -> list[str]:
    """Probe-Bilder der abgelegten Figuren (zum Hochladen für die App)."""
    return [str(p) for n in gebaut() if (p := ordner() / "proben" / f"{n}.jpg").exists()]


def bericht(auftrag_id: str, adressen: dict | None = None, offen: list | None = None) -> Path:
    """Ergebnis-Dokument für die App (`figurenbau/<id>`): gebaute Figuren mit Probe-Bild, offene mit Grund."""
    from datetime import datetime, timezone
    adressen = adressen or {}
    figs = []
    for n in gebaut():
        fig = _lokal(n) or {}
        probe_bild = ordner() / "proben" / f"{n}.jpg"
        figs.append({"name": n, "anzeige": fig.get("name") or n, "anker": sorted(fig.get("anker") or {}),
                     "probe_url": adressen.get(str(probe_bild), "")})
    offen = [str(o)[:200] for o in (offen or []) if str(o).strip()][:10]
    doc = {"id": auftrag_id, "ok": bool(figs) and not offen, "gebaut": figs, "offen": offen,
           "stand": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    ziel = ordner() / "bericht.json"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
    return ziel
