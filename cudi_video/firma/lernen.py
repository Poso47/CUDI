"""Lern-Analyst: wertet aus, welche Varianten (Format, Design, Bewegung, Musik, Maskottchen …) gut ankommen.

Quellen (kostenlos, nur lesend):
  (a) YouTube-Statistik der hochgeladenen Videos (videos.list, part=statistics) – braucht Scope youtube.readonly bzw.
      CUDI_YT_API_KEY für öffentliche Videos; der reine Upload-Scope reicht NICHT (docs/lernen-einrichten.md),
  (b) TikTok video.list (Scope video.list nötig; Zuordnung über den Text, weil Inbox-Entwürfe erst später eine Kennung bekommen),
  (c) Bewertungen 👍/👎 aus der App: liegen in der Artefakt-Datenbank, die GitHub nicht lesen kann – sie wirken stattdessen
      direkt über `vorlieben.varianten_gut/_schlecht` im nächsten Auftrag (experimente.py).
Zuordnung Video -> Varianten: `firma_daten/uploads.json` (schreibt nur der Notbetrieb-Workflow nach einem Upload, weil
Claude-Läufe nichts committen dürfen). Ergebnis: `firma_daten/lernen.json` (Gewichte, Gewinner, Begründung).

Ehrlich: Unter `MIN_VIDEOS` gemessenen Videos bleibt alles bei der Erkundung (`modus: "erkundung"`); ein „Gewinner“
braucht `MIN_JE_VARIANTE` Videos und deutlichen Vorsprung. Kein Lernen aus Zufall.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
from datetime import timedelta
from pathlib import Path

from . import common
from .common import iso, now, parse_time

MIN_VIDEOS = 8                  # so viele gemessene Videos, bevor überhaupt Gewichte entstehen
MIN_JE_VARIANTE = 4             # so viele gemessene Videos je Variante für einen Gewinner
MIN_ALTER_TAGE = 2              # jüngere Videos sind noch nicht ausgewertet
MAX_ALTER_TAGE = 14             # Reichweite wird auf diese Zeit normiert
VORSPRUNG = 0.10                # Gewinner braucht diesen Vorsprung in der Erfolgsquote
GUT, SCHLECHT = 1.25, 0.8       # Reichweite je Tag im Verhältnis zum Median: darüber gut, darunter schlecht
KEEP_UPLOADS = 400


# --------------------------------------------------------------------------- Upload-Liste

def merge_uploads(path: str | Path) -> int:
    """Neue Upload-Einträge (Notbetrieb-Workflow) in firma_daten/uploads.json aufnehmen. Rückgabe: Anzahl neuer."""
    try:
        new = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return 0
    data = common.read_json("uploads.json", {}) or {}
    rows = data.get("eintraege", [])
    seen = {(r.get("ziel"), r.get("video_id") or r.get("publish_id") or r.get("auftrag")) for r in rows}
    added = 0
    for r in new if isinstance(new, list) else []:
        key = (r.get("ziel"), r.get("video_id") or r.get("publish_id") or r.get("auftrag"))
        if r.get("ziel") in ("youtube", "tiktok") and key not in seen:
            rows.append(r)
            seen.add(key)
            added += 1
    data = {"erzeugt": iso(), "hinweis": "Nur von GitHub-Workflows geschrieben (Notbetrieb nach einem Upload).",
            "eintraege": rows[-KEEP_UPLOADS:]}
    common.write_json("uploads.json", data)
    return added


# --------------------------------------------------------------------------- Zahlen holen

def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").casefold()).strip()


def measure(rows: list[dict], notes: list[str]) -> list[dict]:
    """Zu jedem Eintrag mit Varianten die Zahlen anhängen: {..., punkte, alter_tage}. Nicht messbare bleiben weg."""
    from ..upload import tiktok, youtube

    out: list[dict] = []
    yt = [r for r in rows if r.get("ziel") == "youtube" and r.get("video_id")]
    if yt:
        stats, hints = youtube.video_stats([r["video_id"] for r in yt])
        notes += hints
        for r in yt:
            if r["video_id"] in stats:
                out.append({**r, **stats[r["video_id"]]})
    tt = [r for r in rows if r.get("ziel") == "tiktok"]
    if tt:
        try:
            listed = tiktok.video_list(20)
        except Exception as exc:                          # noqa: BLE001 – ohne Scope/Zugang kein TikTok-Lernen
            notes.append(f"TikTok-Zahlen nicht verfügbar: {common.short_error(exc)}")
            listed = []
        for r in tt:
            key = _norm(r.get("text", ""))[:60]
            hit = next((v for v in listed if key and _norm(v["title"]).startswith(key[:40])), None)
            if hit:
                out.append({**r, "views": hit["views"], "likes": hit["likes"], "comments": hit["comments"],
                            "shares": hit["shares"]})
    _from_messung(rows, out, notes)
    for r in out:
        t = parse_time(r.get("hochgeladen", ""))
        r["alter_tage"] = round((now() - t).total_seconds() / 86400, 2) if t else 0
        r["punkte"] = r.get("views", 0) + 25 * r.get("likes", 0) + 60 * r.get("comments", 0) + 80 * r.get("shares", 0)
    return [r for r in out if r["alter_tage"] >= MIN_ALTER_TAGE and r.get("varianten")]


def _from_messung(rows: list[dict], out: list[dict], notes: list[str]) -> None:
    """Fehlen API-Zahlen, hilft die öffentliche Messreihe des Mitarbeiters „Messung“ (messung.json, nur Aufrufe/Likes/Kommentare)."""
    from . import messung
    data = common.read_json(messung.FILE, {}) or {}
    added = 0
    for r in rows:
        if any(r.get("auftrag") == o.get("auftrag") and r.get("ziel") == o.get("ziel") for o in out):
            continue
        url = r.get("url") or (f"https://www.youtube.com/watch?v={r['video_id']}" if r.get("video_id") else "")
        point = messung.latest(url, data) if url else None
        if point:
            out.append({**r, "views": point["aufrufe"], "likes": point.get("likes") or 0, "comments": point.get("kommentare") or 0,
                        "shares": 0})
            added += 1
    if added:
        notes.append(f"{added} Video(s) mit Zahlen der Messung (öffentlich, ohne API) ausgewertet.")


# --------------------------------------------------------------------------- Auswertung

def classify(rows: list[dict]) -> list[tuple[dict, float, float]]:
    """(Eintrag, gut, schlecht) je Video: Reichweite pro Tag (auf MAX_ALTER_TAGE gedeckelt) im Vergleich zum Median
    derselben Plattform. Mittelmaß zählt schwach in beide Richtungen."""
    result = []
    for ziel in ("youtube", "tiktok"):
        group = [r for r in rows if r["ziel"] == ziel]
        if len(group) < 3:
            continue
        rates = {id(r): r["punkte"] / min(r["alter_tage"], MAX_ALTER_TAGE) for r in group}
        median = statistics.median(rates.values()) or 1.0
        for r in group:
            ratio = rates[id(r)] / median
            result.append((r, 1.0, 0.0) if ratio >= GUT else (r, 0.0, 1.0) if ratio <= SCHLECHT else (r, 0.25, 0.25))
    return result


def weights(classified: list[tuple[dict, float, float]]) -> dict:
    out: dict[str, dict] = {}
    for r, good, bad in classified:
        for knob, arm in (r.get("varianten") or {}).items():
            if knob == "_grund" or not isinstance(arm, str):
                continue
            cell = out.setdefault(knob, {}).setdefault(arm, {"gut": 0.0, "schlecht": 0.0, "n": 0})
            cell["gut"] += good
            cell["schlecht"] += bad
            cell["n"] += 1
    for arms in out.values():
        for cell in arms.values():
            cell["gut"], cell["schlecht"] = round(cell["gut"], 2), round(cell["schlecht"], 2)
            cell["quote"] = round((cell["gut"] + 1) / (cell["gut"] + cell["schlecht"] + 2), 3)
    return out


def winners(gewichte: dict) -> list[dict]:
    """Je Stellschraube die Variante mit der besten Erfolgsquote – nur mit genug Videos und klarem Vorsprung."""
    out = []
    for knob, arms in gewichte.items():
        ranked = sorted(((c["quote"], a, c) for a, c in arms.items() if c["n"] >= MIN_JE_VARIANTE), reverse=True)
        if len(ranked) >= 2 and ranked[0][0] - ranked[1][0] >= VORSPRUNG:
            out.append({"stellschraube": knob, "variante": ranked[0][1], "quote": ranked[0][0], "videos": ranked[0][2]["n"],
                        "vorsprung": round(ranked[0][0] - ranked[1][0], 3)})
    return out


def reason(measured: int, uploads: int, win: list[dict], notes: list[str]) -> tuple[str, str]:
    if measured < MIN_VIDEOS:
        return "erkundung", (f"Erst {measured} von {MIN_VIDEOS} nötigen Videos mit Zahlen ({uploads} Uploads erfasst) – "
                             "zu wenig für Schlüsse; alle Varianten bleiben gleichberechtigt (Erkundung).")
    if not win:
        return "lernend", (f"{measured} Videos ausgewertet, aber noch keine Variante mit klarem Vorsprung "
                           f"(≥ {MIN_JE_VARIANTE} Videos und ≥ {int(VORSPRUNG * 100)} Punkte Quote) – der Bandit gewichtet vorsichtig.")
    return "lernend", ("Gewinner: " + ", ".join(f"{w['stellschraube']}={w['variante']}" for w in win)
                       + f" ({measured} Videos). Mindestens 20 % der Videos erkunden weiter.")


def run() -> dict:
    started = time.monotonic()
    notes: list[str] = []
    uploads = (common.read_json("uploads.json", {}) or {}).get("eintraege", [])
    cutoff = now() - timedelta(days=90)
    rows = [r for r in uploads if (parse_time(r.get("hochgeladen", "")) or now()) >= cutoff]
    measured = measure(rows, notes) if rows else []
    if not rows:
        notes.append("Noch keine Uploads in firma_daten/uploads.json – es gibt nichts auszuwerten (Erkundung).")
    classified = classify(measured)
    gewichte = weights(classified) if len(classified) >= MIN_VIDEOS else {}
    win = winners(gewichte)
    mode, why = reason(len(classified), len(rows), win, notes)
    data = {"erzeugt": iso(), "modus": mode, "begruendung": why, "gewinner": win,
            "datenlage": {"uploads": len(rows), "gemessen": len(classified), "mindestens": MIN_VIDEOS,
                          "je_variante": MIN_JE_VARIANTE, "erkundung_mindestens": 0.2,
                          "app_bewertungen": "wirken direkt über vorlieben.varianten_gut/_schlecht im Auftrag"},
            "hinweise": notes, "gewichte": gewichte}
    changed = common.write_json("lernen.json", data)
    common.record_status("lernen", started, True, f"{mode}: {len(classified)} Videos ausgewertet, {len(win)} Gewinner"
                         + ("" if changed else " (unverändert)"), notes)
    return data


def main_merge(argv: list[str]) -> int:
    added = merge_uploads(argv[0]) if argv else 0
    print(f"{added} neue Upload-Einträge aufgenommen.")
    return 0


if __name__ == "__main__":
    sys.exit(main_merge(sys.argv[1:]))
