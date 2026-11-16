"""Clip-Autopilot (GitHub, kein Claude-Verbrauch): schneidet und veröffentlicht Clips von Creators, die nachweislich Clipper
suchen – ganz ohne Zutun (Entscheidung des Nutzers vom 16.11.: „Alles automatisch“).

Regeln (nie lockern):
- Nur Material von Creators mit Status „erlaubt“ (wörtlicher Aufruf + Link + Datum im Clip-Scout). „geduldet“, „unklar“
  und „gesperrt“ nie – die Clip-Engine prüft die Erlaubnis im Lauf noch einmal (clip/erlaubnis.py).
- Höchstens `max_pro_tag` Clips je Tag, jede Quelle nur einmal, Credit „Original: <Creator> – <Link>“ im Beschreibungstext.
- Hochladen sofort (`freigabe: false`) auf die eingestellten Ziele; fehlen Zugangsdaten, steht das ehrlich im Protokoll.
Einstellungen: `firma_daten/clip_autopilot_einstellungen.json` (fehlt sie: Standard unten). Protokoll: `clip_autopilot.json`.
"""

from __future__ import annotations

import hashlib
import json
import re
import time

from . import common
from .common import iso, now, parse_time

EINSTELLUNGEN, PROTOKOLL, RADAR, ERLAUBNIS = ("clip_autopilot_einstellungen.json", "clip_autopilot.json", "clip_radar.json",
                                              "clip_erlaubnis.json")
STANDARD = {"aktiv": True, "max_pro_tag": 3, "max_versuche": 5, "hochladen": "alle", "sichtbarkeit": "oeffentlich",
            "clip_stil": "vollbild", "laenge": 60, "max_alter_tage": 7}
MAX_PROTOKOLL = 300


def einstellungen() -> dict:
    roh = common.read_json(EINSTELLUNGEN, {}) or {}
    e = {**STANDARD, **{k: v for k, v in roh.items() if k in STANDARD}} if isinstance(roh, dict) else dict(STANDARD)
    e["max_pro_tag"] = max(0, min(10, int(e.get("max_pro_tag") or 0)))
    e["max_versuche"] = max(1, min(10, int(e.get("max_versuche") or 1)))
    return e


def _id(url: str) -> str:
    return "ap" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def kandidaten(radar: dict, erlaubnis: dict, protokoll: list[dict], e: dict) -> list[dict]:
    """Material nur von erlaubten Creators: frische Videos/Clips (schnellste zuerst), dann je Twitch-Kanal ein Tages-Ranking.
    Schon versuchte Quellen fallen raus (Fehlschläge höchstens 2-mal)."""
    erlaubt = {c.get("name"): c for c in erlaubnis.get("creators") or [] if isinstance(c, dict) and c.get("status") == "erlaubt"
               and any(b.get("staerke") == "eindeutig" for b in c.get("belege") or [])}
    versuche: dict[str, int] = {}
    fertig = set()
    for p in protokoll:
        versuche[p.get("quelle", "")] = versuche.get(p.get("quelle", ""), 0) + 1
        if p.get("ok"):
            fertig.add(p.get("quelle", ""))
    grenze = now().timestamp() - e["max_alter_tage"] * 86400
    out = []
    zeilen = sorted((r for r in radar.get("videos") or [] if r.get("erlaubnis") == "erlaubt" and r.get("creator") in erlaubt),
                    key=lambda r: -(r.get("aufrufe_je_stunde") or 0))
    for r in zeilen:
        t = parse_time(r.get("veroeffentlicht", ""))
        if not r.get("url") or r["url"] in fertig or versuche.get(r["url"], 0) >= 2 or (t and t.timestamp() < grenze):
            continue
        out.append({"quelle": r["url"], "creator": r["creator"], "titel": r.get("titel", ""), "art": "video"})
    heute = now().strftime("%Y-%m-%d")
    for name, c in erlaubt.items():                        # Twitch: bestes Material der Woche aus den öffentlichen Clips
        for login in (c.get("kanaele") or {}).get("twitch") or []:
            key = f"twitch:{login}:{heute}"
            if key not in fertig and versuche.get(key, 0) < 2:
                out.append({"quelle": key, "creator": name, "titel": f"Twitch {login}", "art": "twitch", "login": login})
    return out


def auftrag(k: dict, e: dict) -> dict:
    hoch = {"ziel": e["hochladen"], "sichtbarkeit": e["sichtbarkeit"], "freigabe": False} if e["hochladen"] else None
    basis = {"art": "clip", "id": _id(k["quelle"]), "sprache": "de", "clip_stil": e["clip_stil"], "hochladen": hoch}
    if k["art"] == "twitch":
        return {**basis, "twitch_kanal": k["login"], "zeitraum": "7d"}
    return {**basis, "quelle": k["quelle"], "laenge": e["laenge"]}


def heute_fertig(protokoll: list[dict]) -> int:
    heute = now().strftime("%Y-%m-%d")
    return sum(1 for p in protokoll if p.get("ok") and str(p.get("zeit", "")).startswith(heute))


def run(runner=None) -> dict:
    """Ein Durchgang: Kandidaten wählen, schneiden + hochladen (job.run_order ohne Claude), protokollieren."""
    from .. import job

    started = time.monotonic()
    notes: list[str] = []
    e = einstellungen()
    alt = common.read_json(PROTOKOLL, {}) or {}
    protokoll = list(alt.get("clips") or [])
    neu: list[dict] = []
    if not e["aktiv"]:
        notes.append("Clip-Autopilot ist aus (clip_autopilot_einstellungen.json: aktiv=false).")
    else:
        frei = e["max_pro_tag"] - heute_fertig(protokoll)
        liste = kandidaten(common.read_json(RADAR, {}) or {}, common.read_json(ERLAUBNIS, {}) or {}, protokoll, e)
        if not liste:
            notes.append("Kein Material von Creators mit belegter Erlaubnis – der Clip-Scout sucht weiter.")
        run_order = runner or job.run_order
        youtube_gesperrt = False
        for k in liste[:e["max_versuche"]]:
            if youtube_gesperrt and "youtu" in k["quelle"]:
                continue                                  # YouTube sperrt diesen Server gerade: übrige YouTube-Quellen später
            if frei <= 0:
                notes.append(f"Tagesgrenze erreicht ({e['max_pro_tag']} Clips).")
                break
            eintrag = {"quelle": k["quelle"], "creator": k["creator"], "titel": k["titel"], "zeit": iso(), "ok": False}
            try:
                order = job.parse_order(auftrag(k, e), set())
                code, data = run_order(order, job.job_folder(order["id"]), via_claude=False)
            except Exception as exc:                      # noqa: BLE001 – ein Clip stoppt den Durchgang nicht
                code, data = 1, {"ok": False, "fehler": common.short_error(exc)}
            data = data or {}
            eintrag["ok"] = bool(data.get("ok"))
            if not eintrag["ok"] and "youtu" in k["quelle"] and re.search(r"sign in|bot|403|429|gesperrt|sperren", str(data.get("fehler") or ""), re.I):
                youtube_gesperrt = True
                notes.append("YouTube sperrt den Server (Anmeldung verlangt) – mit Secret CUDI_YT_COOKIES geht es (docs/clip-team.md).")
            eintrag["fehler"] = "" if eintrag["ok"] else str(data.get("fehler") or f"Exit-Code {code}")[:300]
            eintrag["hochgeladen"] = [{"ziel": h.get("ziel"), "ok": bool(h.get("ok")), "url": h.get("url", ""),
                                       "fehler": str(h.get("fehler") or "")[:160]} for h in data.get("hochgeladen") or []]
            eintrag["credit"] = f"Original: {k['creator']} – {k['quelle'] if k['art'] == 'video' else 'https://www.twitch.tv/' + k['login']}"
            if eintrag["ok"]:
                frei -= 1
                try:
                    (job.job_folder(order["id"]) / "autopilot.json").write_text(json.dumps(eintrag, ensure_ascii=False), "utf-8")
                except OSError:
                    pass
            neu.append(eintrag)
    protokoll = (protokoll + neu)[-MAX_PROTOKOLL:]
    posts = [h["url"] for p in neu for h in p.get("hochgeladen", []) if h.get("ok") and h.get("url")]
    if posts:                                              # eigene Posts misst die Messung (clip_radar.clip_posts)
        radar = common.read_json(RADAR, {}) or {}
        radar["clip_posts"] = list(dict.fromkeys(list(radar.get("clip_posts") or []) + posts))[-200:]
        common.write_json(RADAR, radar)
    common.write_json(PROTOKOLL, {"erzeugt": iso(), "einstellungen": e, "heute": heute_fertig(protokoll), "clips": protokoll,
                                  "hinweise": notes[:10]})
    ok = sum(1 for p in neu if p["ok"])
    summary = f"{ok} Clips geschnitten und veröffentlicht, {len(neu) - ok} fehlgeschlagen" if neu else (notes[0] if notes else "nichts zu tun")
    common.record_status("clipautopilot", started, True, summary, notes)
    return {"neu": neu, "hinweise": notes}
