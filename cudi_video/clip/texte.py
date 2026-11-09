"""Titel, Beschreibungstexte und Prüfbericht für einen fertigen Clip (nur aus Transkript und Quelldaten – nichts erfunden)."""

from __future__ import annotations

import json
import re
from pathlib import Path


def _kurz(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    return cut + "…"


def titel(info: dict) -> str:
    """Titel aus dem Hook (erster Satz, höchstens 70 Zeichen); ohne Hook der Anfang des Transkripts."""
    if info.get("titel_vorschlag"):                       # geprüfter Vorschlag aus dem Inhaltsurteil
        return _kurz(str(info["titel_vorschlag"]).rstrip(".,;:"), 70)
    hook = (info.get("hook") or {}).get("text") or info.get("transkript") or "Clip"
    erster = re.split(r"(?<=[.?!])\s+", hook.strip())[0]
    return _kurz(erster.rstrip(".,;:"), 70)


def nennung(info: dict, url: str = "") -> str:
    """„Clip aus: <Titel/Kanal> – Quelle: <URL>“ (Creator-Nennung)."""
    q = info.get("quelle_info") or {}
    name = " / ".join(x for x in (q.get("titel"), q.get("kanal")) if x) or "Quelle"
    return f"Clip aus: {name} – Quelle: {url or q.get('url') or info.get('quelle', '')}"


def beschreibungen(info: dict, url: str = "", sprache: str = "de") -> tuple[str, str]:
    """(YouTube-Beschreibung, TikTok-Text), beide mit Creator-Nennung; YouTube mit #shorts."""
    t = titel(info)
    credit = nennung(info, url)
    tags = ["#shorts", "#clip", "#podcast"] + (["#deutsch"] if sprache == "de" else ["#english"] if sprache == "en" else [])
    yt = f"{t}\n\n{credit}\n\n{' '.join(tags)}\n"
    tt_credit = _kurz(credit, 160)
    tt = f"{_kurz(t, 90)}\n{tt_credit}\n{' '.join(tags[1:] + ['#fyp'])}\n"
    return yt, tt


def pruefbericht(info: dict, auftrag: dict | None = None) -> str:
    q = info.get("quelle_info") or {}
    z = [f"# Prüfbericht Clip", ""]
    z.append(f"- Quelle: {info.get('quelle')}")
    if q.get("titel") or q.get("kanal"):
        z.append(f"- Titel/Kanal der Quelle: {q.get('titel', '')} / {q.get('kanal', '')}")
    z.append(f"- Lizenz/Herkunft: {q.get('lizenz') or info.get('herkunft') or 'nicht angegeben (Standard-Lizenz der Plattform)'}")
    from . import erlaubnis as erl

    zeilen = erl.bericht_zeilen(info.get("erlaubnis"))
    if zeilen:
        z += zeilen
    if auftrag and auftrag.get("bestaetigt_erlaubnis"):
        z.append("- Erlaubnis: Der Nutzer hat bestätigt, dass er die Erlaubnis des Creators zum Clippen hat.")
    z.append(f"- Stil: {info.get('stil', 'zuschnitt')}")
    f = info["fenster"]
    z.append(f"- Fenster in der Quelle: {f['start']}–{f['ende']} s ({'vorgegeben' if f['erzwungen'] else 'automatisch nach Regeln'}; "
             f"Auswahl: {info.get('auswahl')})")
    u = info.get("urteil")
    if u:
        z.append(f"- Inhaltsurteil ({u['quelle']}): {u['punkte']}/10, Pointe: {'ja' if u['pointe'] else 'nein'}, "
                 f"ohne Vorwissen verständlich: {'ja' if u['verstaendlich'] else 'nein'} – {u['grund']}")
        for b in u.get("befunde") or []:
            z.append(f"- Titelvorschlag verworfen: {b}")
    sg = info.get("signale") or {}
    if sg:
        z.append(f"- Auswahl-Signale: {', '.join(f'{k}={v}' for k, v in sg.items())}; Bildschnitte erkannt: "
                 f"{info.get('bildschnitte', 0)}")
    h = info.get("hook")
    if h:
        z.append(f"- Hook ({h['start']}–{h['ende']} s, Punkte {h['wert']}): „{h['text']}“ – "
                 + ("als Teaser vorangestellt" if h["teaser_vorangestellt"] else "steht am Anfang, kein Teaser nötig"))
    else:
        z.append("- Hook: kein starker Kandidat gefunden")
    z.append(f"- Dauer: {info['dauer']} s, Pausen entfernt: {info['pausen_entfernt_s']} s, erkannte Personen: {info['personen']}")
    arten = [s["art"] for s in info["schnitte"]]
    z.append(f"- Schnitte: {len(arten)} (davon Blitz: {arten.count('blitz')}), Untertitel-Gruppen: {info['untertitel']['gruppen']}")
    for hinweis in info.get("hinweise", []):
        z.append(f"- Hinweis: {hinweis}")
    z += ["", "## Transkript (Ausschnitt)", "", info.get("transkript", "")[:3000]]
    return "\n".join(z) + "\n"


def schreibe(ausgabe: Path, info: dict, auftrag: dict | None = None, url: str = "", sprache: str = "de") -> dict:
    """Schreibt youtube.txt, tiktok.txt, review.md und spec.json (Titel) neben clip.mp4; gibt das `videos`-Ergebnis zurück."""
    yt, tt = beschreibungen(info, url, sprache)
    (ausgabe / "youtube.txt").write_text(yt, "utf-8")
    (ausgabe / "tiktok.txt").write_text(tt, "utf-8")
    (ausgabe / "review.md").write_text(pruefbericht(info, auftrag), "utf-8")
    (ausgabe / "spec.json").write_text(json.dumps({"title": {"de": titel(info)}}, ensure_ascii=False), "utf-8")
    return {"clip": {"video": "clip.mp4", "duration": info["dauer"], "description_file": "youtube.txt",
                     "caption_file": "tiktok.txt"}}


def ranking_titel(info: dict) -> str:
    return _kurz(f"Top {len(info['teile'])} Twitch-Clips: {info['kanal']}", 60)


def ranking_beschreibungen(info: dict, sprache: str = "de") -> tuple[str, str]:
    """Texte fürs Twitch-Ranking: nur belegte Angaben (Kanal, Zeitraum, Clip-Links), Creator-Nennung."""
    zeitraum = {"24hr": "der letzten 24 Stunden", "7d": "der letzten 7 Tage", "30d": "der letzten 30 Tage"}.get(
        info.get("zeitraum"), "des gewählten Zeitraums")
    t = ranking_titel(info)
    quellen = "\n".join(f"#{p['platz']} {p['url']}" for p in sorted(info["teile"], key=lambda x: x["platz"]))
    credit = f"Die meistgesehenen Twitch-Clips von {info['kanal']} {zeitraum}. Quelle: {info['quelle']}"
    tags = ["#shorts", "#twitch", "#clips"]
    yt = f"{t}\n\n{credit}\n{quellen}\n\n{' '.join(tags)}\n"
    tt = f"{_kurz(t, 90)}\n{_kurz(credit, 160)}\n{' '.join(tags[1:] + ['#fyp'])}\n"
    return yt, tt


def ranking_pruefbericht(info: dict, auftrag: dict | None = None) -> str:
    from . import erlaubnis as erl

    z = ["# Prüfbericht Twitch-Ranking", "", f"- Kanal: {info['kanal']} (Zeitraum {info['zeitraum']}), Quelle: {info['quelle']}"]
    z += erl.bericht_zeilen(info.get("erlaubnis"))
    z.append(f"- Stil: {info.get('stil')}; Dauer {info['dauer']} s; Reihenfolge als Countdown (Platz 1 zuletzt)")
    for p in sorted(info["teile"], key=lambda x: x["platz"]):
        z.append(f"- Platz {p['platz']}: „{p['titel']}“ – {p['aufrufe']} Aufrufe laut Twitch, {p['dauer']} s – {p['url']}")
    for h in info.get("hinweise", []):
        z.append(f"- Hinweis: {h}")
    z += ["", "## Transkript (Ausschnitt)", "", info.get("transkript", "")[:3000]]
    return "\n".join(z) + "\n"


def schreibe_ranking(ausgabe: Path, info: dict, auftrag: dict | None = None, sprache: str = "de") -> dict:
    yt, tt = ranking_beschreibungen(info, sprache)
    ausgabe.mkdir(parents=True, exist_ok=True)
    (ausgabe / "youtube.txt").write_text(yt, "utf-8")
    (ausgabe / "tiktok.txt").write_text(tt, "utf-8")
    (ausgabe / "review.md").write_text(ranking_pruefbericht(info, auftrag), "utf-8")
    (ausgabe / "spec.json").write_text(json.dumps({"title": {"de": ranking_titel(info)}}, ensure_ascii=False), "utf-8")
    (ausgabe / "clip.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, default=str), "utf-8")
    return {"clip": {"video": "clip.mp4", "duration": info["dauer"], "description_file": "youtube.txt",
                     "caption_file": "tiktok.txt"}}
