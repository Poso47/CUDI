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
    if auftrag and auftrag.get("bestaetigt_erlaubnis"):
        z.append("- Erlaubnis: Der Nutzer hat bestätigt, dass er die Erlaubnis des Creators zum Clippen hat.")
    f = info["fenster"]
    z.append(f"- Fenster in der Quelle: {f['start']}–{f['ende']} s ({'vorgegeben' if f['erzwungen'] else 'automatisch nach Regeln'}; "
             f"Auswahl: {info.get('auswahl')})")
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
