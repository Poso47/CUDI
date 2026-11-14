"""Figuren-Werkstatt: Fehlt dem Studio eine Figur (z. B. „Imker“), wird sie im selben Lauf gebaut – aber NIE frei erfunden.
Regel des Nutzers: Für JEDE Figur sucht zuerst der Referenz-Scout (`referenzen.suche`, Crawler über offene Bildquellen) die beste
Vorlage. Aus dem besten Fund werden die Farben gemessen; die Schreibaufgabe „Figurenbau“ bekommt Vorlagenbild + Farben und baut
danach einen Bauplan aus Grundkörpern (Kugel, Zylinder, Kegel, Quader, Kapsel). Ohne Fund entsteht keine Figur. Der Bauplan wird
streng geprüft, mit seiner Vorlage (Quelle, Lizenz) abgelegt (`video_output/_figuren/<name>.json`) und steht sofort für die Szenen
bereit – in 3D als echte Körper, in 2D als flache Formen. Über den Lernstand des Studios (`studio/lernstand`, Feld „figuren“)
bleiben neue Figuren für alle späteren Videos erhalten. Handgebaute Figuren (`data/figuren`) haben immer Vorrang. Das
Vorlagenbild selbst kommt nie ins Video und nie ins Repository.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .. import config

FORMEN = ("kugel", "zylinder", "kegel", "quader", "kapsel")
MAX_TEILE, MIN_TEILE, MAX_ANKER, MAX_FIGUREN = 32, 8, 8, 40
GRUPPE = re.compile(r"(kopf|arm|bein|schwanz|fluegel)[1-4]?")   # bewegliche Glieder (werden in 3D animiert)
GROESSE = 400                                             # Figurenraum wie bei den handgebauten Figuren
MAX_JE_LAUF = 3                                           # neue Figuren je Lauf (jede kostet eine Suche)
WUNSCH_REGEL = ("Schreibe jeden Wunsch als „deutsch (englisch)“, z. B. „Imker (beekeeper)“ – das englische Wort sucht die "
                "Vorlage im Netz; gebaut wird die Figur danach aus dem besten Fund.")
ANLEITUNG = (
    "Du bist die Figuren-Werkstatt eines Animationsstudios. Unter „daten.figuren“ steht je fehlender Figur der Name, das beste "
    "Vorlagenfoto aus dem Netz („vorlage“ = Bilddatei – SIEH SIE DIR ZUERST AN, z. B. mit dem Read-Werkzeug) und die daraus "
    "gemessenen Farben („farben“, häufigste zuerst). Baue JEDE Figur genau nach ihrer Vorlage: Körperbau, Verhältnisse, Haltung "
    "und kennzeichnende Einzelheiten wie auf dem Foto; als Farben nimmst du die gemessenen (und was du im Bild siehst) – nichts "
    "frei erfinden. Antworte mit EINEM JSON-Objekt: {\"figuren\": [{\"name\": \"imker\", \"gesehen\": \"ein Satz, was das "
    "Foto zeigt\", \"teile\": [{\"form\": \"kugel|zylinder|kegel|quader|kapsel\", \"x\": 50, \"y\": 20, \"z\": 0, "
    "\"b\": 18, \"h\": 18, \"t\": 18, \"farbe\": \"#e8c9a0\", \"dreh\": 0, \"glanz\": 0.2, \"gruppe\": \"kopf\"}, …], "
    "\"anker\": {\"kopf\": [50, 20]}}]}. "
    "Raum 0–100 (x nach rechts, y nach UNTEN, z nach vorn −30…30), b/h/t = Breite/Höhe/Tiefe, dreh = Drehung in Grad. "
    f"12–{MAX_TEILE} Teile, Seitenansicht, die Figur füllt den Raum (etwa 8–92). Erst die großen Körper (Rumpf, Kopf), dann "
    "Glieder, dann die Einzelheiten, an denen man die Figur sofort erkennt. \"anker\": 2–6 benannte Stellen (kleingeschrieben, "
    "ein Wort) für Beschriftungen. BEWEGUNG: Die Figur wird in 3D animiert – gib jedem Teil eines beweglichen Glieds das Feld "
    "\"gruppe\": kopf, arm, arm2, bein, bein2, schwanz, fluegel, fluegel2 (alle Teile eines Glieds dieselbe Gruppe, z. B. Oberarm, "
    "Unterarm, Hand = arm); Rumpf-Teile bekommen keine Gruppe. Jede Figur braucht mindestens den Kopf als Gruppe. Kannst du die Vorlage nicht ansehen, baue nur nach „titel“ und „farben“ und schreibe das in "
    "„gesehen“. Eine Figur, deren Vorlage nicht zum Namen passt, lässt du weg.")

_neu: list[str] = []                                       # in diesem Prozess neu aufgenommene Figuren (für den Prüfbericht)


def ordner() -> Path:
    return config.OUTPUT_DIR / "_figuren"


def _name(roh) -> str:
    from .zeichnen import figur_name
    return re.sub(r"[^a-z0-9_]", "", figur_name(str(roh or "")))[:24]


def pruefe_bauplan(roh) -> dict | None:
    """Bauplan säubern: nur bekannte Formen, Werte im Rahmen, genug Teile. None = unbrauchbar."""
    from .zeichnen import _zahl, farbe

    if not isinstance(roh, dict) or not _name(roh.get("name")):
        return None
    teile = []
    for t in (roh.get("teile") or [])[:MAX_TEILE]:
        if not isinstance(t, dict) or t.get("form") not in FORMEN:
            continue
        b = _zahl(t.get("b"), 12, 1, 100)
        teile.append({"form": t["form"], "x": _zahl(t.get("x"), 50, 0, 100), "y": _zahl(t.get("y"), 50, 0, 100),
                      "z": _zahl(t.get("z"), 0, -30, 30), "b": b, "h": _zahl(t.get("h"), b, 1, 100), "t": _zahl(t.get("t"), b, 1, 60),
                      "farbe": list(farbe(t.get("farbe"), (200, 200, 200))), "dreh": _zahl(t.get("dreh"), 0, -180, 180),
                      "glanz": _zahl(t.get("glanz"), .2, 0, 1)})
        g = str(t.get("gruppe") or "").strip().lower()
        if GRUPPE.fullmatch(g):
            teile[-1]["gruppe"] = g
    if len(teile) < MIN_TEILE:
        return None
    xs = [t["x"] - t["b"] / 2 for t in teile] + [t["x"] + t["b"] / 2 for t in teile]
    ys = [t["y"] - t["h"] / 2 for t in teile] + [t["y"] + t["h"] / 2 for t in teile]
    if max(max(xs) - min(xs), max(ys) - min(ys)) < 25:          # winziges Etwas in der Ecke ist keine Figur
        return None
    anker = {}
    for k, v in list((roh.get("anker") or {}).items())[:MAX_ANKER] if isinstance(roh.get("anker"), dict) else []:
        key = re.sub(r"[^a-zäöüß0-9_]", "", str(k).lower())[:20]
        if key and isinstance(v, (list, tuple)) and len(v) == 2:
            anker[key] = [_zahl(v[0], 50, 0, 100), _zahl(v[1], 50, 0, 100)]
    anker.setdefault("mitte", [round((min(xs) + max(xs)) / 2, 1), round((min(ys) + max(ys)) / 2, 1)])
    plan = {"name": _name(roh["name"]), "teile": teile, "anker": anker}
    if isinstance(roh.get("vorlage"), dict):                # woher die Figur stammt (Quelle/Lizenz des besten Fundes)
        plan["vorlage"] = {k: str(v)[:200] for k, v in roh["vorlage"].items() if k in ("seite", "quelle", "lizenz", "urheber", "begriff")}
    return plan


def _lernstand() -> dict:
    try:
        from .. import animation
        return (animation._lies(animation.lernstand_datei()).get("figuren") or {})
    except Exception:                                      # noqa: BLE001 – Lernstand ist nur ein Zusatz
        return {}


def bauplan(name: str) -> dict | None:
    """Abgelegter Bauplan: aus diesem Lauf (Datei) oder aus dem Lernstand früherer Läufe."""
    name = _name(name)
    if not name:
        return None
    datei = ordner() / f"{name}.json"
    try:
        if datei.exists():
            return pruefe_bauplan(json.loads(datei.read_text("utf-8")))
    except (OSError, ValueError):
        pass
    alt = _lernstand().get(name)
    return pruefe_bauplan(dict(alt, name=name)) if isinstance(alt, dict) else None


def info(name: str) -> dict | None:
    """Wie `zeichnen.figur_info`, aber für Werkstatt-Figuren (ohne Ebenen-Bilder, dafür mit „bauplan“)."""
    plan = bauplan(name)
    if not plan:
        return None
    k = GROESSE / 100
    return {"name": plan["name"], "ebenen": [], "groesse": GROESSE, "versteckt": [], "mit_kopf": [], "drehpunkte": {},
            "anker": {a: [v[0] * k, v[1] * k] for a, v in plan["anker"].items()}, "bauplan": plan["teile"], "ordner": None}


def namen() -> list[str]:
    hier = [p.stem for p in sorted(ordner().glob("*.json"))] if ordner().exists() else []
    return sorted(set(hier) | {_name(n) for n in _lernstand() if _name(n)})


def alle() -> dict[str, dict]:
    """Alle Werkstatt-Figuren für den Lernstand (neueste des Laufs gewinnen, höchstens MAX_FIGUREN)."""
    out = {}
    for n in namen():
        plan = bauplan(n)
        if plan:
            out[n] = {k: plan[k] for k in ("teile", "anker", "vorlage") if k in plan}
    return dict(list(out.items())[-MAX_FIGUREN:])


def aufnehmen(liste, vorhanden: set[str], vorlagen: dict[str, dict] | None = None) -> list[str]:
    """Baupläne aus einer Antwort prüfen und ablegen – nur Figuren, für die der Crawler eine Vorlage gefunden hat
    (`vorlagen`: name -> Fund). Vorhandene (handgebaute) Figuren werden nie überschrieben.
    Rückgabe: Namen der jetzt verfügbaren Werkstatt-Figuren aus dieser Liste."""
    fertig = []
    for roh in (liste or [])[:MAX_JE_LAUF] if isinstance(liste, list) else []:
        fund = (vorlagen or {}).get(_name(roh.get("name")) if isinstance(roh, dict) else "")
        if not fund:                                           # Regel: keine Figur ohne Vorlage aus dem Netz
            continue
        plan = pruefe_bauplan(dict(roh, vorlage=fund))
        if not plan or plan["name"] in vorhanden:
            continue
        try:
            ordner().mkdir(parents=True, exist_ok=True)
            (ordner() / f"{plan['name']}.json").write_text(json.dumps(plan, ensure_ascii=False), "utf-8")
        except OSError:
            continue
        fertig.append(plan["name"])
        if plan["name"] not in _neu:
            _neu.append(plan["name"])
    return fertig


def aktiv() -> bool:
    import os
    return os.environ.get("CUDI_WERKSTATT", "1") != "0"


def wunsch(roh) -> tuple[str, str, str]:
    """„Imker (beekeeper)“ -> (name, Anzeigename, Suchbegriff). Ohne Klammer sucht der deutsche Name."""
    text = re.sub(r"\s+", " ", str(roh or "")).strip()[:60]
    m = re.fullmatch(r"(.+?)\s*\(([^()]{2,40})\)", text)
    de, en = (m.group(1).strip(), m.group(2).strip()) if m else (text, text)
    return _name(de), de, re.sub(r"[^A-Za-zÄÖÜäöüß0-9 -]", "", en).strip()


def farben(datei, n: int = 6) -> list[str]:
    """Häufigste Farben der Bildmitte (dort sitzt das Motiv) als Hex – gemessen, nicht geraten."""
    from PIL import Image

    with Image.open(datei) as im:
        im = im.convert("RGB")
        w, h = im.size
        im = im.crop((int(w * .2), int(h * .15), int(w * .8), int(h * .85))).resize((96, 96))
        q = im.quantize(n, method=Image.MEDIANCUT)
        pal, zahl = q.getpalette()[:n * 3], sorted(q.getcolors(), reverse=True)
    return ["#%02x%02x%02x" % tuple(pal[i * 3:i * 3 + 3]) for _, i in zahl]


GANZ_MIN = .45                                           # so sicher muss CLIP sein, dass das Foto die GANZE Figur zeigt


def ganz_wert(begriff: str, funde: list[dict]) -> list[float] | None:
    """CLIP je Fund: Wie sicher zeigt das Foto die ganze Figur (nicht nur ein Detail, nichts anderes, keine Zeichnung)?
    None = CLIP nicht verfügbar."""
    from .. import bildcheck

    try:
        geladen = bildcheck.model() if bildcheck.enabled() and bildcheck.available() else None
        if not geladen or not funde:
            return None
        from PIL import Image
        mdl, preprocess, tokenizer, torch = geladen
        bilder = []
        for f in funde:
            with Image.open(f["datei"]) as im:
                bilder.append(preprocess(im.convert("RGB")))
        saetze = [f"a photo of a whole {begriff}, fully visible from top to bottom", f"a close-up of a small part or detail, hands only",
                  f"a photo of something else, not a {begriff}", "a drawing, logo or illustration", f"many {begriff}s in a crowd or far away"]
        with torch.no_grad():
            b = mdl.encode_image(torch.stack(bilder))
            t = mdl.encode_text(tokenizer(saetze))
            b, t = b / b.norm(dim=-1, keepdim=True), t / t.norm(dim=-1, keepdim=True)
            return [float(x) for x in (100.0 * b @ t.T).softmax(dim=-1)[:, 0]]
    except Exception:                                      # noqa: BLE001
        return None


def vorlage_suchen(begriff: str) -> dict | None:
    """Crawler: bester Fund für eine Figur -> {datei, seite, quelle, lizenz, urheber, titel, farben, begriff}. None = nichts.
    Der Fund muss das Gesuchte als Ganzes zeigen: mit CLIP der sicherste Ganzkörper-Treffer (mindestens GANZ_MIN), ohne CLIP
    der erste Fund, dessen Titel/Schlagwörter den Begriff nennen. Die Naturfoto-Quelle (nur Arten) braucht immer den Namen."""
    from .. import referenzen

    try:                                                   # zwei Suchen: der Begriff allein und als Ganzkörper-Aufnahme
        liste = referenzen.kandidaten(f"{begriff} full body", 20)[0] + referenzen.kandidaten(begriff, 12)[0]
        beste = referenzen.bewerten(begriff, liste)[:24]
    except Exception:                                      # noqa: BLE001 – Netz/Quelle darf ausfallen: dann keine Figur
        return None
    beste = [b for b in beste if b.get("quelle") != "inaturalist" or referenzen._passung_text(begriff, b) > 0]
    werte = ganz_wert(begriff, beste)
    if werte is not None:
        reihe = [b for w, b in sorted(zip(werte, beste), key=lambda x: -x[0]) if w >= GANZ_MIN]
    else:
        reihe = [b for b in beste if referenzen._passung_text(begriff, b) > 0]
    for b in reihe:
        try:
            return {"datei": str(b["datei"]), "seite": b.get("seite", ""), "quelle": b.get("quelle", ""), "lizenz": b.get("lizenz", ""),
                    "urheber": b.get("urheber", ""), "titel": b.get("titel", ""), "farben": farben(b["datei"]), "begriff": begriff}
        except Exception:                                  # noqa: BLE001 – kaputtes Bild: nächster Fund
            continue
    return None


def bauen(wuensche: list, aufgabe: str, notes: list[str]) -> list[str]:
    """Fehlende Figuren dieses Laufs bauen: je Wunsch Crawler -> bester Fund -> EINE Schreibaufgabe „Figurenbau“ für alle
    zusammen -> prüfen -> ablegen. Rückgabe: Namen der neu verfügbaren Figuren."""
    from .. import handoff
    from .zeichnen import FIGUREN, figur_info

    if not (aktiv() and handoff.active()):
        return []
    fest = {d.parent.name for d in FIGUREN.glob("*/figur.json")}
    offen, gesehen = [], set()
    for w in wuensche:
        name, anzeige, begriff = wunsch(w)
        if name and begriff and name not in gesehen and not figur_info(name):
            gesehen.add(name)
            offen.append((name, anzeige, begriff))
    offen = offen[:MAX_JE_LAUF]
    if not offen:
        return []
    datei = handoff.task_file(aufgabe)                         # nach der Schreibpause: dieselben Funde wieder nehmen
    funde = {}
    try:
        alt = json.loads(datei.read_text("utf-8")) if datei.exists() else {}
        funde = {f["name"]: f["fund"] for f in (alt.get("daten") or {}).get("figuren", []) if isinstance(f.get("fund"), dict)}
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        funde = {}
    if not funde:
        for name, anzeige, begriff in offen:
            fund = vorlage_suchen(begriff)
            if fund:
                funde[name] = fund
            else:
                notes.append(f"Figuren-Werkstatt: keine Vorlage für „{anzeige}“ gefunden – Figur wird nicht gebaut.")
    if not funde:
        return []
    daten = {"figuren": [{"name": n, "vorlage": f["datei"], "titel": f["titel"], "farben": f["farben"], "fund": f} for n, f in funde.items()]}
    answer = handoff.request(aufgabe, ANLEITUNG, daten)
    fertig = aufnehmen((answer or {}).get("figuren") if isinstance(answer, dict) else None, fest, funde)
    for n in fertig:
        f = funde[n]
        notes.append(f"Figuren-Werkstatt: „{n}“ neu gebaut nach Vorlage aus dem Netz ({f['quelle']}, {f['lizenz'] or 'Lizenz unbekannt'}; "
                     f"nur zum Modellieren, nicht im Video): {f['seite']}")
    return fertig


def neu_gebaut() -> list[str]:
    return list(_neu)


def zeichne(teile: list[dict], px: int, alpha: float, t: float = 0.0):
    """2D-Fassung (Ersatz ohne 3D): Teile von hinten nach vorn als flache Formen mit leichtem Licht."""
    from PIL import Image, ImageDraw

    s = 2
    bild = Image.new("RGBA", (px * s, px * s), (0, 0, 0, 0))
    k = px * s / 100
    for teil in sorted(teile, key=lambda q: q["z"]):
        w, h = max(2, int(teil["b"] * k)), max(2, int(teil["h"] * k))
        lage = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(lage)
        c = tuple(int(v) for v in teil["farbe"])
        a = int(255 * alpha)
        if teil["form"] == "kugel":
            d.ellipse((0, 0, w - 1, h - 1), fill=c + (a,))
        elif teil["form"] == "kegel":
            d.polygon([(w / 2, 0), (w - 1, h - 1), (0, h - 1)], fill=c + (a,))
        elif teil["form"] == "quader":
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=max(1, min(w, h) // 10), fill=c + (a,))
        else:                                              # zylinder, kapsel
            d.rounded_rectangle((0, 0, w - 1, h - 1), radius=(min(w, h) // 2 if teil["form"] == "kapsel" else max(1, min(w, h) // 6)),
                                fill=c + (a,))
        if abs(teil["dreh"]) > .5:
            lage = lage.rotate(-teil["dreh"], resample=Image.BICUBIC, expand=True)
        bild.alpha_composite(lage, (int(teil["x"] * k - lage.width / 2), int(teil["y"] * k - lage.height / 2 + math.sin(t * 2.4) * .2 * k)))
    return bild.resize((px, px), Image.LANCZOS)
