"""Referenz-Scout: Crawler, der im Netz die besten Vorlagen für 3D-Figuren sucht (Wunsch des Nutzers: „das Beste nehmen“).

Fragt mehrere offene Bildquellen gleichzeitig ab (Openverse – bündelt u. a. Flickr und Museen –, iNaturalist mit
geprüften Naturfotos, Pexels/Pixabay, falls Schlüssel da sind), lädt die Kandidaten klein herunter und bewertet jedes Bild:
Schärfe (Laplace-Varianz), Auflösung, Passung zum Suchbegriff (CLIP, falls installiert, sonst Titel/Schlagwörter) und
Beliebtheit der Quelle. Die besten landen mit Quelle und Lizenz in `video_output/_referenzen/<begriff>/` als
Kontaktbogen + `referenzen.json`. Die Bilder sind NUR Vorlage zum Modellieren (Proportionen, Farben, Aufbau) – sie kommen
nie ins Video und nie ins Repository. Aufruf: `python -m cudi_video referenzen "honeybee side view" --anzahl 8`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config, net

log = logging.getLogger(__name__)
ORDNER = config.OUTPUT_DIR / "_referenzen"
UA = {"User-Agent": "CUDI-Video/1.0 (Referenz-Scout)"}


def _openverse(begriff: str, n: int) -> list[dict]:
    d = net.get_json("https://api.openverse.org/v1/images/", params={"q": begriff, "page_size": min(n, 20)},
                     headers=UA, cache_hours=24)
    return [{"quelle": "openverse/" + str(r.get("source") or r.get("provider") or ""), "bild": r.get("thumbnail") or r.get("url"),
             "seite": r.get("foreign_landing_url") or "", "lizenz": f"{r.get('license', '')} {r.get('license_version') or ''}".strip(),
             "urheber": r.get("creator") or "", "titel": r.get("title") or "",
             "schlagworte": [t.get("name", "") for t in (r.get("tags") or [])][:20], "breite": r.get("width") or 0,
             "hoehe": r.get("height") or 0, "beliebt": 0} for r in (d.get("results") or []) if r.get("url")]


def _inaturalist(begriff: str, n: int) -> list[dict]:
    d = net.get_json("https://api.inaturalist.org/v1/observations",
                     params={"q": begriff, "photos": "true", "quality_grade": "research", "per_page": n, "order_by": "votes"},
                     headers=UA, cache_hours=24)
    out = []
    for o in d.get("results") or []:
        for p in (o.get("photos") or [])[:2]:
            url = str(p.get("url") or "").replace("square", "large")
            if url:
                out.append({"quelle": "inaturalist", "bild": url, "seite": o.get("uri") or "", "lizenz": p.get("license_code") or "alle Rechte",
                            "urheber": (p.get("attribution") or "")[:80], "titel": (o.get("taxon") or {}).get("name") or "",
                            "schlagworte": [(o.get("taxon") or {}).get("preferred_common_name") or ""],
                            "breite": (p.get("original_dimensions") or {}).get("width") or 0,
                            "hoehe": (p.get("original_dimensions") or {}).get("height") or 0, "beliebt": o.get("faves_count") or 0})
    return out


def _pexels(begriff: str, n: int) -> list[dict]:
    if not config.PEXELS_API_KEY:
        return []
    d = net.get_json("https://api.pexels.com/v1/search", params={"query": begriff, "per_page": n},
                     headers={"Authorization": config.PEXELS_API_KEY}, cache_hours=24)
    return [{"quelle": "pexels", "bild": (p.get("src") or {}).get("large"), "seite": p.get("url") or "", "lizenz": "Pexels",
             "urheber": p.get("photographer") or "", "titel": p.get("alt") or "", "schlagworte": [], "breite": p.get("width") or 0,
             "hoehe": p.get("height") or 0, "beliebt": 0} for p in d.get("photos") or []]


def _pixabay(begriff: str, n: int) -> list[dict]:
    if not config.PIXABAY_API_KEY:
        return []
    d = net.get_json("https://pixabay.com/api/", params={"key": config.PIXABAY_API_KEY, "q": begriff, "per_page": max(3, n),
                                                         "image_type": "photo"}, cache_hours=24)
    return [{"quelle": "pixabay", "bild": h.get("webformatURL"), "seite": h.get("pageURL") or "", "lizenz": "Pixabay",
             "urheber": h.get("user") or "", "titel": "", "schlagworte": str(h.get("tags") or "").split(", "),
             "breite": h.get("imageWidth") or 0, "hoehe": h.get("imageHeight") or 0, "beliebt": h.get("likes") or 0}
            for h in d.get("hits") or []]


QUELLEN = (_openverse, _inaturalist, _pexels, _pixabay)


def kandidaten(begriff: str, je_quelle: int = 30) -> tuple[list[dict], list[str]]:
    """Alle Quellen gleichzeitig; jede einzeln abgesichert (Ausfall = Hinweis)."""
    gefunden, hinweise = [], []
    with ThreadPoolExecutor(max_workers=len(QUELLEN)) as pool:
        for quelle, zukunft in [(q.__name__.strip("_"), pool.submit(q, begriff, je_quelle)) for q in QUELLEN]:
            try:
                gefunden += [k for k in zukunft.result() if k.get("bild")]
            except Exception as exc:                          # noqa: BLE001
                hinweise.append(f"{quelle}: {str(exc)[:120]}")
    return gefunden, hinweise


def schaerfe(im) -> float:
    """Laplace-Varianz auf 256 px Graustufen – höher = schärfer (Makrofotos mit klaren Details gewinnen)."""
    import numpy as np

    g = np.asarray(im.convert("L").resize((256, 256)), dtype=np.float32)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def _passung_text(begriff: str, k: dict) -> float:
    woerter = {w for w in re.findall(r"\w+", begriff.lower()) if len(w) > 2}
    text = " ".join([k.get("titel", "")] + list(k.get("schlagworte") or [])).lower()
    return sum(1 for w in woerter if w in text) / max(1, len(woerter))


def vorlage_wert(begriff: str, bilder: list) -> list[float] | None:
    """CLIP: Wie sehr ist das Bild eine gute Modellier-Vorlage? Ein einzelnes Motiv groß und scharf gewinnt gegen Schwärme,
    winzige Motive in der Ferne, Zeichnungen und Unscharfes."""
    from . import bildcheck

    geladen = bildcheck.model()
    if geladen is None or not bilder:
        return None
    mdl, preprocess, tokenizer, torch = geladen
    saetze = [f"a sharp close-up macro photo of a single {begriff} filling the frame, side view",
              f"a photo of many {begriff}s crowded together", f"a photo of a tiny {begriff} far away in a large scene",
              "a drawing, cartoon or illustration", "a blurry out of focus photo", "a photo of a landscape or building"]
    with torch.no_grad():
        f = mdl.encode_image(torch.stack([preprocess(b) for b in bilder]))
        t = mdl.encode_text(tokenizer(saetze))
        f, t = f / f.norm(dim=-1, keepdim=True), t / t.norm(dim=-1, keepdim=True)
        p = (100.0 * f @ t.T).softmax(dim=-1)[:, 0]
    return [float(x) for x in p]


def bewerten(begriff: str, liste: list[dict]) -> list[dict]:
    """Herunterladen (klein, parallel) und bewerten. Rückgabe: beste zuerst, ohne Doppel."""
    from PIL import Image

    def laden(k):
        try:
            p = net.download(k["bild"], suffix=".jpg", headers=UA, timeout=20)
            im = Image.open(p).convert("RGB")
            return k, p, im
        except Exception:                                      # noqa: BLE001 – einzelnes Bild darf fehlen
            return k, None, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        geladen = [x for x in pool.map(laden, liste) if x[2] is not None and min(x[2].size) >= 200]
    if not geladen:
        return []
    clip = None
    try:
        from . import bildcheck
        if bildcheck.enabled() and bildcheck.available():
            clip = vorlage_wert(begriff, [im for _, _, im in geladen])
    except Exception:                                          # noqa: BLE001 – ohne CLIP: Titel/Schlagwörter
        clip = None
    schaerfen = [schaerfe(im) for _, _, im in geladen]
    smax = max(schaerfen) or 1.0
    out, gesehen = [], set()
    for i, (k, p, im) in enumerate(geladen):
        kennung = hashlib.md5(im.resize((16, 16)).convert("L").tobytes()).hexdigest()
        if kennung in gesehen:
            continue
        gesehen.add(kennung)
        aufl = min(1.0, max(k.get("breite") or im.width, k.get("hoehe") or im.height) / 3000)
        passung = clip[i] if clip else _passung_text(begriff, k)
        punkte = .6 * passung + .2 * (schaerfen[i] / smax) + .12 * aufl + .08 * min(1.0, (k.get("beliebt") or 0) / 20)
        out.append(dict(k, datei=str(p), punkte=round(punkte, 3), schaerfe=round(schaerfen[i], 1), passung=round(passung, 2)))
    return sorted(out, key=lambda x: -x["punkte"])


def kontaktbogen(beste: list[dict], ziel: Path) -> Path:
    from PIL import Image, ImageDraw

    zellen = []
    for i, k in enumerate(beste, start=1):
        im = Image.open(k["datei"]).convert("RGB")
        im.thumbnail((400, 300))
        zelle = Image.new("RGB", (400, 330), (20, 20, 26))
        zelle.paste(im, ((400 - im.width) // 2, 0))
        ImageDraw.Draw(zelle).text((8, 306), f"{i}. {k['punkte']:.2f}  {k['quelle']}  {k['lizenz']}"[:60], fill=(230, 230, 230))
        zellen.append(zelle)
    spalten = 4
    bogen = Image.new("RGB", (400 * min(spalten, len(zellen)), 330 * ((len(zellen) + spalten - 1) // spalten)), (10, 10, 14))
    for i, z in enumerate(zellen):
        bogen.paste(z, ((i % spalten) * 400, (i // spalten) * 330))
    bogen.save(ziel, quality=88)
    return ziel


def suche(begriff: str, anzahl: int = 8) -> dict:
    """Crawlen, bewerten, die besten ablegen. Rückgabe: {ordner, bogen, beste, hinweise}."""
    liste, hinweise = kandidaten(begriff)
    beste = bewerten(begriff, liste)[:anzahl]
    ordner = ORDNER / re.sub(r"[^a-z0-9]+", "-", begriff.lower()).strip("-")[:40]
    ordner.mkdir(parents=True, exist_ok=True)
    bogen = kontaktbogen(beste, ordner / "kontaktbogen.jpg") if beste else None
    daten = {"begriff": begriff, "kandidaten": len(liste), "hinweise": hinweise,
             "hinweis": "Nur Vorlage zum Modellieren – nie ins Video oder ins Repository übernehmen.",
             "beste": [{k: v for k, v in b.items() if k != "datei"} for b in beste]}
    (ordner / "referenzen.json").write_text(json.dumps(daten, ensure_ascii=False, indent=1), "utf-8")
    return {"ordner": str(ordner), "bogen": str(bogen) if bogen else "", "beste": beste, "hinweise": hinweise,
            "kandidaten": len(liste)}
