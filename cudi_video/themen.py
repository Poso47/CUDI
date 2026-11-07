"""Themen-Wissensstruktur: Jedes Video dreht sich um den Themenkern – die Frage, die Zuschauer wirklich haben.

Der Planer legt beim Deuten des Wunsches fest (`spec.focus`):
* **frage** – der Themenkern als Zuschauerfrage („Wie steuert mein Unterbewusstsein, was ich tue und fühle?“),
* **aspekte** – 3–6 Unterthemen, die das Video abdeckt (Wahrnehmung, Entscheidungen, Gewohnheiten …),
* **nicht** – Randthemen, die nicht gefragt sind (Begriffsgeschichte, Namensherkunft, Biografien).

Jede Schreibaufgabe (Fakten, Ranking-Erzählung, Story-Lektorat) bekommt den Themenkern mit und erzählt nach
derselben Wissensstruktur: Aufhänger → Kernaussage → Erklärung (wie/warum) → Bedeutung für dich. Die Prüfregeln
(nichts erfinden, Zahlen werttreu) bleiben unverändert – die Struktur bestimmt nur, WAS aus den Quellen erzählt wird.
"""

from __future__ import annotations

import re

from .spec import VideoSpec

TOPIC_RULES = (
    "Themenkern: Alles im Video beantwortet die Frage in „themenkern“ – aus immer neuer Richtung (siehe „aspekte“). "
    "Wähle nur Inhalte, die genau dieses Thema betreffen und die Zuschauer direkt angehen; Randthemen aus "
    "„nicht_gemeint“ (z. B. Begriffsgeschichte, Namensherkunft, Biografien von Forschern, Jahreszahlen der "
    "Forschung) lässt du weg, außer der Wunsch fragt danach."
)

KNOWLEDGE_STRUCTURE = (
    "Wissensstruktur je Platz – erzähle MEHR als den nackten Fakt: (1) Aufhänger: ein Bild im Kopf oder eine Frage "
    "aus dem Alltag; (2) Kernaussage; (3) Erklärung: wie und warum es so ist (Mechanismus, Hintergrund, ein Beispiel "
    "aus der Quelle); (4) Bedeutung für dich: was das im eigenen Leben heißt. Kein Fazit-Satz am Ende. Formuliere "
    "jeden Platz anders: keine wiederkehrenden Satzanfänge oder Floskeln über die Plätze hinweg (nicht jedes Mal "
    "„Für dich heißt das …“ oder „Stell dir vor …“) – mal eine Frage, mal ein Beispiel, mal ein Vergleich."
)


def focus(spec: VideoSpec, lang: str) -> dict:
    """Themenkern einer Sprache für die Schreibaufgaben (ohne Planer-Angabe: der Titel)."""
    f = spec.focus or {}
    question = (f.get("frage") or {}).get(lang) or (f.get("frage") or {}).get("de") or spec.title.get(lang, "")
    return {"themenkern": question, "aspekte": list(f.get("aspekte") or []), "nicht_gemeint": list(f.get("nicht") or [])}


def parse_focus(answer: dict) -> dict:
    """Themenkern aus der Planer-Antwort (gekürzt, nur Text)."""
    def short(text: str, n: int = 48) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) <= n else text[:n].rsplit(" ", 1)[0].rstrip(" ,:;–-")

    def texts(key: str, limit: int) -> list[str]:
        return [short(str(t)) for t in (answer.get(key) or [])[:limit] if str(t).strip()]

    frage = {lang: str(answer.get(f"themenkern_{lang}") or "").strip()[:160] for lang in ("de", "en")}
    return {"frage": {k: v for k, v in frage.items() if v}, "aspekte": texts("aspekte", 6), "nicht": texts("nicht_gemeint", 6)}


def matches_aspect(aspect: str, aspects: list[str]) -> bool:
    """Gehört ein Fakt zu einem der geplanten Aspekte? Ohne Aspekt-Liste passt alles."""
    if not aspects:
        return True
    a = aspect.strip().lower()
    return bool(a) and any(a == x.lower() or a in x.lower() or x.lower() in a for x in aspects)
