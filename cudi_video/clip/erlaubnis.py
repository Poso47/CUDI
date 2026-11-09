"""Erlaubnis-Prüfung für Clips: Darf aus diesem Video/Kanal geclippt werden?

Quellen (Vertrag mit dem Clip-Scout, beide in `firma_daten/`):
- `clip_creators.json` (pflegt der Nutzer): {"creators": [{"name", "youtube": [...], "twitch": [...], "tiktok": [...],
  "gesperrt": bool}]} – eine Sperre geht immer vor.
- `clip_erlaubnis.json` (schreibt nur der Clip-Scout): je Creator Status „erlaubt“ | „gesperrt“ | „unklar“ mit
  wörtlichen Belegen. „erlaubt“ gilt nur mit mindestens einem Beleg samt Link und Zitat.

`pruefe(url)` ordnet die URL einem Kanal zu (YouTube-Kanal-ID/Handle, Twitch-Login, TikTok-Handle) und liefert
{"erlaubt": bool, "status": ..., "grund": str, "belege": [...], ...}. Nichts wird geraten: ohne Eintrag ist der
Status „unklar“ – der Auftrag läuft dann nur mit ausdrücklicher Bestätigung des Nutzers (`bestaetigt_erlaubnis`).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import ClipError

log = logging.getLogger(__name__)

ERLAUBT, GESPERRT, UNKLAR = "erlaubt", "gesperrt", "unklar"
_META_CACHE: dict[str, dict] = {}


def daten_ordner() -> Path:
    """`firma_daten/` (per CUDI_FIRMA_DATEN umlenkbar, wie bei den Firma-Mitarbeitern)."""
    env = os.environ.get("CUDI_FIRMA_DATEN")
    if env:
        return Path(env)
    from ..firma import common

    return Path(common.DATA_DIR)


def _lies(name: str) -> dict:
    try:
        d = json.loads((daten_ordner() / name).read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _norm(plattform: str, kennung: str) -> tuple[str, str]:
    k = str(kennung or "").strip().lower().lstrip("@")
    return plattform, k


def kanal_aus_url(url: str) -> list[tuple[str, str]]:
    """Kanalkennungen, die schon in der Adresse stehen (ohne Netz)."""
    p = urlparse(url.strip())
    host = (p.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    teile = [unquote(t) for t in p.path.split("/") if t]
    out: list[tuple[str, str]] = []
    if host.endswith("youtube.com") or host == "youtu.be":
        if teile and teile[0].startswith("@"):
            out.append(_norm("youtube", teile[0]))
        elif len(teile) >= 2 and teile[0] in ("channel", "c", "user"):
            out.append(_norm("youtube", teile[1]))
    elif host.endswith("twitch.tv"):
        if teile and teile[0] not in ("videos", "directory", "clip", "downloads"):
            out.append(_norm("twitch", teile[0]))
    elif host == "clips.twitch.tv":
        pass                                        # Clip-Adresse nennt den Kanal nicht – kommt aus den Metadaten
    elif host.endswith("tiktok.com"):
        if teile and teile[0].startswith("@"):
            out.append(_norm("tiktok", teile[0]))
    return out


def kanal_aus_meta(meta: dict) -> list[tuple[str, str]]:
    """Kanalkennungen aus yt-dlp-Metadaten (info.json): channel_id, uploader_id/@Handle, Twitch-Login, TikTok-Handle."""
    if not meta:
        return []
    ex = str(meta.get("extractor_key") or meta.get("extractor") or "").lower()
    out: list[tuple[str, str]] = []
    if "youtube" in ex or "youtube.com" in str(meta.get("channel_url") or meta.get("webpage_url") or ""):
        for key in ("channel_id", "uploader_id"):
            if meta.get(key):
                out.append(_norm("youtube", meta[key]))
        out += [k for k in kanal_aus_url(str(meta.get("uploader_url") or meta.get("channel_url") or ""))
                if k[0] == "youtube"]
    elif "twitch" in ex:
        for key in ("creator", "uploader_id", "channel"):
            if meta.get(key):
                out.append(_norm("twitch", meta[key]))
                break
    elif "tiktok" in ex:
        for key in ("uploader", "uploader_id", "channel"):
            if meta.get(key):
                out.append(_norm("tiktok", meta[key]))
    return list(dict.fromkeys(out))


def meta_holen(url: str) -> dict:
    """Metadaten ohne Download (yt-dlp, zwischengespeichert). Bei Fehler {} – dann bleibt der Status „unklar“."""
    if url in _META_CACHE:
        return _META_CACHE[url]
    meta: dict = {}
    try:
        res = subprocess.run(["yt-dlp", "--no-playlist", "--skip-download", "--dump-single-json", url],
                             capture_output=True, text=True, timeout=90)
        if res.returncode == 0 and res.stdout.strip():
            meta = json.loads(res.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        meta = {}
    _META_CACHE[url] = meta
    return meta


def _passt(creator: dict, kanaele: list[tuple[str, str]]) -> bool:
    haben = set()
    for pl in ("youtube", "twitch", "tiktok"):
        roh = creator.get(pl) or (creator.get("kanaele") or {}).get(pl) or []
        if isinstance(roh, str):
            roh = [roh]
        haben |= {_norm(pl, k) for k in roh}
    return bool(haben & set(kanaele))


def _beleg_ok(b: dict) -> bool:
    return bool(isinstance(b, dict) and str(b.get("url") or "").startswith("http") and str(b.get("zitat") or "").strip())


def pruefe(url: str, meta: dict | None = None, online: bool = True) -> dict:
    """Erlaubnis für die Quelle. `meta`: bereits bekannte yt-dlp-Metadaten (spart den Abruf)."""
    kanaele = kanal_aus_url(url) + kanal_aus_meta(meta or {})
    if not kanaele and online and meta is None:
        meta = meta_holen(url)
        kanaele = kanal_aus_meta(meta)
    kanaele = list(dict.fromkeys(kanaele))
    basis = {"erlaubt": False, "status": UNKLAR, "grund": "", "belege": [], "creator": "", "monetarisierung": "unklar",
             "bedingungen": [], "kanaele": [f"{p}:{k}" for p, k in kanaele]}
    if not kanaele:
        basis["grund"] = "Der Kanal der Quelle konnte nicht bestimmt werden – keine Erlaubnis gefunden."
        return basis
    # 1. Sperre des Nutzers geht vor
    for c in _lies("clip_creators.json").get("creators") or []:
        if isinstance(c, dict) and c.get("gesperrt") and _passt(c, kanaele):
            basis.update(status=GESPERRT, creator=str(c.get("name") or ""),
                         grund=f"Creator „{c.get('name', '?')}“ steht auf deiner Sperrliste (clip_creators.json).")
            return basis
    # 2. Ergebnis des Clip-Scouts
    for c in _lies("clip_erlaubnis.json").get("creators") or []:
        if not (isinstance(c, dict) and _passt(c, kanaele)):
            continue
        name = str(c.get("name") or "")
        belege = [b for b in c.get("belege") or [] if _beleg_ok(b)]
        basis.update(creator=name, belege=belege, monetarisierung=str(c.get("monetarisierung") or "unklar"),
                     bedingungen=[str(x) for x in c.get("bedingungen") or []])
        status = str(c.get("status") or UNKLAR)
        if status == GESPERRT:
            basis.update(status=GESPERRT, grund=f"Creator „{name}“ untersagt Clips laut Clip-Scout"
                         + (f": „{belege[0]['zitat']}“" if belege else "."))
        elif status == ERLAUBT and belege:
            basis.update(erlaubt=True, status=ERLAUBT,
                         grund=f"Creator „{name}“ erlaubt Clips (Beleg: {belege[0]['url']}).")
        elif status == ERLAUBT:
            basis.update(status=UNKLAR, grund=f"Creator „{name}“ gilt als erlaubt, aber ohne wörtlichen Beleg mit Link – "
                         "zählt deshalb als unklar.")
        else:
            basis.update(grund=f"Für „{name}“ ist die Erlaubnis unklar.")
        return basis
    basis["grund"] = "Zu diesem Kanal liegt keine Erlaubnis vor (weder erlaubt noch gesperrt)."
    return basis


def pruefe_auftrag(url: str, bestaetigt: bool, meta: dict | None = None) -> dict:
    """Für den App-Auftrag: erlaubt → Ergebnis; gesperrt → Abbruch; unklar → nur mit `bestaetigt_erlaubnis`.
    Das Ergebnis trägt `vermerk` für den Prüfbericht."""
    r = pruefe(url, meta)
    if r["status"] == GESPERRT:
        raise ClipError("Clip abgebrochen: " + r["grund"] + " Von gesperrten Creators wird nicht geclippt.")
    if r["status"] == ERLAUBT:
        r["vermerk"] = "Erlaubnis geprüft: " + r["grund"]
    elif bestaetigt:
        r["vermerk"] = ("ACHTUNG – Erlaubnis UNKLAR, nur auf deine Bestätigung geclippt (bestaetigt_erlaubnis): "
                        + r["grund"])
    else:
        raise ClipError("Clip abgebrochen: " + r["grund"] + " Bitte bestätigen, dass du die Erlaubnis des Creators "
                        "zum Clippen hast (bestaetigt_erlaubnis), oder den Creator vom Clip-Scout prüfen lassen.")
    return r


def bericht_zeilen(r: dict | None) -> list[str]:
    """Zeilen für den Prüfbericht (Vermerk + Belege)."""
    if not r:
        return []
    z = [f"- Erlaubnis: {r.get('vermerk') or r.get('grund')}"]
    if r.get("monetarisierung") not in (None, "", "unklar"):
        z.append(f"- Monetarisierung laut Scout: {r['monetarisierung']}")
    for b in r.get("bedingungen") or []:
        z.append(f"- Bedingung des Creators: {b}")
    for b in (r.get("belege") or [])[:3]:
        z.append(f"- Beleg ({b.get('art', 'web')}, {b.get('datum', '')}): „{b.get('zitat', '')}“ – {b.get('url', '')}")
    return z


