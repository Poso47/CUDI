"""Schaubild: Erklärvideo in Stationen – je Station ein Bild im gewählten Bildstil, EINE belegte Zahl, Etiketten, Alltagsbezug.

Auftrag `{"art": "schaubild", "thema", "sprache", "stationen": 3–9, "stil", "seitenformat": "9:16"|"16:9"}`.
Wahrheit: Jede Station braucht einen wörtlichen Beleg aus der Quelle (Wikipedia-Artikel zum Thema); Zahlen im Sprechtext
müssen im Beleg stehen, neue Eigennamen gibt es nicht. Unbelegtes fliegt raus, zu wenig Belegtes = ehrlicher Abbruch.
Die Bilder sind Illustrationen (KI oder vom Renderer gezeichnet) und in jedem Bild als solche gekennzeichnet.
Vorbild und Stilregeln: docs/gehirn/vorbilder.md.
"""

from __future__ import annotations

import functools
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import logging

from .. import handoff, net, textcheck
from . import zeichnen

log = logging.getLogger(__name__)
TASK = "schaubild"
MIN_STATIONEN, MAX_WORDS, TEXT_LIMIT = 3, 60, 9000
MAX_BILDER = 3                            # Bilder je Station (eines je Satz)
# Bildmodelle mit Pollinations-Konto, günstigste zuerst. NICHT kostenlos: Jedes Bild kostet Guthaben („Pollen“, geprüft 11/2026:
# flux ≈ 0,002 $, zimage ≈ 0,004 $, klein ≈ 0,005 $, flux.1.1-pro ≈ 0,03 $ je Bild). Ein Konto hat nur ein kleines Gratis-Guthaben
# („Quest Pollen“); ist es leer (HTTP 402), geht es ohne Kosten mit dem alten, schwächeren Weg weiter.
MODELLE = ("flux", "zimage", "klein")
_guthaben_leer = [False]
MIN_KANTEN = 3.0                          # mittlere Kantenstärke (0–255), darunter gilt ein Bild als leer/unscharf
FORMATE = ("9:16", "16:9")
KATALOG = Path(__file__).resolve().parent.parent / "data" / "bildstile.json"

INSTRUCTIONS = """Schreibe das Skript für ein kurzes Erklärvideo in Stationen (Stil „Schaubild“) – nur aus den Quellen unter „quellen“.
Antworte mit EINEM JSON-Objekt:
{"titel": "≤ 60 Zeichen", "hook": "eine Frage, die neugierig macht", "versprechen": "ein Satz: was man gleich versteht",
 "stationen": [{"name": "1–2 Wörter", "text": "2–3 gesprochene Sätze", "zahl": "eine Zahl aus dem Beleg, z. B. 20", "einheit": "z. B. Stunden",
                "beleg": "WÖRTLICHES Zitat aus der Quelle (ein bis zwei Sätze, unverändert)", "quelle": "id der Quelle",
                "etiketten": ["1–2 Wörter", "…"],
                "bilder": ["englische Bildbeschreibung zu Satz 1", "… zu Satz 2", "… zu Satz 3"]}],
 "bild_hook": "englische Bildbeschreibung für den Einstieg (Alltagsszene zum Thema)",
 "bild_schluss": "englische Bildbeschreibung für den Schluss (Alltagsszene)",
 "schluss": "ein Satz mit Bezug zum Alltag"}
Regeln:
- Genau {n} Stationen in der natürlichen Reihenfolge des Vorgangs (Anfang → Ende). Jede Station erklärt EINEN Schritt.
- Jede Station hat einen wörtlichen Beleg aus der Quelle. Jede Zahl im Text steht genau so im Beleg. Keine Zahl ohne Beleg –
  dann lieber „zahl“ leer lassen. Keine neuen Namen, keine Wertungen, keine Übertreibung, nichts vermuten.
- Sprache des Textes: {lang}. Einfach und bildhaft: wenn möglich ein Vergleich oder ein Bezug zum Alltag („wie …“).
- Höchstens 3 Etiketten je Station; jedes Etikett ist ein Begriff, der im Text der Station vorkommt.
- Hook, Versprechen und Schluss enthalten keine Zahlen, die nicht in einem Beleg stehen.
- BILDER ERKLÄREN MIT: „bilder“ hat je Satz des Textes GENAU EINE Beschreibung (gleiche Reihenfolge, 1–3 Stück). Jedes Bild zeigt
  sichtbar genau das, was dieser Satz sagt – den Vorgang, den Ort, das Teil (z. B. Schnittbild/Querschnitt, Nahaufnahme, „vorher“ und im
  nächsten Bild „nachher“). Nenne das Hauptmotiv in jedem Bild gleich (gleiche Farben/Form), damit die Bilder wie eine Folge wirken.
  Konkret statt allgemein: nicht „an egg“, sondern „cutaway of a hen's oviduct, an orange yolk sliding through a spiral tube, clear
  egg white wrapping around it“. Nur darstellen, was der Beleg stützt; keine Schrift, keine Zahlen, keine Menschen im Bild."""

SZENEN_ANLEITUNG = """
EIGENE ANIMATION statt Bilder: Lass „bilder“, „bild_hook“ und „bild_schluss“ weg. Gib stattdessen je Station eine „szene“ an
(dazu „szene_hook“ und „szene_schluss“) – das Programm zeichnet und bewegt sie selbst.
ERST PLANEN, DANN ZEICHNEN: Schreibe je Station zuerst ein „drehbuch“ – die Liste ALLER Dinge und Vorgänge des Textes in Sprechreihenfolge:
  "drehbuch": [{"wort": "Wort aus dem Text", "zeigt": "was genau dann im Bild zu sehen ist oder passiert"}, …]
Jeder Eintrag des Drehbuchs MUSS in der Szene vorkommen: als Schritt oder Beschriftung mit "bei": dieses Wort. Es wird nachgeprüft:
jedes Hauptwort des Textes braucht eine Beschriftung oder einen Schritt, jeder Satz mindestens einen Schritt. Was sich wirklich nicht
zeigen lässt (z. B. „Regel“, „Überraschung“), kommt in "ohne_bild": ["Wort", …] – so kurz wie möglich.
OBERSTE REGEL – ALLES ZEIGEN, WAS GESAGT WIRD, GENAU DANN, WENN ES GESAGT WIRD:
- Gehe den Text Wort für Wort durch. JEDES genannte Ding (Teil, Ort, Stoff) ist als Element zu sehen und bekommt eine „beschriftung“
  mit genau dem Wort aus dem Text. JEDER genannte Vorgang (wandert, bildet sich, wächst, beginnt, färbt sich, dauert …) ist ein Schritt.
- Jeder Schritt und jede Beschriftung startet mit „bei“: dem Wort aus dem Text, bei dem es passiert (z. B. "bei": "wandert").
  Nur wenn kein Wort passt: „ab“ = Satznummer und „nach“ = Sekunden.
- Was wandert, bewegt sich; was entsteht, wächst oder erscheint; was sich verändert, wechselt Farbe oder bekommt eine Schicht; was dauert,
  bekommt eine Uhr. Zeige das Ganze (z. B. das Tier, das Gerät) als Umriss mit den Teilen darin und zoome dann mit der Kamera an die Stelle.
- Rechne mit 2–4 Schritten und 1–3 Beschriftungen je Satz. Lieber mehr Einzelheiten als ein leeres Bild.
Format: {"elemente": [...], "schritte": [...]}. Koordinaten 0–100 (0/0 = links oben, Mitte = 50/50), „groesse“ in Prozent der Bildbreite.
BILD FÜLLEN: Das Hauptelement (oder die Figur) ist groß (groesse 55–90) und steht von Anfang an da; alles zusammen füllt 70–90 % des
Bildes. Lebewesen, die es als Figur gibt (Liste unten), IMMER als Figur zeigen – nie aus Formen nachbauen. Jede Szene, in der ein
solches Lebewesen vorkommt oder handelt (auch „sie“, „die Bienen“), zeigt die Figur groß. Lieber 3–6 große, klare Elemente als viele kleine
Kugeln; Stoffe (Honig, Nektar, Wasser) als Tropfen/Form mit Beschriftung, Orte (Stock, Wabe) als Sechseck-Waben.
FIGUREN (fertig gezeichnete, lebendige Illustrationen – atmen, blinzeln, bewegen sich): Gibt es für das Thema eine passende Figur,
benutze sie statt sie aus Formen zu bauen: {"id": "huhn", "art": "figur", "figur": "huhn", "x": 50, "y": 52, "groesse": 85,
"durchsichtig": true (Körper halb durchsichtig, um Organe im Inneren zu zeigen), "blick": "links"|"rechts"}. Aktionen: picke, flattere,
bewege, wachse, erscheine, verschwinde. Teile IN der Figur setzt du über Ankerpunkte: "x": "huhn.eierstock", "y": "huhn.eierstock",
Schlauch-Punkte ebenso (z. B. ["huhn.eierstock", "huhn.eileiter", "huhn.kloake"]). Verfügbare Figuren und Anker: {figuren}
Elemente (höchstens 18, Reihenfolge = Zeichenreihenfolge, später = weiter vorn), jedes mit „id“, „art“ und:
- form: „form“ kreis|ei|tropfen|herz|quadrat|sechseck ODER eigener „pfad“ (SVG-Pfad für einen einfachen Umriss, z. B. Tier, Organ,
  Blatt, Haus), „farbe“, „x“, „y“, „groesse“, optional „streckung“ (Höhe/Breite), „deckkraft“ 0–1 (durchscheinend), „sichtbar“: false
- schlauch: „punkte“ [[x,y],…] (Röhre, Weg, Ader, Leitung, Faden), „breite“, „farbe“; „fuellung“: 0 = wird erst gezeichnet;
  „durchsichtig“: true = was DAVOR in der Liste steht, ist im Schlauch zu sehen (so wandert etwas sichtbar durch eine Röhre)
- huelle: „um“: id einer Form – durchsichtige Schicht darum, „groesse“ = Dicke, wächst mit „fuelle“
- schale: „um“: id – feste Schicht, wächst mit „fuelle“ von unten nach oben
- kristalle: „um“: id – Körnchen setzen sich mit „fuelle“ auf die Oberfläche
- partikel: „von“/„nach“ (id oder [x,y]) – Strom kleiner Teilchen, Stärke über „fuelle“
- traube: Haufen aus „anzahl“ Kugeln; pfeil: „punkte“ [[x,y],[x,y]]; uhr: Zeit vergeht mit „fuelle“ (1 = ganze Runde)
- beschriftung: „text“ (ein Wort/Begriff, der WÖRTLICH im Text der Station steht), „an“: id, „bei“: Wort, optional „seite“ links|rechts|oben|unten
Farben: dotter, eiklar, schale, kalk, rot, blau, gruen, gelb, orange, weiss, grau, braun, rosa, lila, tuerkis, gold, haut, schwarz oder #rrggbb.
Schritte (höchstens 28): {"bei": "Wort", "dauer": Sekunden, "ziel": id, "aktion": …} (statt „bei“ auch "ab": Satznummer, "nach": Sekunden)
Aktionen: erscheine · verschwinde · bewege („entlang“: Schlauch-id mit „von“/„bis“ 0–1 ODER „zu“: id ODER „punkt“: [x,y]) ·
wachse („auf“: groesse) · faerbe („farbe“) · fuelle („auf“: 0–1) · drehe („um“: Grad) · pulsiere ·
zoom (ziel „kamera“, „auf“: 1–3, „zu“: id oder „punkt“: [x,y]; "auf": 1 fährt wieder zurück).
Regeln: Lass Platz am Rand (10–90). Keine Schrift außer den Beschriftungen. Nichts zeigen, was der Text nicht sagt.
Beispiel (Text: „Der Dotter wandert durch den Eileiter. Dort legt sich das Eiklar um ihn.“):
{"elemente": [{"id": "dotter", "art": "form", "form": "kreis", "farbe": "dotter", "x": 20, "y": 15, "groesse": 13},
              {"id": "eiklar", "art": "huelle", "um": "dotter", "groesse": 30, "farbe": "eiklar"},
              {"id": "rohr", "art": "schlauch", "punkte": [[20,15],[70,30],[30,55],[70,80]], "breite": 18, "farbe": "gold", "durchsichtig": true},
              {"id": "b1", "art": "beschriftung", "text": "Dotter", "an": "dotter", "bei": "Dotter"},
              {"id": "b2", "art": "beschriftung", "text": "Eileiter", "an": "rohr", "bei": "Eileiter"},
              {"id": "b3", "art": "beschriftung", "text": "Eiklar", "an": "dotter", "bei": "Eiklar", "seite": "unten"}],
 "schritte": [{"bei": "wandert", "dauer": 3, "ziel": "dotter", "aktion": "bewege", "entlang": "rohr", "von": 0, "bis": 0.6},
              {"bei": "Dort", "dauer": 1.2, "ziel": "kamera", "aktion": "zoom", "auf": 1.8, "zu": "dotter"},
              {"bei": "legt", "dauer": 2.5, "ziel": "eiklar", "aktion": "fuelle", "auf": 1}]}"""

FALLBACK = {"de": {"hook": "Wie funktioniert das eigentlich: {t}?", "schluss": "Jetzt weißt du, wie das funktioniert: {t}.",
                   "quelle": "Quelle", "bilder": "Bilder: Illustrationen (KI-generiert bzw. gezeichnet), keine echten Aufnahmen.",
                   "stand": "Stand"},
            "en": {"hook": "How does this actually work: {t}?", "schluss": "Now you know how it works: {t}.",
                   "quelle": "Source", "bilder": "Images: illustrations (AI-generated or drawn), not real footage.", "stand": "As of"}}
AUTO = (("isometrisch", r"stadt|verkehr|fabrik|logistik|netz|internet|strom|city|factory|network"),
        ("doku", r"geschichte|krieg|antik|mittelalter|history|ancient|geheim|mystery"),
        ("motiongraphics", r"geld|wirtschaft|zins|inflation|steuer|statistik|money|economy|tax"),
        ("wissenschaft3d", r"atom|zelle|dna|virus|physik|chemie|motor|cell|physics|engine|quanten"))


class SchaubildError(RuntimeError):
    """Auftrag nicht erfüllbar (zu wenig Belegtes, kein Sprachmodell) – ehrliche Meldung, nicht wiederholen."""
    wiederholbar = False


@functools.lru_cache(maxsize=1)
def stile() -> dict[str, dict]:
    return {s["id"]: s for s in json.loads(KATALOG.read_text("utf-8"))["stile"]}


def waehle_stil(wunsch: str, thema: str) -> dict:
    alle = stile()
    if wunsch in alle:
        return alle[wunsch]
    if wunsch in ("", "animation"):
        return alle["animation"]
    if wunsch == "auto":
        for sid, pattern in AUTO:
            if re.search(pattern, thema, re.I):
                return alle[sid]
    return alle["schaubild"]


def _norm(text: str) -> str:
    text = str(text).replace(" ", " ").replace("’", "'").replace("“", '"').replace("”", '"').replace("„", '"')
    return re.sub(r"\s+", " ", text.replace("–", "-").replace("—", "-")).strip().lower()


def quellen_sammeln(thema: str, lang: str) -> list[dict]:
    """Bis zu zwei Wikipedia-Artikel zum Thema (Volltextsuche), als Klartext."""
    from ..facts import article_text

    data = net.get_json(f"https://{lang}.wikipedia.org/w/api.php",
                        params={"action": "query", "list": "search", "srsearch": thema, "srlimit": 3, "format": "json"},
                        cache_hours=24, retries=3, max_wait=30)
    out = []
    for hit in (data.get("query", {}).get("search") or [])[:3]:
        text, title = article_text(lang, hit["title"], TEXT_LIMIT)
        if len(text) > 600:
            out.append({"id": f"q{len(out) + 1}", "name": f"Wikipedia: {title}", "text": text,
                        "url": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"})
        if len(out) == 2:
            break
    return out


def pruefe_station(st: dict, quellen: list[dict], lang: str) -> tuple[dict | None, str]:
    """Eine Station gegen die Quelle prüfen. Rückgabe (bereinigte Station | None, Grund)."""
    if not isinstance(st, dict):
        return None, "kein Objekt"
    text, beleg = str(st.get("text") or "").strip(), str(st.get("beleg") or "").strip()
    name = re.sub(r"\s+", " ", str(st.get("name") or "")).strip()[:28]
    if len(text.split()) < 6 or len(text.split()) > MAX_WORDS:
        return None, "Text zu kurz oder zu lang"
    if len(beleg) < 20:
        return None, "kein Beleg"
    quelle = next((q for q in quellen if _norm(beleg) in _norm(q["text"])), None)
    if quelle is None:
        return None, "Beleg steht nicht wörtlich in der Quelle"
    extra = textcheck.numbers(text, lang) - textcheck.numbers(beleg, lang)
    if extra:
        return None, f"Zahl ohne Beleg: {', '.join(sorted(extra))}"
    people = textcheck.invented_people(text, " ".join(q["text"] for q in quellen))
    if people:
        return None, f"Name ohne Beleg: {', '.join(people)}"
    zahl = re.sub(r"\s+", " ", str(st.get("zahl") or "")).strip()[:12]
    if zahl and not (textcheck.digits(zahl) and textcheck.digits(zahl) <= textcheck.digits(beleg)):
        zahl = ""                                             # Zahl steht nicht im Beleg -> ohne Riesenzahl
    einheit = re.sub(r"\s+", " ", str(st.get("einheit") or "")).strip()[:18] if zahl else ""
    if einheit and _norm(einheit) not in _norm(beleg) and _norm(einheit) not in _norm(text):
        einheit = ""
    low = _norm(text + " " + name)
    etiketten = []
    for e in st.get("etiketten") or []:
        e = re.sub(r"\s+", " ", str(e)).strip()
        if 2 <= len(e) <= 22 and len(e.split()) <= 2 and _norm(e) in low and e not in etiketten:
            etiketten.append(e)
    bild = re.sub(r"[^\x20-\x7e]", "", str(st.get("bild") or ""))[:220].strip()
    folge = [re.sub(r"[^\x20-\x7e]", "", str(b))[:260].strip() for b in (st.get("bilder") or []) if str(b).strip()][:MAX_BILDER]
    folge = [b for b in folge if len(b) >= 8] or [bild or name]
    return {"name": name or text.split()[0], "text": text, "zahl": zahl, "einheit": einheit, "beleg": beleg,
            "quelle": quelle["name"], "quelle_url": quelle["url"], "etiketten": etiketten[:3], "bild": folge[0], "bilder": folge,
            "szene": zeichnen.beschriftungen_pruefen(zeichnen.pruefe_szene(st.get("szene")), text + " " + name),
            "drehbuch": [{"wort": str(d.get("wort"))[:30], "zeigt": re.sub(r"\s+", " ", str(d.get("zeigt") or ""))[:140]}
                         for d in (st.get("drehbuch") or [])[:24] if isinstance(d, dict) and _wort(str(d.get("wort") or "")) in _woerter(text)],
            "ohne_bild": [str(w)[:30] for w in (st.get("ohne_bild") or [])[:8] if _wort(str(w)) in _woerter(text)]}, ""


SATZANFANG = {"wie", "was", "warum", "wieso", "weshalb", "wer", "wo", "wann", "welche", "welcher", "welches", "woher", "wohin", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "hier", "dort", "danach", "dann", "im", "in",
              "am", "an", "auf", "wenn", "und", "oder", "aber", "es", "sie", "er", "so", "zuerst", "zuletzt", "erst", "nun", "jetzt", "dabei",
              "damit", "dazu", "alles", "alle", "jede", "jeder", "jedes", "diese", "dieser", "dieses", "nach", "vor", "mit", "bei", "aus", "von",
              "zum", "zur", "für", "ohne", "weil", "während", "sobald", "dadurch", "daher", "deshalb", "außerdem", "schließlich", "anschließend"}


def _wort(w: str) -> str:
    return re.sub(r"[^\wäöüß–-]", "", w.lower().split()[0]) if w.strip() else ""


def _woerter(text: str) -> set[str]:
    return {_wort(t) for t in text.split()} - {""}


def _passt(a: str, b: str) -> bool:
    """Gleiches Wort oder gleiche Wortfamilie (Eiklar/Eiklars, Schale/Schalen)."""
    return bool(a and b) and (a == b or len(min(a, b, key=len)) > 3 and (a.startswith(b[:max(4, len(b) - 2)]) or b.startswith(a[:max(4, len(a) - 2)])))


def hauptwoerter(text: str) -> list[str]:
    """Hauptwörter eines deutschen Textes (großgeschrieben; am Satzanfang nur, wenn es kein übliches Anfangswort ist)."""
    out, anfang = [], True
    for tok in text.split():
        roh = tok.strip("„“\"(),;:!?.–-")
        if roh[:1].isupper() and len(roh) >= 3 and not (anfang and roh.lower() in SATZANFANG) and _wort(roh) not in out:
            out.append(_wort(roh))
        anfang = tok[-1:] in ".!?:"
    return out


def abgleich(st: dict, lang: str) -> list[str]:
    """1:1-Prüfung Bild ↔ Text einer Station: Was wird gesagt, aber nicht gezeigt? Leere Liste = alles zu sehen."""
    sz = st.get("szene")
    if not sz:
        return ["keine gültige Szene"]
    gezeigt = [_wort(x.get("bei") or "") for x in sz["schritte"]] + \
              [_wort(e.get("bei") or e["text"]) for e in sz["elemente"] if e["art"] == "beschriftung"]
    schilder = {_wort(w) for e in sz["elemente"] if e["art"] == "beschriftung" for w in e["text"].split()}
    gezeigt = [g for g in gezeigt if g]
    maengel, nr, satz = [], 1, []
    for tok in st["text"].split() + [None]:                    # jeder Satz braucht mindestens einen Schritt/eine Beschriftung
        if tok is not None:
            satz.append(_wort(tok))
        if tok is None or tok[-1:] in ".!?":
            if satz and not (any(_passt(g, w) for g in gezeigt for w in satz)
                             or any(x.get("ab") == nr and not x.get("bei") for x in sz["schritte"])):
                maengel.append(f"Satz {nr} hat keinen eigenen Schritt")
            nr, satz = nr + 1, []
    for d in st.get("drehbuch") or []:
        if not any(_passt(g, _wort(d["wort"])) for g in gezeigt):
            maengel.append(f"Drehbuch-Wort „{d['wort']}“ kommt in der Szene nicht vor")
    if lang == "de":
        frei = [_wort(w) for w in st.get("ohne_bild") or []]
        zahlwoerter = {_wort(st.get("einheit") or "")}
        for w in hauptwoerter(st["text"]):
            if not (any(_passt(g, w) for g in gezeigt) or any(_passt(s2, w) for s2 in schilder) or any(_passt(f, w) for f in frei)
                    or w in zahlwoerter):
                maengel.append(f"„{w}“ wird gesagt, aber nicht gezeigt")
    return maengel


KORREKTUR = """Die Szenen dieser Stationen zeigen noch nicht alles, was der Text sagt. Unter „daten.stationen“ stehen je Station der Text,
die bisherige Szene und die „maengel“. Gib für JEDE dieser Stationen eine vollständige, verbesserte „szene“ zurück (gleiches Format wie
bisher, alle bisherigen guten Teile behalten) – so, dass jeder Mangel behoben ist: fehlende Dinge als Element mit „beschriftung“
(Text = das Wort aus dem Text), fehlende Vorgänge als Schritt mit "bei": Wort. Was sich wirklich nicht zeigen lässt, nenne in „ohne_bild“.
Antwort: {"stationen": [{"name": "…", "szene": {...}, "ohne_bild": ["…"]}]}"""


def nachbessern(stationen: list[dict], lang: str, notes: list[str], aufgabe: str = "schaubild_korrektur") -> None:
    """Stationen mit Lücken einmal zur Korrektur geben; eine neue Szene gilt nur, wenn sie weniger Lücken hat."""
    offen = [(st, abgleich(st, lang)) for st in stationen]
    offen = [(st, m) for st, m in offen if m]
    if not offen:
        return
    figuren_text = "; ".join(f"{n} (Anker: {', '.join(i['anker'])})" for n, i in zeichnen.figuren().items()) or "keine"
    answer = handoff.request(aufgabe, KORREKTUR + SZENEN_ANLEITUNG.replace("{figuren}", figuren_text), {"sprache": lang, "stationen": [
        {"name": st["name"], "text": st["text"], "szene": st.get("szene"), "maengel": m} for st, m in offen]})
    neu = {str(x.get("name")): x for x in (answer or {}).get("stationen", []) if isinstance(x, dict)} if isinstance(answer, dict) else {}
    for st, m in offen:
        x = neu.get(st["name"])
        if not x:
            continue
        versuch = {**st, "szene": zeichnen.beschriftungen_pruefen(zeichnen.pruefe_szene(x.get("szene")), st["text"] + " " + st["name"]),
                   "ohne_bild": [str(w)[:30] for w in (x.get("ohne_bild") or st.get("ohne_bild") or [])[:8] if _wort(str(w)) in _woerter(st["text"])]}
        if versuch["szene"] and len(abgleich(versuch, lang)) < len(m):
            st.update(szene=versuch["szene"], ohne_bild=versuch["ohne_bild"])
    rest = [(st["name"], abgleich(st, lang)) for st in stationen]
    rest = [f"{name}: {'; '.join(m[:4])}" for name, m in rest if m]
    if rest:
        notes.append("Bild und Text passen noch nicht überall 1:1 – " + " | ".join(rest))


def pruefe_satz(text: str, erlaubt: set[str], quellen_text: str, lang: str) -> bool:
    """Hook/Versprechen/Schluss: keine Zahl außerhalb der Belege, kein Name außerhalb der Quellen."""
    text = str(text or "").strip()
    return bool(text) and len(text.split()) <= 34 and not (textcheck.numbers(text, lang) - erlaubt) \
        and not textcheck.invented_people(text, quellen_text)


def wahrheit(stationen: list[dict], lang: str) -> tuple[list[dict], list[tuple[str, str]]]:
    """Derselbe Wahrheits-Prüfer wie bei Fakten-Videos (über die Satire-Brücke): Satz gegen seinen Beleg."""
    from ..satire import wahrheit_fakten

    saetze = [{"text": s["text"], "belege": [{"zitat": s["beleg"], "name": s["quelle"]}]} for s in stationen]
    ok, rejected = wahrheit_fakten(saetze, lang)
    keep = {s["text"] for s in ok}
    return [s for s in stationen if s["text"] in keep], rejected


def baue_skript(ident: str, titel: str, hook: str, versprechen: str, stationen: list[dict], schluss: str, lang: str,
                stil: dict, seitenformat: str) -> dict:
    szenen = [{"typ": "intro", "text": " ".join(x for x in (hook, versprechen) if x), "kopf": titel, "name": titel.split()[0]}]
    for i, st in enumerate(stationen, start=1):
        szenen.append({"typ": "station", "station": i, **st})
    szenen.append({"typ": "outro", "text": schluss, "kopf": titel, "name": titel.split()[0]})
    return {"id": ident, "titel": titel, "sprache": lang, "stil": stil, "seitenformat": seitenformat, "szenen": szenen}


def bild_brauchbar(path: str) -> bool:
    """KI-Bilder sind manchmal nur ein unscharfer Farbverlauf – solche Bilder zeigen nichts und fliegen raus."""
    from PIL import Image, ImageFilter, ImageStat

    try:
        with Image.open(path) as im:
            kanten = im.convert("L").resize((256, 256)).filter(ImageFilter.FIND_EDGES)
            return ImageStat.Stat(kanten.crop((8, 8, 248, 248))).mean[0] >= MIN_KANTEN
    except OSError:
        return False


def ki_bild(prompt: str, seed: int):
    """KI-Illustration (1024×1024). Mit Konto (`CUDI_POLLINATIONS_TOKEN`) über die kostenlosen, deutlich besseren Modelle
    (`MODELLE`, nacheinander versucht), sonst der alte Weg ohne Konto (klein, weich)."""
    from urllib.parse import quote, urlencode

    from .. import config
    from ..story import visuals

    if config.POLLINATIONS_TOKEN and not _guthaben_leer[0]:
        headers = {"Authorization": f"Bearer {config.POLLINATIONS_TOKEN}"}
        for modell in MODELLE:
            url = (f"https://gen.pollinations.ai/image/{quote(prompt[:900])}?"
                   + urlencode({"model": modell, "width": 1024, "height": 1024, "seed": seed, "nologo": "true"}))
            try:
                path = net.cached_file(url, ".jpg") or net.download(url, suffix=".jpg", retries=2, max_wait=20, timeout=150,
                                                                    headers=headers, retry_on=(429, 500, 502, 503, 504))
                if bild_brauchbar(str(path)):
                    return visuals.Visual("image", str(path), f"KI-Illustration ({modell.split('/')[-1]})", prompt), False
            except Exception as exc:                          # nächstes Modell bzw. alter Weg
                if "402" in str(exc):                         # Guthaben leer: nicht weiter anfragen
                    _guthaben_leer[0] = True
                    break
                log.warning("Bildmodell %s nicht verfügbar: %s", modell, str(exc)[:120])
    vis = visuals.ai_image(prompt, seed=seed)
    if vis is not None and not bild_brauchbar(vis.path):
        vis = visuals.ai_image(prompt, seed=seed + 1000)
        vis = vis if vis is not None and bild_brauchbar(vis.path) else None
    return vis, True                                          # True = Bild trägt unten das Logo des Dienstes (wird abgeschnitten)


def bilder(skript: dict, work: Path, notes: list[str]) -> None:
    """Je Satz einer Station ein Bild (Bildfolge): KI-Illustration → freies Foto → vom Renderer gezeichnete Grafik."""
    stil = skript["stil"]
    if stil["modus"] == "code":
        return
    from ..story import visuals

    stationen = [s for s in skript["szenen"] if s["typ"] == "station"]
    used: set = set()
    fehlt, nr = 0, 0

    def hole(prompt: str) -> dict | None:
        nonlocal nr
        nr += 1
        voll = f"{prompt}, {stil['prompt']}"
        vis, logo = ki_bild(voll, 1000 + nr)
        if vis is not None:
            return {"datei": vis.path, "ki": True, "logo": logo, "quelle": vis.credit, "prompt": voll}
        try:
            foto = visuals.commons_photo(prompt, used)
        except Exception:                                     # Bild ist optional
            foto = None
        return {"datei": foto.path, "ki": False, "logo": False, "quelle": f"Foto: {foto.credit}", "prompt": ""} if foto else None

    from concurrent.futures import ThreadPoolExecutor
    from .. import config

    alle = [(sz, p) for sz in stationen for p in (sz.get("bilder") or [sz["bild"]])]
    gleichzeitig = 4 if config.POLLINATIONS_TOKEN else 1      # ohne Konto drosselt der Dienst: nur nacheinander
    with ThreadPoolExecutor(max_workers=gleichzeitig) as pool:
        geholt = list(pool.map(lambda sp: hole(sp[1]), alle))
    for sz in stationen:
        folge = [b for (s2, _), b in zip(alle, geholt) if s2 is sz and b]
        if folge:
            sz.update(bildfolge=folge, bild_datei=folge[0]["datei"], ki=folge[0]["ki"], bild_quelle=folge[0]["quelle"],
                      bild_prompt=" | ".join(b["prompt"] for b in folge))
        else:
            fehlt += 1
    if _guthaben_leer[0]:
        notes.append("Bild-Guthaben bei Pollinations ist aufgebraucht – die übrigen Bilder kommen vom kostenlosen, schwächeren Modell.")
    if fehlt:
        notes.append(f"{fehlt} Station(en) ohne Bild – dort zeichnet der Renderer eine schlichte Grafik.")
    for sz, key, ersatz in ((skript["szenen"][0], "bild_hook", stationen[:1]), (skript["szenen"][-1], "bild_schluss", stationen[-1:])):
        eigenes = hole(sz[key]) if sz.get(key) else None
        folge = [eigenes] if eigenes else (ersatz[0].get("bildfolge") or [])[-1:] if ersatz else []
        if folge:
            sz.update(bildfolge=folge, bild_datei=folge[0]["datei"], ki=folge[0]["ki"], bild_quelle=folge[0]["quelle"],
                      bild_prompt=folge[0]["prompt"])


def texte(skript: dict, quellen: list[dict], lang: str) -> tuple[str, str]:
    s = FALLBACK[lang]
    namen = [sz["name"] for sz in skript["szenen"] if sz["typ"] == "station"]
    used = sorted({(sz["quelle"], sz["quelle_url"]) for sz in skript["szenen"] if sz.get("quelle_url")})
    stand = datetime.now(timezone.utc).date().isoformat()
    yt = "\n".join([skript["titel"], "", skript["szenen"][0]["text"], "", " → ".join(namen), "",
                    *(f"{s['quelle']}: {n} – {u}" for n, u in used), f"{s['stand']}: {stand}", s["bilder"], "", "#shorts #wissen #erklaert"])
    tt = f"{skript['titel']} – {' → '.join(namen)}\n{s['bilder']}\n#fyp #wissen #erklaert"
    return yt, tt


def pruefbericht(skript: dict, quellen: list[dict], rejected: list[tuple[str, str]], notes: list[str]) -> str:
    stil = skript["stil"]
    lines = [f"# Prüfbericht Schaubild: {skript['titel']}", "",
             f"- Bildstil: {stil['name']} ({stil['id']}, {'KI-Illustration' if stil['modus'] == 'bild' else 'vom Programm gezeichnet'}), "
             f"Seitenformat {skript['seitenformat']}",
             ("- Eigene Animation: schematische Erklär-Zeichnung, vom Programm gezeichnet und bewegt – keine Abbildung der Wirklichkeit."
              if stil["modus"] == "szene" else
              "- Bewegung: Zoom/Schwenk/Parallaxe/Ruckeln – keine animierten Figuren. Alle Bilder sind als Illustration gekennzeichnet."),
             "", "## Stationen (Sprechtext → wörtlicher Beleg)"]
    for sz in skript["szenen"]:
        if sz["typ"] != "station":
            continue
        lines += [f"{sz['station']}. **{sz['name']}** – {sz['text']}", f"   - Beleg ({sz['quelle']}): „{sz['beleg']}“",
                  f"   - Bild: {sz.get('bild_quelle') or 'vom Renderer gezeichnet'}"
                  + (f" · Zahl im Bild: {sz['zahl']} {sz['einheit']}".rstrip() if sz.get("zahl") else "")]
    if stil["modus"] == "szene":
        lines += ["", "## Abgleich Bild ↔ Text (was gesagt wird → was zu sehen ist)"]
        for sz in skript["szenen"]:
            if sz["typ"] != "station":
                continue
            m = abgleich(sz, skript["sprache"])
            lines.append(f"**{sz['station']}. {sz['name']}** – " + ("alles Gesagte ist zu sehen" if not m else "Lücken: " + "; ".join(m)))
            lines += [f"   - „{d['wort']}“ → {d['zeigt']}" for d in sz.get("drehbuch") or []]
            if sz.get("ohne_bild"):
                lines.append("   - bewusst ohne Bild: " + ", ".join(sz["ohne_bild"]))
    lines += ["", "## Quellen", *(f"- {q['name']} – {q['url']}" for q in quellen)]
    if rejected:
        lines += ["", "## Abgelehnt (nicht im Video)", *(f"- {t} – {why}" for t, why in rejected)]
    if notes:
        lines += ["", "## Hinweise", *(f"- {n}" for n in notes)]
    return "\n".join(lines) + "\n"


def run(order: dict, folder: Path, progress=lambda stage, f: None) -> dict:
    """Schaubild-Auftrag -> Ergebnis im Format von job._summary."""
    from .render import render_schaubild

    lang, thema = order["sprache"], order["thema"]
    out = folder / "schaubild"
    out.mkdir(parents=True, exist_ok=True)
    if not handoff.active():
        raise SchaubildError("Schaubild braucht ein Sprachmodell zum Formulieren (Claude oder CUDI_LLM_*) – gerade keines erreichbar. "
                             "Erfunden wird nichts; bitte später erneut versuchen.")
    cache = folder / "schaubild_quellen.json"                 # ein Weiterlauf prüft gegen dieselben Texte
    if cache.exists():
        quellen = json.loads(cache.read_text("utf-8"))
    else:
        progress("Quellen sammeln", 0.05)
        quellen = quellen_sammeln(thema, lang)
        cache.write_text(json.dumps(quellen, ensure_ascii=False), "utf-8")
    if not quellen:
        raise SchaubildError(f"Schaubild nicht möglich: Zu „{thema}“ fand sich kein Artikel als Quelle. Bitte das Thema genauer nennen.")
    stil = waehle_stil(order.get("stil") or "animation", thema)
    eigen = stil["modus"] == "szene"
    progress("Skript schreiben", 0.15)
    anleitung = INSTRUCTIONS.replace("{n}", str(order["stationen"])).replace("{lang}", "Deutsch" if lang == "de" else "English")
    figuren_text = "; ".join(f"{n} (Anker: {', '.join(i['anker'])})" for n, i in zeichnen.figuren().items()) or "keine"
    answer = handoff.request(TASK, anleitung + (SZENEN_ANLEITUNG.replace("{figuren}", figuren_text) if eigen else ""),
                             {"thema": thema, "sprache": lang, "stationen": order["stationen"],
                              "quellen": [{"id": q["id"], "name": q["name"], "text": q["text"]} for q in quellen]})
    if not isinstance(answer, dict):
        raise SchaubildError("Schaubild nicht möglich: Das Sprachmodell hat kein Skript geliefert. Es wird nichts erfunden – bitte später erneut versuchen.")
    rejected: list[tuple[str, str]] = []
    stationen = []
    for st in (answer.get("stationen") or [])[:9]:
        ok, why = pruefe_station(st, quellen, lang)
        if ok:
            stationen.append(ok)
        else:
            rejected.append((str((st or {}).get("text") if isinstance(st, dict) else st)[:120], why))
    stationen, rej = wahrheit(stationen, lang)
    rejected += rej
    if len(stationen) < MIN_STATIONEN:
        raise SchaubildError(f"Schaubild nicht möglich: Nur {len(stationen)} Station(en) ließen sich wörtlich belegen "
                             f"(nötig: {MIN_STATIONEN}). Es wird nichts ergänzt.")
    erlaubt = set().union(*(textcheck.numbers(s["beleg"], lang) for s in stationen))
    qtext = " ".join(q["text"] for q in quellen)
    notes: list[str] = []
    titel = re.sub(r"\s+", " ", str(answer.get("titel") or "")).strip()
    if not (4 <= len(titel) <= 60 and pruefe_satz(titel, erlaubt, qtext, lang)):
        titel = thema[:60]
    fb = FALLBACK[lang]
    hook = str(answer.get("hook") or "").strip()
    if not pruefe_satz(hook, erlaubt, qtext, lang):
        hook = fb["hook"].format(t=titel)
        notes.append("Einstieg aus der Regel-Fassung (der Vorschlag enthielt Unbelegtes).")
    versprechen = str(answer.get("versprechen") or "").strip()
    if not pruefe_satz(versprechen, erlaubt, qtext, lang):
        versprechen = ""
    schluss = str(answer.get("schluss") or "").strip()
    if not pruefe_satz(schluss, erlaubt, qtext, lang):
        schluss = fb["schluss"].format(t=titel)
    skript = baue_skript("schaubild", titel, hook, versprechen, stationen, schluss, lang, stil, order.get("seitenformat") or "9:16")
    for sz, key in ((skript["szenen"][0], "bild_hook"), (skript["szenen"][-1], "bild_schluss")):
        sz[key] = re.sub(r"[^\x20-\x7e]", "", str(answer.get(key) or ""))[:260].strip()
    if eigen:                                                 # eigene Animation: nichts aus dem Netz, das Programm zeichnet selbst
        for sz, key in ((skript["szenen"][0], "szene_hook"), (skript["szenen"][-1], "szene_schluss")):
            sz["szene"] = zeichnen.beschriftungen_pruefen(zeichnen.pruefe_szene(answer.get(key)), sz["text"])
        nachbessern([sz for sz in skript["szenen"] if sz["typ"] == "station"], lang, notes)
        ohne = sum(1 for sz in skript["szenen"] if sz["typ"] == "station" and not sz.get("szene"))
        if ohne:
            notes.append(f"{ohne} Station(en) ohne gültige Szenen-Beschreibung – dort zeigt das Video eine schlichte Grafik.")
        for sz in skript["szenen"]:
            sz["bild_quelle"] = "eigene Animation (vom Programm gezeichnet)" if sz.get("szene") else "schlichte Grafik"
    else:
        progress("Bilder", 0.3)
        bilder(skript, out / "work", notes)
    yt, tt = texte(skript, quellen, lang)
    (out / "youtube.txt").write_text(yt, "utf-8")
    (out / "tiktok.txt").write_text(tt, "utf-8")
    (out / "spec.json").write_text(json.dumps({"title": {"de": titel, "en": titel}}, ensure_ascii=False), "utf-8")
    (out / "review.md").write_text(pruefbericht(skript, quellen, rejected, notes), "utf-8")
    progress("Video rendern", 0.4)
    result = render_schaubild(skript, out, progress=lambda f: progress("Video rendern", 0.4 + 0.55 * f))
    files = {"video": result["video"], "cover": result["cover"], "duration": result["duration"], "qa": result.get("qa"),
             "description_file": "youtube.txt", "caption_file": "tiktok.txt", "abnahme": {"ok": True, "gruende": []}}
    return {"output_dir": str(out), "videos": {lang: files}, "kind": "schaubild", "warnings": notes}
