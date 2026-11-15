"""Modell-Scout: sucht für eine fehlende Figur zuerst ein FERTIGES freies 3D-Modell (statt sie aus Grundkörpern zu bauen).

Quelle: Objaverse (allenai/objaverse auf Hugging Face, ~800 000 Modelle von Sketchfab; hier der geprüfte LVIS-Teil mit 1 156
Kategorien und ~46 000 Modellen). Ablauf: englischer Begriff -> Kategorie -> Kandidaten -> Lizenz und Größe aus den Metadaten
prüfen (nur CC0 und CC BY: frei und kommerziell nutzbar; kein NC, kein SA) -> GLB laden. CC BY verlangt die Nennung des
Urhebers: Name, Lizenz und Link stehen am Bauplan (`vorlage`) und gehören in Prüfbericht UND Beschreibungstext des Videos.
Kostenlos, ohne Schlüssel. Fehlt die Kategorie oder ein passendes Modell: None (dann baut die Werkstatt nach Foto-Vorlage).
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

from .. import config, net

BASIS = "https://huggingface.co/datasets/allenai/objaverse/resolve/main"
LIZENZEN = {"cc0": "CC0", "by": "CC BY 4.0"}              # frei + kommerziell; BY = Urheber nennen
MAX_FLAECHEN, MAX_BYTES, MAX_PRUEFEN = 120_000, 9_000_000, 10
UA = {"User-Agent": "CUDI-Video/1.0 (Modell-Scout)"}


def ordner() -> Path:
    return config.OUTPUT_DIR / "_modelle"


def _gz_json(url: str):
    pfad = net.download(url, suffix=".json.gz", headers=UA, timeout=180)
    with gzip.open(pfad, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def kategorie(begriff: str, kategorien) -> str | None:
    """Englischer Begriff -> LVIS-Kategorie („cow“, „chicken“ -> „chicken_(animal)“, Mehrzahl -> Einzahl)."""
    w = re.sub(r"[^a-z ]", "", begriff.lower()).strip().replace(" ", "_")
    if not w:
        return None
    formen = [w, w.rstrip("s"), w[:-2] if w.endswith("es") else w, w.split("_")[-1]]
    for f in formen:
        if f in kategorien:
            return f
    for f in formen:
        treffer = sorted(k for k in kategorien if k.startswith(f + "_("))
        if treffer:
            return treffer[0]
    return None


def finde(begriff: str) -> dict | None:
    """Erstes freies Modell (ohne Sichtprüfung) oder None – siehe `kandidaten`."""
    return next(iter(kandidaten(begriff, 1)), None)


def kandidaten(begriff: str, anzahl: int = 4) -> list[dict]:
    """Freie Modelle zum Begriff, beliebteste zuerst -> [{datei, url, lizenz, urheber, seite, titel, flaechen, bewegt, begriff}]."""
    out = []
    try:
        lvis = _gz_json(f"{BASIS}/lvis-annotations.json.gz")
        kat = kategorie(begriff, lvis)
        if not kat:
            return []
        pfade = _gz_json(f"{BASIS}/object-paths.json.gz")
        roh, meta_cache = [], {}
        for uid in lvis[kat][:MAX_PRUEFEN]:
            pfad = pfade.get(uid)
            if not pfad:
                continue
            teil = pfad.split("/")[1]
            if teil not in meta_cache:
                meta_cache[teil] = _gz_json(f"{BASIS}/metadata/{teil}.json.gz")
            m = meta_cache[teil].get(uid) or {}
            if m.get("license") not in LIZENZEN or not 0 < (m.get("faceCount") or 0) <= MAX_FLAECHEN:
                continue
            roh.append((m.get("likeCount") or 0, uid, pfad, m))
            if len(meta_cache) >= 4 and roh:           # Metadaten sind groß: nicht endlos weitere Teile laden
                break
        for _, uid, pfad, m in sorted(roh, key=lambda x: -x[0]):
            datei = net.download(f"{BASIS}/{pfad}", suffix=".glb", headers=UA, timeout=180)
            if not 1000 < datei.stat().st_size <= MAX_BYTES:
                continue
            out.append({"datei": str(datei), "url": f"{BASIS}/{pfad}", "lizenz": LIZENZEN[m["license"]],
                        "urheber": str((m.get("user") or {}).get("username") or "")[:60], "titel": str(m.get("name") or "")[:80],
                        "seite": str(m.get("viewerUrl") or f"https://sketchfab.com/3d-models/{uid}"), "quelle": "objaverse/sketchfab",
                        "flaechen": m.get("faceCount") or 0, "bewegt": bool(m.get("animationCount")), "begriff": begriff})
            if len(out) >= anzahl:
                break
    except Exception:                                      # noqa: BLE001 – Netz/Quelle darf ausfallen: dann Foto-Weg
        return out
    return out


SICHT_MIN = .5                                            # so sicher muss CLIP das Modell als das Gesuchte erkennen


def sichtpruefung(fund: dict) -> dict | None:
    """Modell probeweise rendern: Größe angleichen, beste Blickrichtung wählen, Unpassendes ablehnen.
    Rückgabe: fund + {"dreh", "skala", "sicher"} oder None (lädt nicht / leer / sieht nicht nach dem Begriff aus)."""
    from . import drei

    if not drei.aktiv():
        return dict(fund, dreh=0, skala=1.0, sicher=None)
    bilder = drei.modell_probe(fund["datei"])
    masse = []
    for w, im in bilder:
        box = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
        masse.append(max(box[2] - box[0], box[3] - box[1]) / im.width if box else 0.0)
    if not bilder or max(masse) <= 0.01:
        return None
    soll = .9 * drei.PROBE_GROESSE / 100                    # eine Figur der Größe g füllt etwa 0,9 · g % der Bildbreite
    skala = lambda i: round(max(.15, min(12.0, soll / max(masse[i], .01))), 3)   # noqa: E731
    werte = _clip(fund["begriff"], [im for _, im in bilder])
    if werte is None:
        return dict(fund, dreh=0, skala=skala(0), sicher=None)
    bester = max(range(len(werte)), key=lambda i: werte[i])
    if werte[bester] < SICHT_MIN or masse[bester] <= 0.01:
        return None
    return dict(fund, dreh=bilder[bester][0], skala=skala(bester), sicher=round(werte[bester], 2))


def _clip(begriff: str, bilder: list) -> list[float] | None:
    from .. import bildcheck

    try:
        geladen = bildcheck.model() if bildcheck.enabled() and bildcheck.available() else None
        if not geladen:
            return None
        from PIL import Image
        mdl, preprocess, tokenizer, torch = geladen
        flach = []
        for im in bilder:                                  # auf hellem Grund beurteilen (durchsichtig wäre schwarz)
            grund = Image.new("RGBA", im.size, (235, 235, 235, 255))
            grund.alpha_composite(im)
            flach.append(preprocess(grund.convert("RGB")))
        saetze = [f"a 3D render of a {begriff}, seen from the side or front", f"a 3D render of a {begriff} seen from behind",
                  f"a 3D render of something else, not a {begriff}", "an empty image or abstract shapes"]
        with torch.no_grad():
            b = mdl.encode_image(torch.stack(flach))
            t = mdl.encode_text(tokenizer(saetze))
            b, t = b / b.norm(dim=-1, keepdim=True), t / t.norm(dim=-1, keepdim=True)
            return [float(x) for x in (100.0 * b @ t.T).softmax(dim=-1)[:, 0]]
    except Exception:                                      # noqa: BLE001
        return None


def nennung(fund: dict) -> str:
    """Pflichtangabe für CC BY (und fair bei CC0): „3D-Modell „Cow“ von shakiller (CC BY 4.0): Link“."""
    return f"3D-Modell „{fund.get('titel') or fund.get('begriff')}“ von {fund.get('urheber') or 'unbekannt'} ({fund.get('lizenz')}): {fund.get('seite')}"
