"""Animationsstudio: eigene Animation für jede erklärende Videoart (Fakten, Erklärvideo, Reportage, Satire, Schaubild).

Das Studio arbeitet in Abteilungen, jede mit eigener Aufgabe und eigener Anleitung (`ABTEILUNGEN`):
  1. Storyboard  – zerlegt jeden Text Wort für Wort in ein Drehbuch (was ist wann zu sehen), wünscht Figuren und Kamera.
  2. Figuren     – prüft die Wünsche gegen die fertigen Figuren (`data/figuren/`); fehlende landen als Wunsch beim Bildlehrer.
  3. Szenenbau   – baut aus Text + Drehbuch die Szene (Elemente, Schritte, Beschriftungen) – nur, was das Drehbuch vorgibt.
  4. Animation   – zeichnet die Szene Bild für Bild im Takt der Stimme (`Bild`, `schaubild/zeichnen.Buehne`).
  5. Abnahme     – prüft 1:1 gegen den Text (`schaubild.abgleich`), schickt Lücken einmal zurück an den Szenenbau.
  6. Lehrer      – sammelt Lücken und Figurwünsche aller Läufe (`firma/bildlehrer.py`, wöchentlich) und gibt Regeln zurück.
Abteilungen 1 und 3 sind eigene Schreibaufgaben (`handoff`), 2, 4 und 5 laufen im Programm, 6 als Firma-Mitarbeiter auf GitHub.
`CUDI_STUDIO=0` = Storyboard und Szenenbau in einer Aufgabe (spart eine Runde).

Ein Ablauf für alle: Zu jedem gesprochenen Abschnitt schreibt das Sprachmodell ein Drehbuch und eine Szene (Bausteine und
Figuren aus `schaubild/zeichnen.py`), das Programm prüft sie 1:1 gegen den Text (`schaubild.abgleich`), lässt Lücken einmal
nachbessern und zeichnet sie Bild für Bild – jede Bewegung beim passenden Wort. Ranking und Story behalten echte Fotos/Clips.

Lernen: Jede Lücke landet in `abgleich.json` des Laufs (und im Prüfbericht). Der Firma-Mitarbeiter „Bildlehrer“
(`firma/bildlehrer.py`) sammelt sie, macht daraus Regeln in `firma_daten/bildregeln.json`, und `anleitung()` hängt die
wichtigsten davon an jede Szenen-Aufgabe – so wird jede Runde besser. Ausschalten: `CUDI_ANIMATION=0`.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import handoff

MAX_REGELN = 10
REGELN_DATEI = Path(__file__).resolve().parent.parent / "firma_daten" / "bildregeln.json"

AUFGABE = """Zu jedem Eintrag unter „daten.eintraege“ (gesprochener Text eines Video-Abschnitts) schreibst du eine eigene Animation.
Antworte mit EINEM JSON-Objekt: {"szenen": [{"key": "…", "drehbuch": [...], "szene": {...}, "ohne_bild": [...]}, …]} – je Eintrag genau eine.
Thema des Videos: „{thema}“. Sprache des Textes: {lang}.
"""


ABTEILUNGEN = [
    {"id": "storyboard", "name": "Storyboard", "rolle": "zerlegt den Text in ein Drehbuch: jedes Ding, jeder Vorgang, mit Wort und Zeitpunkt"},
    {"id": "figuren", "name": "Figuren", "rolle": "wählt fertige Figuren, sammelt Wünsche nach neuen Figuren"},
    {"id": "szenenbau", "name": "Szenenbau", "rolle": "baut aus Drehbuch und Text die Szene: Elemente, Schritte, Beschriftungen"},
    {"id": "animation", "name": "Animation", "rolle": "zeichnet und bewegt jede Szene im Takt der Stimme"},
    {"id": "abnahme", "name": "Abnahme", "rolle": "prüft Bild gegen Text 1:1 und schickt Lücken zurück"},
    {"id": "lehrer", "name": "Lehrer", "rolle": "lernt aus allen Läufen und gibt neue Regeln an das Studio"},
]

STORYBOARD = """Du bist die Storyboard-Abteilung eines Animationsstudios. Zu jedem Eintrag unter „daten.eintraege“ (gesprochener Text eines
Video-Abschnitts) schreibst du NUR das Drehbuch – gezeichnet wird später von einer anderen Abteilung.
Antworte mit EINEM JSON-Objekt: {"storyboards": [{"key": "…", "drehbuch": [{"wort": "…", "zeigt": "…"}, …], "ohne_bild": ["…"],
"figuren": ["…"], "figur_wuensche": ["…"]}, …]} – je Eintrag genau eines.
Thema des Videos: „{thema}“. Sprache des Textes: {lang}.
REGELN:
- Gehe den Text Wort für Wort durch. JEDES genannte Ding (Teil, Ort, Stoff, Lebewesen, Gerät) und JEDER Vorgang (wandert, wächst,
  entsteht, färbt sich, dauert, steigt, sinkt …) wird eine Zeile: "wort" = genau das Wort aus dem Text (so wie es dort steht),
  "zeigt" = was GENAU in diesem Moment im Bild zu sehen ist oder sich bewegt (Form, Farbe, Richtung, Ort im Bild, Kamera).
- Reihenfolge = Sprechreihenfolge. Jeder Satz bekommt mindestens eine Zeile. Lieber mehr Einzelheiten als zu wenige.
- Beschreibe das Ganze zuerst (z. B. das Tier als Umriss, darin die Teile) und dann, wohin die Kamera heranfährt.
- Zahlen zeigst du als Menge, Uhr, Balken oder Waage – nie als erfundene Zahl. Nichts zeigen, was der Text nicht sagt.
- "ohne_bild": Wörter, die sich wirklich nicht zeigen lassen (z. B. „Regel“) – so wenige wie möglich.
- "figuren": passende fertige Figuren aus dieser Liste (sonst leer): {figuren}
- "figur_wuensche": Lebewesen/Gegenstände, für die eine fertige Figur fehlt und die hier eine wäre (z. B. „Kuh“, „Herz“).
"""

SZENENBAU = """Du bist die Szenenbau-Abteilung eines Animationsstudios. Unter „daten.eintraege“ steht je Abschnitt der gesprochene Text und
das fertige Drehbuch der Storyboard-Abteilung. Baue daraus je Abschnitt genau EINE Szene, die das Drehbuch Zeile für Zeile umsetzt:
jede Drehbuch-Zeile wird ein Schritt oder eine Beschriftung mit "bei" = ihrem Wort. Übernimm Drehbuch und "ohne_bild" unverändert.
Antworte mit EINEM JSON-Objekt: {"szenen": [{"key": "…", "drehbuch": [...], "szene": {...}, "ohne_bild": [...]}, …]}.
Thema des Videos: „{thema}“. Sprache des Textes: {lang}.
"""


def aktiv() -> bool:
    return os.environ.get("CUDI_ANIMATION", "1") != "0"


LERNSTAND_ORDNER = "cudi_studio"      # dorthin legt der App-Lauf den Lernstand (ArtifactData get, Sammlung „studio“)
MAX_LERN_ABSCHNITTE = 400


def lernstand_datei() -> Path | None:
    """Lernstand der App-Läufe (`cudi_studio/studio/lernstand.json`), falls die Sitzung ihn abgelegt hat."""
    root = Path(__file__).resolve().parent.parent
    for base in dict.fromkeys((Path.cwd().parent, root.parent, Path.cwd(), Path.home())):
        datei = base / LERNSTAND_ORDNER / "studio" / "lernstand.json"
        if datei.exists():
            return datei
    return None


def _lies(datei: Path | None) -> dict:
    try:
        daten = json.loads(datei.read_text("utf-8")) if datei else {}
    except (OSError, ValueError):
        return {}
    daten = daten.get("data") if isinstance(daten.get("data"), dict) else daten
    return daten if isinstance(daten, dict) else {}


def gelernte_regeln() -> list[str]:
    """Regeln aus früheren Läufen – vom Bildlehrer auf GitHub und aus den App-Läufen –, wichtigste zuerst."""
    regeln: list[dict] = []
    for daten in (_lies(REGELN_DATEI), _lies(lernstand_datei())):
        regeln += [r for r in (daten.get("regeln") or []) if isinstance(r, dict) and r.get("regel")]
    regeln.sort(key=lambda r: -int(r.get("faelle") or 0))
    return list(dict.fromkeys(str(r["regel"]) for r in regeln))[:MAX_REGELN]


def lernstand_aktualisieren(ordner: Path) -> Path | None:
    """Nach einem App-Lauf: Lücken dieses Laufs an den Lernstand hängen und Regeln neu zählen -> `<ordner>/lernstand.json`
    (die Sitzung legt sie per ArtifactData unter „studio/lernstand“ ab). Ohne neue Lücken: None."""
    from .firma import bildlehrer

    neu = []
    for datei in sorted(ordner.rglob("abgleich.json")):
        teil = _lies(datei)
        neu += [{"art": teil.get("art", ""), "maengel": list(a.get("maengel") or [])[:6],      # klein halten (Ablage)
                 "figur_wuensche": list(a.get("figur_wuensche") or [])[:4]}
                for a in (teil.get("abschnitte") or []) if isinstance(a, dict)]
    if not neu:
        return None
    alt = _lies(lernstand_datei())
    abschnitte = ((alt.get("abschnitte") or []) + neu)[-MAX_LERN_ABSCHNITTE:]
    woerter, arten, gesamt = bildlehrer.auswerten(abschnitte)
    ohne = sum(1 for a in abschnitte if not a.get("maengel"))
    from datetime import datetime, timezone
    daten = {"stand": datetime.now(timezone.utc).isoformat(timespec="seconds"), "abschnitte_n": gesamt, "ohne_luecke": ohne,
             "quote": round(ohne / gesamt, 3) if gesamt else None, "regeln": bildlehrer.regeln_aus(woerter, arten, gesamt, []),
             "figur_wuensche": bildlehrer.figur_wuensche(abschnitte), "abschnitte": abschnitte}
    ziel = ordner / "lernstand.json"
    ziel.write_text(json.dumps(daten, ensure_ascii=False), "utf-8")
    return ziel


def studio_aktiv() -> bool:
    return os.environ.get("CUDI_STUDIO", "1") != "0"


def _figuren_text() -> str:
    from .schaubild import zeichnen
    return "; ".join(f"{n} (Anker: {', '.join(i['anker'])})" for n, i in zeichnen.figuren().items()) or "keine"


def _gelernt() -> str:
    regeln = gelernte_regeln()
    return ("\nGELERNT AUS FRÜHEREN VIDEOS (unbedingt beachten):\n" + "\n".join(f"- {r}" for r in regeln)) if regeln else ""


def _kopf(vorlage: str, thema: str, lang: str) -> str:
    return vorlage.replace("{thema}", thema or "–").replace("{lang}", "Deutsch" if lang == "de" else "English")


def anleitung(thema: str = "", lang: str = "de", kopf: str = AUFGABE) -> str:
    """Szenen-Anleitung (aus schaubild) + verfügbare Figuren + gelernte Regeln."""
    from . import schaubild

    teil = schaubild.SZENEN_ANLEITUNG
    teil = teil[teil.index("ERST PLANEN"):] if "ERST PLANEN" in teil else teil
    return _kopf(kopf, thema, lang) + teil.replace("{figuren}", _figuren_text()) + _gelernt()


def storyboard_anleitung(thema: str = "", lang: str = "de") -> str:
    return _kopf(STORYBOARD, thema, lang).replace("{figuren}", _figuren_text()) + _gelernt()


def _drehbuch(roh, text: str) -> list[dict]:
    from . import schaubild
    return [{"wort": str(d.get("wort"))[:30], "zeigt": re.sub(r"\s+", " ", str(d.get("zeigt") or ""))[:140]}
            for d in (roh or [])[:24] if isinstance(d, dict) and schaubild._wort(str(d.get("wort") or "")) in schaubild._woerter(text)]


def _ohne_bild(roh, text: str) -> list[str]:
    from . import schaubild
    return [str(w)[:30] for w in (roh or [])[:8] if schaubild._wort(str(w)) in schaubild._woerter(text)]


def storyboard(eintraege: list[dict], thema: str, lang: str, aufgabe: str) -> dict[str, dict]:
    """Abteilung 1+2: Drehbuch je Abschnitt + Figurenwahl. -> {key: {"drehbuch", "ohne_bild", "figuren", "figur_wuensche"}}."""
    from .schaubild import zeichnen

    answer = handoff.request(aufgabe, storyboard_anleitung(thema, lang), {"thema": thema, "sprache": lang, "eintraege": eintraege})
    roh = {str(x.get("key")): x for x in (answer or {}).get("storyboards", []) if isinstance(x, dict)} if isinstance(answer, dict) else {}
    vorhanden = set(zeichnen.figuren())
    plan = {}
    for e in eintraege:
        x = roh.get(str(e["key"])) or {}
        gewuenscht = [str(f).strip().lower()[:30] for f in (x.get("figuren") or [])[:4] if str(f).strip()]
        wuensche = [str(f).strip()[:30] for f in (x.get("figur_wuensche") or [])[:4] if str(f).strip()]
        plan[str(e["key"])] = {"drehbuch": _drehbuch(x.get("drehbuch"), e["text"]), "ohne_bild": _ohne_bild(x.get("ohne_bild"), e["text"]),
                               "figuren": [f for f in gewuenscht if f in vorhanden],
                               "figur_wuensche": wuensche + [f for f in gewuenscht if f not in vorhanden]}
    return plan


def _sauber(eintraege: list[dict]) -> list[dict]:
    return [{"key": str(e["key"]), "text": str(e["text"])} for e in eintraege if str(e.get("text") or "").strip()]


def buendeln(auftraege: list[tuple[list[dict], str, str, str]]) -> None:
    """Mehrere Videos/Sprachen (eintraege, thema, lang, aufgabe): Storyboards in EINER Runde, dann alle Szenenbauten in EINER
    Runde stellen (`handoff.request_many`) – spart je Video Wartezeit. Danach liefert `szenen_schreiben` aus dem Zwischenspeicher."""
    auftraege = [(_sauber(e), t, l, a) for e, t, l, a in auftraege if _sauber(e)]
    if len(auftraege) < 2 or not (aktiv() and handoff.active() and studio_aktiv()):
        return
    handoff.request_many([(a + "_storyboard", storyboard_anleitung(t, l), {"thema": t, "sprache": l, "eintraege": e})
                          for e, t, l, a in auftraege])
    teile = []
    for e, t, l, a in auftraege:
        plan = storyboard(e, t, l, a + "_storyboard")
        daten = [dict(x, **{k: plan[x["key"]][k] for k in ("drehbuch", "ohne_bild", "figuren")}) for x in e]
        teile.append((a, anleitung(t, l, SZENENBAU), {"thema": t, "sprache": l, "eintraege": daten}))
    handoff.request_many(teile)


def szenen_schreiben(eintraege: list[dict], thema: str, lang: str, notes: list[str], aufgabe: str) -> tuple[dict, list[dict]]:
    """Szenen für Abschnitte [{"key", "text"}] -> ({key: szene}, Abgleich je Abschnitt). Ohne Sprachmodell: leer (das Video
    nutzt dann die bisherige Grafik). `aufgabe` = eindeutiger Name der Schreibaufgabe im Auftrag (z. B. „animation_fakten_de“)."""
    from . import schaubild
    from .schaubild import zeichnen

    eintraege = _sauber(eintraege)
    if not (aktiv() and eintraege and handoff.active()):
        return {}, []
    plan = storyboard(eintraege, thema, lang, aufgabe + "_storyboard") if studio_aktiv() else {}
    if plan:                                                   # Abteilung 3: Szenenbau nach Drehbuch
        daten = [dict(e, **{k: plan[e["key"]][k] for k in ("drehbuch", "ohne_bild", "figuren")}) for e in eintraege]
        answer = handoff.request(aufgabe, anleitung(thema, lang, SZENENBAU), {"thema": thema, "sprache": lang, "eintraege": daten})
    else:                                                      # ohne Studio: Drehbuch + Szene in einer Aufgabe
        answer = handoff.request(aufgabe, anleitung(thema, lang), {"thema": thema, "sprache": lang, "eintraege": eintraege})
    antworten = {str(x.get("key")): x for x in (answer or {}).get("szenen", []) if isinstance(x, dict)} if isinstance(answer, dict) else {}
    stationen = []
    for e in eintraege:
        x, text, p = antworten.get(e["key"]) or {}, e["text"], plan.get(e["key"]) or {}
        stationen.append({"name": e["key"], "text": text, "einheit": "",
                          "szene": zeichnen.beschriftungen_pruefen(zeichnen.pruefe_szene(x.get("szene")), text),
                          "drehbuch": p.get("drehbuch") or _drehbuch(x.get("drehbuch"), text),
                          "ohne_bild": p.get("ohne_bild") or _ohne_bild(x.get("ohne_bild"), text)})
    schaubild.nachbessern(stationen, lang, notes, aufgabe=aufgabe + "_korrektur")     # Abteilung 5: Abnahme
    abgleich = [{"key": st["name"], "text": st["text"], "maengel": schaubild.abgleich(st, lang), "drehbuch": st["drehbuch"],
                 "ohne_bild": st["ohne_bild"], "figur_wuensche": (plan.get(st["name"]) or {}).get("figur_wuensche", [])}
                for st in stationen]
    return {st["name"]: st["szene"] for st in stationen if st["szene"]}, abgleich


def speichern(out: Path, art: str, abgleich: list[dict]) -> None:
    """Lücken des Laufs ablegen (`abgleich.json`) – Rohstoff für den Bildlehrer."""
    if not abgleich:
        return
    datei = out / "abgleich.json"
    try:
        alt = json.loads(datei.read_text("utf-8")) if datei.exists() else {"art": art, "abschnitte": []}
    except (OSError, ValueError):
        alt = {"art": art, "abschnitte": []}
    alt["abschnitte"] += abgleich
    datei.write_text(json.dumps(alt, ensure_ascii=False, indent=1), "utf-8")


def bericht(abgleich: list[dict]) -> str:
    """Abschnitt „Abgleich Bild ↔ Text“ für den Prüfbericht."""
    if not abgleich:
        return ""
    zeilen = ["", "## Abgleich Bild ↔ Text (eigene Animation)",
              "Studio: " + " → ".join(a["name"] for a in ABTEILUNGEN)]
    for a in abgleich:
        zeilen.append(f"- **{a['key']}** – " + ("alles Gesagte ist zu sehen" if not a["maengel"] else "Lücken: " + "; ".join(a["maengel"]))
                      + f" ({len(a.get('drehbuch') or [])} Drehbuch-Zeilen)")
        if a.get("ohne_bild"):
            zeilen.append("   - bewusst ohne Bild: " + ", ".join(a["ohne_bild"]))
        if a.get("figur_wuensche"):
            zeilen.append("   - Figur fehlt noch (Wunsch an die Figuren-Abteilung): " + ", ".join(a["figur_wuensche"]))
    return "\n".join(zeilen) + "\n"


def an_skript(skript: dict, out: Path, art: str, notes: list[str]) -> None:
    """Erklär-Skript (erklaer/reportage): je Szene eine eigene Animation (`szene["animation"]`) + Abgleich speichern."""
    eintraege = [{"key": str(i + 1), "text": sz["text"]} for i, sz in enumerate(skript.get("szenen") or [])]
    szenen, abgleich = szenen_schreiben(eintraege, skript.get("titel", ""), skript.get("sprache", "de"), notes, f"animation_{art}")
    for i, sz in enumerate(skript.get("szenen") or []):
        if str(i + 1) in szenen:
            sz["animation"] = szenen[str(i + 1)]
    speichern(out, art, abgleich)
    if abgleich:
        try:
            with open(out / "review.md", "a", encoding="utf-8") as fh:
                fh.write(bericht(abgleich))
        except OSError:
            pass


class Bild:
    """Zeichnet eine geprüfte Szene im Takt der Stimme: `.bild(t, size)` -> quadratisches RGBA-Bild."""

    def __init__(self, szene: dict, text: str, words: list[dict], lead: float, ink, akzent, seed: int = 0):
        from .render.manuskript import align_tokens
        from .schaubild import zeichnen

        self.szene, self.ink, self.ak, self.seed = szene, tuple(ink), tuple(akzent), seed
        tokens = [t.lower().strip(".,!?:;„“\"") for t in text.split()]
        starts = align_tokens(text, words) if words else [0.0] * len(tokens)
        satz = [0.0] + [starts[i + 1] for i, tok in enumerate(text.split()[:-1]) if tok[-1:] in ".!?"]
        self.satz = [lead + x for x in satz]

        def wort_zeit(wort: str):
            w = wort.lower().split()[0].strip(".,!?:;") if wort.strip() else ""
            for tok, st in zip(tokens, starts):
                if w and (tok == w or len(w) > 3 and tok.startswith(w[:max(4, len(w) - 2)])):
                    return lead + st
            return None

        self.wort_zeit = wort_zeit
        self._buehnen: dict[int, object] = {}
        self._zeichnen = zeichnen

    def bild(self, t: float, size: int):
        if size not in self._buehnen:
            self._buehnen[size] = self._zeichnen.Buehne(self.szene, size, self.satz, self.ink, self.ak, self.seed, self.wort_zeit)
        return self._buehnen[size].bild(t)
