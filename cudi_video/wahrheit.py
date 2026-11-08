"""Wahrheits-Prüfer und Endabnahme: Nie lügen – auch nicht durch Formulierungen, die die Wahrheit anders verstehen lassen.

Geprüft wird jede Aussage eines Ranking-/Faktenvideos (Sprechtext, Hook, Untertitel, Titel, Cover-Text, Beschreibung,
TikTok-Text; Deutsch und Englisch) gegen die geprüften Daten (Recherche, Belege, Quellen-Abgleich). Ein Regelkatalog
(`REGELN`) erkennt irreführende Muster; jeder Befund nennt Regel, Textstelle und Begründung. Befunde werden automatisch
korrigiert (Zeitbezug ergänzen, Satz durch die geprüfte Textbaustein-Fassung ersetzen, sonst Satz streichen) und danach
erneut geprüft. Was sich nicht korrigieren lässt, verhindert die Auslieferung (Endabnahme in `pipeline.render_checked`).

Optional liest Claude (bzw. im Notbetrieb das freie Sprachmodell) über `handoff` gegen (Aufgabe `wahrheit_pruefung`);
übernommen werden nur Befunde, die auf einen wörtlich vorhandenen Textteil zeigen und eine Begründung haben.
Bestehende Prüfungen werden wiederverwendet (`textcheck.numbers`, `script._is_year`, `metadata.CLICKBAIT`,
`narrate.RANK_CLAIM`), nicht dupliziert.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date

from . import handoff, textcheck
from .metadata import CLICKBAIT, DISCLOSURE, FACT_DISCLOSURE
from .models import Research, Script
from .script import TEXT, TIME_VARYING, _is_day, _is_year, _sentences, as_of_year
from .spec import VideoSpec
from .units import quantity
from .verify import STATUS_OK, SOURCE_NAMES, external_sources

log = logging.getLogger(__name__)

MAX_ROUNDS = 3
STALE_YEARS = 2                 # Stand ab so vielen Jahren gilt für veränderliche Werte als alt
ROUND_TOLERANCE = 0.05          # Rundung: höchstens 5 % Abweichung
NEAR_WINDOW = 0.15              # Zahlen bis 15 % neben einem geprüften Wert gelten als Angabe dieses Werts

# Regelkatalog: Kennung -> (Kurzname, Begründung)
REGELN: dict[str, tuple[str, str]] = {
    "superlativ": ("Superlativ ohne Beleg", "„größte“, „einzige“, „erste“ … sind Tatsachenbehauptungen; ohne Beleg in den "
                   "geprüften Daten könnten sie falsch sein."),
    "bis_zu": ("„bis zu“ / „über“ / „fast“ falsch zur Zahl", "Das Wort muss zur geprüften Zahl passen: „über X“ gilt nur "
               "unterhalb des Werts, „fast X“ nur knapp darüber, „bis zu X“ nur als Obergrenze."),
    "rundung": ("Rundung zu grob", "Gerundete Zahlen dürfen höchstens 5 % vom geprüften Wert abweichen."),
    "zeitbezug": ("Zeitbezug fehlt", "Veränderliche Werte (Einwohner, Rekorde, „derzeit“) brauchen den Stand, sonst "
                  "wirkt ein alter Wert wie ein aktueller."),
    "ursache": ("Ursache statt Zusammenhang", "„weil“, „verursacht“ behaupten eine Ursache; belegt ist ohne Quelle höchstens "
               "ein Zusammenhang."),
    "verallgemeinerung": ("Verallgemeinerung", "„alle“, „immer“, „nie“ lassen keine Ausnahme zu; die Quelle belegt das nicht."),
    "clickbait": ("Clickbait", "Titel, Cover und Beschreibung dürfen nichts versprechen, was das Video nicht hält."),
    "anzahl": ("Falsche Anzahl", "Die Anzahl im Titel/Hook muss zur Zahl der gezeigten Plätze bzw. Fakten passen."),
    "zitat": ("Zitat/Aussage ohne Quelle", "Zitate und Personenaussagen müssen wörtlich in der Quelle stehen."),
    "bezugsgroesse": ("Falsche Bezugsgröße", "Vergleiche („5-mal so hoch wie …“) brauchen ein belegtes Vergleichsobjekt und "
                      "den richtigen Faktor."),
    "quellenlage": ("Quellenlage überzeichnet", "Was nur Wikipedia/Wikidata stützt, darf nicht als „bewiesen“, „offiziell“ "
                    "oder „mit mehreren unabhängigen Quellen abgeglichen“ erscheinen."),
    "zahl_ohne_beleg": ("Zahl ohne Beleg", "Jede Zahl muss im Beleg des Fakts stehen."),
    "gegenlesen": ("Gegenlesen", "Befund beim Gegenlesen (Claude bzw. Notbetrieb-Modell) mit Verweis auf eine Textstelle."),
}

SPRECH, HOOK, UNTERTITEL, TITEL, COVER, BESCHREIBUNG, CAPTION = (
    "Sprechtext", "Hook", "Untertitel", "Titel", "Cover", "Beschreibung", "TikTok-Text")
SCRIPT_ARTS = {SPRECH, HOOK, UNTERTITEL}


@dataclass
class Aussage:
    lang: str
    art: str
    text: str
    rank: int | None = None
    idx: int | None = None          # Segmentindex (Sprechtext/Hook/Untertitel)
    herkunft: str = ""              # "spec_titel" = Text stammt aus spec.title und wird dort korrigiert

    @property
    def ort(self) -> str:
        return f"{self.art}" + (f" Platz {self.rank}" if self.rank is not None else "")


@dataclass
class Befund:
    regel: str
    lang: str
    art: str
    satz: str
    grund: str
    rank: int | None = None
    idx: int | None = None
    aktion: str = "streichen"       # streichen | ersetzen | ergaenzen | keine
    ersatz: str = ""
    korrigiert: bool = False
    korrektur: str = ""
    herkunft: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Bericht:
    lang: str
    geprueft: int = 0
    offen: list[Befund] = field(default_factory=list)
    korrigiert: list[Befund] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.offen

    def to_dict(self) -> dict:
        return {"lang": self.lang, "geprueft": self.geprueft, "ok": self.ok,
                "offen": [b.to_dict() for b in self.offen], "korrigiert": [b.to_dict() for b in self.korrigiert]}


# --------------------------------------------------------------------------- Text-Helfer

_SPLIT = re.compile(r"(?<![0-9]\.)(?<!\b[A-Za-z]\.)(?<!\bSt\.)(?<!\bNr\.)(?<!\bbzw\.)(?<!\bca\.)(?<!\bCo\.)"
                    r"(?<=[.!?…])\s+(?=[A-ZÄÖÜ„\"“0-9])")


def saetze(text: str) -> list[str]:
    return [p.strip() for p in _SPLIT.split(str(text or "").strip()) if p.strip()]


def _n(text: str) -> str:
    """Zum Vergleichen: klein, ohne Anführungszeichen, Leerraum vereinheitlicht."""
    return re.sub(r"\s+", " ", re.sub(r"[„“”\"'«»]", "", str(text or "")).lower()).strip()


def _words_in(text: str, name_set: set[str]) -> bool:
    rx = re.compile(rf"\b{re.escape(text.lower().strip())}\b")
    return any(rx.search(name) for name in name_set)


# --------------------------------------------------------------------------- Wortlisten (Deutsch + Englisch)

_SUPER = [
    ("hoch", r"(?:zweit|dritt|viert|fünft|welt)?höchst(?:e[rnms]?)?\b|\bhighest\b|\btallest\b"),
    ("gross", r"(?:zweit|dritt|viert|fünft|welt)?(?:größt|grösst)(?:e[rnms]?)?\b|\blargest\b|\bbiggest\b|\bgreatest\b"),
    ("lang", r"(?:zweit|dritt|viert|fünft|welt)?längst(?:e[rnms]?)?\b|\blongest\b"),
    ("tief", r"(?:zweit|dritt|viert|fünft|welt)?tiefst(?:e[rnms]?)?\b|\bdeepest\b"),
    ("schwer", r"schwerst(?:e[rnms]?)?\b|\bheaviest\b"),
    ("schnell", r"schnellst(?:e[rnms]?)?\b|\bfastest\b"),
    ("alt", r"ältest(?:e[rnms]?)?\b|\boldest\b"),
    ("jung", r"jüngst(?:e[rnms]?)?\b|\byoungest\b"),
    ("klein", r"kleinst(?:e[rnms]?)?\b|\bsmallest\b"),
    ("stark", r"stärkst(?:e[rnms]?)?\b|\bstrongest\b"),
    ("breit", r"breitest(?:e[rnms]?)?\b|\bwidest\b"),
    ("reich", r"reichst(?:e[rnms]?)?\b|\brichest\b"),
    ("bekannt", r"bekanntest(?:e[rnms]?)?\b|beliebtest(?:e[rnms]?)?\b|\bmost (?:famous|popular|common|important)\b"),
    ("gefaehrlich", r"gefährlichst(?:e[rnms]?)?\b|\bmost (?:dangerous|powerful|beautiful)\b"),
    ("best", r"\bbeste[rnms]?\b|\bthe best\b|\bam besten\b"),
    ("einzig", r"\beinzig\w*|\bthe only\b|\bonly one\b|\bone and only\b|\bunique\b"),
    ("erst", r"\berste[rnms]?\b(?!\s+(?:Platz|Hilfe))|\bfirst\b(?!\s+(?:place|spot|up|aid))"),
    ("rekord", r"\b\w*rekord\w*|\bworld records?\b|\brecord[- ](?:breaking|holder|high|low)\b|\brecords?\b"),
]
SUPER = [(k, re.compile(rx, re.I)) for k, rx in _SUPER]

CAUSAL = re.compile(
    r"\bweil\b|\bverursach\w*|\bführ(?:t|te|en|ten)\b(?:\s+\w+){0,2}\s+zu\b|\bdeshalb\b|\bdeswegen\b|\bdaher\b|\bdadurch\b|"
    r"\binfolge\b|\baufgrund\b|\bwegen\b|\bsorg(?:t|te|en|ten)\b(?:\s+\w+){0,2}\s+für\b|\bbecause\b|\bcaus(?:e|es|ed|ing)\b|"
    r"\bleads? to\b|\bled to\b|\bdue to\b|\bresults? in\b|\bresulted in\b|\btherefore\b|\bas a result\b|\bthanks to\b|\bowing to\b",
    re.I)

GENERAL = re.compile(
    r"\balle[nrms]?\b|\balles\b|\bjede[rnms]?\b|\bjedermann\b|\bimmer\b|\bnie\b|\bniemals\b|\bniemand\b|\bnirgends\w*|"
    r"\büberall\b|\bstets\b|\bausnahmslos\b|\ball\b|\bevery(?:one|body|thing|where)?\b|\balways\b|\bnever\b|\bnobody\b|"
    r"\bnowhere\b|\bno one\b|\bwithout exception\b|\beveryone\b", re.I)
_GENERAL_OK = re.compile(            # Takt/Häufigkeit und Steigerung sind keine Allaussagen („alle drei Jahre“, „immer mehr“)
    r"(?:alle|every)\s+(?:\d+|zwei|drei|vier|fünf|sechs|sieben|acht|zehn|two|three|four|five|six|seven|ten|other|second|"
    r"minute|day|year|week|hour|month|decade|few|couple)|"
    r"jede[nrms]?\s+(?:\w+\s+)?(?:tag|nacht|sekunde|minute|stunde|woche|monat|jahr|jahrzehnt|mal)|"
    r"immer\s+(?:mehr|weniger|wieder|größer|höher|kleiner|schneller|länger|besser|schlechter|noch|häufiger|öfter)|"
    r"every\s+(?:single\s+)?(?:time|now and then)|"
    r"\bnie\s+wieder|\bnot\s+always|\bnicht\s+immer|\balles\s+(?:in\s+allem|andere)", re.I)

STRONG = re.compile(
    r"\bbewiesen\w*|\bnachgewiesen\w*|\bnachweislich\b|\bunbestritten\w*|\bgesichert\w*|\bamtlich\w*|\boffiziell\w*|"
    r"\bverifiziert\w*|\bbestätigt\w*|\bbelegt(?!\s+(?:den\s+|die\s+)?(?:\w+\s+)?(?:Platz|Rang))\b|"
    r"\bproven\b|\bproof\b|\bofficial(?:ly)?\b|\bconfirmed\b|\bverified\b|\bundisputed\b|\bestablished fact\b|"
    r"\bscientifically proven\b", re.I)

PROMISE = re.compile(
    r"geheimnis\w*|\bsecrets?\b|\benthüll\w*|\bverrät\b|\breveals\b|\brevealed\b|\bbeweis\w*|\bproof\b|\bproven\b|"
    r"\bwahrheit\b|\btruth\b|\bexklusiv\w*|\bexclusive\b|\bnie zuvor\b|\bnever before\b|\bverboten\w*|\bbanned\b|"
    r"\bexperten\b|\bexperts\b|\bwissenschaftler\b|\bscientists\b|\bstudie\w*|\bstudy\b|\bstudies\b", re.I)

TIME_WORDS = re.compile(
    r"\bderzeit\b|\baktuell\w*|\bzurzeit\b|\bmomentan\b|\bcurrently\b|\bat present\b|\bnowadays\b|\bthese days\b|"
    r"\bbis heute\b|\bto this day\b|\bright now\b|\bneuest\w*|\blatest\b", re.I)
POP_WORDS = re.compile(r"einwohner|bevölkerung|inhabitants|population|residents|bewohner", re.I)

MODS = [
    ("bis_zu", re.compile(r"(?:bis\s+zu|up\s+to|höchstens|maximal|at\s+most)\s*$", re.I)),
    ("ueber", re.compile(r"(?:über|mehr\s+als|more\s+than|over|above|exceeding|größer\s+als|upwards\s+of)\s*$", re.I)),
    ("fast", re.compile(r"(?:fast|beinahe|knapp|nearly|almost|just\s+(?:under|below|shy\s+of)|knapp\s+unter)\s*$", re.I)),
    ("unter", re.compile(r"(?:unter|weniger\s+als|less\s+than|fewer\s+than|under|below)\s*$", re.I)),
    ("mindestens", re.compile(r"(?:mindestens|wenigstens|at\s+least)\s*$", re.I)),
    ("etwa", re.compile(r"(?:rund|etwa|circa|ca\.|zirka|ungefähr|about|around|approximately|roughly|approx\.|~)\s*$", re.I)),
]
RANK_BEFORE = re.compile(r"(?:platz|nr\.?|no\.?|number|nummer|#|top|fakt|fact|rank|stand|as of|seit|since)\s*$", re.I)
QUOTE = re.compile(r"„([^“”]{10,})[“”]|\"([^\"]{10,})\"|«([^»]{10,})»")
ATTRIBUTION = re.compile(
    r"\b(?i:sagte|sagt|meinte|erklärte|behauptete|behauptet|betonte|laut|nach\s+Angaben\s+(?:von|der|des)|"
    r"nach\s+Aussage\s+(?:von|der|des)|according\s+to|said|says|claims?|claimed|stated|argues?|argued|quoted|told"
    r")\s+(?:dem\s+|der\s+|den\s+)?"
    r"([A-ZÄÖÜ][\w.-]+(?:\s+[A-ZÄÖÜ][\w.-]+){0,2})")
ATTRIBUTION_POST = re.compile(r"\b([A-ZÄÖÜ][\w.-]+)\s+zufolge\b")
COMPARE_TIMES = re.compile(
    r"(?P<f>\d+(?:[.,]\d+)?)-?\s?(?:mal|x|×|times)(?:\s+so)?\s+(?:\w+\s+)?(?:wie|als|as)\s+(?P<ref>[^.,!?;–]+)|"
    r"(?P<f2>\d+(?:[.,]\d+)?)\s+times\s+(?:the\s+(?:size|capacity)\s+of)\s+(?P<ref2>[^.,!?;–]+)", re.I)
COMPARE_PCT = re.compile(
    r"(?P<p>\d+(?:[.,]\d+)?)\s+(?:Prozent|percent|%)\s+(?:\w+\s+)?(?:größer|höher|tiefer|mehr|bigger|taller|higher|deeper|more)"
    r"(?:\s+\w+)?\s+(?:als|than)\s+(?P<ref>[^.,!?;–]+)", re.I)
COUNT_PATTERNS = [
    re.compile(r"\btop\s*(\d+)\b", re.I),
    re.compile(r"\b(\d+)\s+(?:Fakten|Fakt|facts|Plätze|Plätzen|places|Gründe|reasons|Dinge|things|Rekorde|records)\b", re.I),
    re.compile(r"\b(\d+)\s+(?:der\s+|of\s+the\s+)?(?:höchsten|größten|längsten|tiefsten|schwersten|schnellsten|ältesten|"
               r"jüngsten|kleinsten|stärksten|breitesten|reichsten|bekanntesten|beliebtesten|gefährlichsten|besten|tallest|"
               r"highest|largest|biggest|longest|deepest|heaviest|fastest|oldest|youngest|smallest|strongest|widest|richest|"
               r"best)\b", re.I),
]
_MONTH_WORDS = {"januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november",
                "dezember", "january", "february", "march", "may", "june", "july", "october", "december"}

_NUM = re.compile(r"(?<![\w.,/#-])(\d{1,3}(?:[.,]\d{3})+(?!\d)|\d+(?:[.,]\d+)?)"
                  r"(?:\s*(?P<scale>Millionen|Million|Milliarden|Milliarde|Billionen|Billion|Mio\.?|Mrd\.?|million|billion|"
                  r"trillion|thousand|Tausend)\b)?", re.I)
_SCALE = {"de": {"millionen": 1e6, "million": 1e6, "mio": 1e6, "mio.": 1e6, "milliarden": 1e9, "milliarde": 1e9,
                 "mrd": 1e9, "mrd.": 1e9, "billionen": 1e12, "billion": 1e12, "tausend": 1e3},
          "en": {"million": 1e6, "mio": 1e6, "billion": 1e9, "trillion": 1e12, "thousand": 1e3, "milliarden": 1e9,
                 "milliarde": 1e9, "millionen": 1e6, "tausend": 1e3}}


def _parse(raw: str, lang: str) -> float | None:
    thousands, decimal = (".", ",") if lang == "de" else (",", ".")
    tok = raw
    if re.fullmatch(rf"\d{{1,3}}(?:{re.escape(thousands)}\d{{3}})+", tok):
        tok = tok.replace(thousands, "")
    else:
        tok = tok.replace(thousands, "").replace(decimal, ".") if tok.count(decimal) <= 1 else tok.replace(decimal, "")
        if tok.count(".") > 1:
            return None
    try:
        return float(tok)
    except ValueError:
        return None


def zahlen(satz: str, lang: str) -> list[dict]:
    """Mengenangaben eines Satzes: Wert (mit Größenwort), Modifikator davor, Position. Jahre, Tage, Plätze entfallen."""
    out, prev_year = [], False
    for m in _NUM.finditer(satz):
        raw = m.group(1)
        digits = raw.rstrip(".,")
        before, after = satz[:m.start()], satz[m.end(1):]
        if _is_year(digits, before, after, prev_year):
            prev_year = True
            continue
        prev_year = False
        if _is_day(digits, before, after) or RANK_BEFORE.search(before[-14:]) or re.match(r"\.\s*(?:Platz|Mal)\b", after):
            continue
        if re.match(r"\s*(?:" + "|".join(_MONTH_WORDS) + r")\b", after, re.I):
            continue
        value = _parse(digits, lang)
        if value is None:
            continue
        scale = m.group("scale")
        if scale:
            value *= _SCALE[lang if lang in _SCALE else "en"].get(scale.lower(), 1.0)
        mod = next((name for name, rx in MODS if rx.search(before[-30:])), "")
        out.append({"wert": value, "mod": mod, "roh": m.group(0).strip()})
    return out


# --------------------------------------------------------------------------- Kontext (die geprüften Daten)

class Kontext:
    """Die geprüften Daten eines Videos: was darf der Text behaupten?"""

    def __init__(self, spec: VideoSpec, research: Research, heute: date | None = None):
        self.spec, self.research = spec, research
        self.heute = heute or date.today()
        self.facts = spec.kind == "facts"
        self.items = {it.rank: it for it in research.items}
        self.top = min(research.items, key=lambda i: i.rank, default=None)
        self.n = len(research.items)
        self.labels = {lab.lower() for it in research.items for lab in it.labels.values() if lab}
        self.titles = " ".join(spec.title.values())
        self._werte: dict[int, float] = {}
        self._bekannt: dict[str, list[float]] = {}

    # Werte ---------------------------------------------------------------
    def anzeige(self, item) -> float:
        if item.rank not in self._werte:
            try:
                self._werte[item.rank] = float(quantity(item.value, item.unit, self.spec.unit).value)
            except Exception:                                   # noqa: BLE001 – unbekannte Einheit: Rohwert
                self._werte[item.rank] = float(item.value)
        return self._werte[item.rank]

    def beleg(self, rank: int | None) -> str:
        pool = [self.items[rank]] if rank in self.items else list(self.research.items)
        parts = []
        for it in pool:
            if self.facts:
                parts += [it.fact.get("beleg", ""), *(it.fact.get("belege") or [])]
            else:
                parts += [*it.summary.values(), *it.descriptions.values()]
        return " ".join(str(p) for p in parts if p)

    def kandidaten(self, rank: int | None, text_lang: str) -> list[float]:
        """Geprüfte Zahlen, auf die sich eine Angabe im Text beziehen kann."""
        if self.facts:
            return [v for v in _numbers_of(self.beleg(rank)) if v > 0]
        if rank in self.items:
            return [self.anzeige(self.items[rank])]
        return [self.anzeige(it) for it in self.research.items]

    def bekannt(self, lang: str) -> list[float]:
        """Weitere erlaubte Zahlen (Abstände, Verhältnisse, Anzahl, Vergleichswerte) – diese gelten nie als Abweichung."""
        if lang in self._bekannt:
            return self._bekannt[lang]
        vals = [self.anzeige(it) for it in self.research.items]
        out = [float(self.n), *vals]
        out += [abs(a - b) for a in vals for b in vals if a != b]
        ref = (self.research.references or {}).get(lang) or {}
        if ref.get("value"):
            try:
                rv = float(quantity(ref["value"], ref.get("unit", "Q199"), self.spec.unit).value)
            except Exception:                                   # noqa: BLE001
                rv = float(ref["value"])
            out += [rv] + [v / rv for v in vals if rv] + [rv / v for v in vals if v]
        self._bekannt[lang] = [v for v in out if v]
        return self._bekannt[lang]

    # Quellenlage -----------------------------------------------------------
    def schwach(self, item) -> bool:
        """Nur von Wikipedia/Wikidata gestützt (kein unabhängiger Beleg außerhalb)?"""
        v = item.verification or {}
        if self.facts:
            return True                                          # Fakten stützen sich auf Wikipedia-Artikel
        if "n_extern" in v:
            return not v["n_extern"] or v.get("status") not in STATUS_OK
        return not external_sources(v.get("sources", [])) or v.get("status") not in STATUS_OK

    def quellen_namen(self) -> set[str]:
        names = {"wikipedia", "wikidata"}
        for k, v in SOURCE_NAMES.items():
            names |= {k.lower(), *(x.lower() for x in v.values())}
        for it in self.research.items:
            names |= {str(s).lower() for s in (it.verification or {}).get("sources", [])}
            names.add(str(it.fact.get("quelle", "")).lower())
        return {n for n in names if n}

    def offenlegung_wahr(self, lang: str) -> str | None:
        """None, wenn die Standard-Offenlegung stimmt, sonst die ehrliche Fassung."""
        if self.facts:
            if self.research.items and all("wikipedia.org" in str(i.fact.get("url", "")) for i in self.research.items):
                return HONEST[True][lang]
            return None
        ok = bool(self.research.items) and all(
            (it.verification or {}).get("status") in STATUS_OK and not self.schwach(it) for it in self.research.items)
        return None if ok else HONEST[False][lang]

    @staticmethod
    def offenlegungen(lang: str) -> set[str]:
        """Bekannte Offenlegungszeilen (Standard und ehrliche Fassung): sie werden nur auf Wahrheit geprüft."""
        return {DISCLOSURE[lang], FACT_DISCLOSURE[lang], HONEST[True][lang], HONEST[False][lang]}


HONEST = {
    True: {"de": "ℹ️ Die Stimme ist KI-generiert. Jeder Fakt ist wörtlich in einem Wikipedia-Artikel belegt, Zahlen sind mit "
                 "einer zweiten Quelle abgeglichen.",
           "en": "ℹ️ The voice is AI-generated. Every fact is backed word for word by a Wikipedia article; figures are "
                 "cross-checked with a second source."},
    False: {"de": "ℹ️ Die Stimme ist KI-generiert. Die Zahlen stammen aus Wikidata; nicht jede ist von unabhängigen Quellen "
                  "bestätigt – Details im Prüfbericht.",
            "en": "ℹ️ The voice is AI-generated. The figures come from Wikidata; not every one is confirmed by independent "
                  "sources – see the review report."},
}


def _numbers_of(text: str) -> set[float]:
    out: set[float] = set()
    for lang in ("de", "en"):
        out |= {float(x) for x in textcheck.numbers(text, lang)}
    return out


# --------------------------------------------------------------------------- Regeln

def _befund(regel: str, a: Aussage, satz: str, grund: str, aktion: str = "streichen", ersatz: str = "") -> Befund:
    return Befund(regel=regel, lang=a.lang, art=a.art, satz=satz, grund=grund, rank=a.rank, idx=a.idx, aktion=aktion,
                  ersatz=ersatz, herkunft=a.herkunft)


def _in_namen(ctx: Kontext, wort: str) -> bool:
    """Das Wort gehört zu einem Namen („Largest Brewery“) und ist keine Behauptung."""
    return _words_in(wort.strip().lower(), ctx.labels)


def regel_superlativ(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    beleg = ctx.beleg(a.rank)
    for key, rx in SUPER:
        for m in rx.finditer(satz):
            word = m.group(0)
            if _in_namen(ctx, word) or rx.search(beleg) or re.search(r"\b(?:unser\w*|our)\s+$", satz[:m.start()], re.I):
                continue                                          # Name, belegt oder „unser stärkster Fakt“ (eigenes Ranking)
            if not ctx.facts and key not in ("einzig", "erst") and rx.search(ctx.titles):
                # das Kriterium des Rankings selbst: für das Ranking als Ganzes und die (vollständige) Spitze
                if a.rank is None or (a.rank == 1 and not ctx.research.partial):
                    continue
            return [_befund("superlativ", a, satz, f"„{word.strip()}“ ist ohne Beleg in den geprüften Daten eine "
                                                   f"unbelegte Tatsachenbehauptung.")]
    return []


def _closest(x: float, cands: list[float]) -> float | None:
    near = [v for v in cands if v > 0 and 0.5 <= x / v <= 2.0]
    return min(near, key=lambda v: abs(x - v) / v) if near else None


def _beleg_sagt_es(beleg: str, mod: str, x: float) -> bool:
    return any(z["mod"] == mod and abs(z["wert"] - x) <= 1e-9 * max(1.0, x)
               for lang in ("de", "en") for sent in saetze(beleg) for z in zahlen(sent, lang))


def regel_zahlen(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    out: list[Befund] = []
    cands = ctx.kandidaten(a.rank, a.lang)
    if not cands:
        return out
    known = ctx.bekannt(a.lang) if not ctx.facts else []
    own = cands if a.rank is not None or ctx.facts else [ctx.anzeige(ctx.top)] if ctx.top else []
    for z in zahlen(satz, a.lang):
        x, mod = z["wert"], z["mod"]
        v = _closest(x, cands)
        if v is None:
            continue
        rel = abs(x - v) / v
        eps = 1e-9 * max(1.0, v)
        if ctx.facts and mod and _beleg_sagt_es(ctx.beleg(a.rank), mod, x):
            continue                                              # steht so in der Quelle („über 100“)
        if mod == "ueber" and x >= v - eps:
            out.append(_befund("bis_zu", a, satz, f"„{z['roh']}“ mit „über/mehr als“ – der geprüfte Wert ist aber {v:g}; "
                                                  f"„über“ gilt nur für Zahlen unterhalb des Werts."))
        elif mod == "bis_zu" and x < v - eps:
            out.append(_befund("bis_zu", a, satz, f"„bis zu {z['roh']}“ – der geprüfte Wert {v:g} liegt darüber."))
        elif mod == "unter" and x <= v + eps:
            out.append(_befund("bis_zu", a, satz, f"„unter {z['roh']}“ – der geprüfte Wert {v:g} ist nicht kleiner."))
        elif mod == "mindestens" and x > v + eps:
            out.append(_befund("bis_zu", a, satz, f"„mindestens {z['roh']}“ – der geprüfte Wert {v:g} liegt darunter."))
        elif mod == "fast" and x < v - eps:
            out.append(_befund("bis_zu", a, satz, f"„fast {z['roh']}“ – der geprüfte Wert {v:g} liegt schon darüber."))
        elif mod == "fast" and rel > ROUND_TOLERANCE:
            out.append(_befund("rundung", a, satz, f"„fast {z['roh']}“ weicht {rel:.0%} vom geprüften Wert {v:g} ab (erlaubt: 5 %)."))
        elif mod == "etwa" and rel > ROUND_TOLERANCE:
            out.append(_befund("rundung", a, satz, f"„{z['roh']}“ weicht {rel:.0%} vom geprüften Wert {v:g} ab (erlaubt: 5 %)."))
        elif not mod and not ctx.facts and v in own and ROUND_TOLERANCE < rel <= NEAR_WINDOW and \
                not any(abs(x - k) / k <= 0.02 for k in known):
            out.append(_befund("rundung", a, satz, f"„{z['roh']}“ weicht {rel:.0%} vom geprüften Wert {v:g} ab (erlaubt: 5 %)."))
    return out


def regel_zahl_ohne_beleg(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    """Nur Fakten-Rankings: Zahlen müssen im Beleg stehen (wiederverwendet `textcheck.numbers`)."""
    if not ctx.facts or a.art in (TITEL, COVER):
        return []
    allowed = textcheck.numbers(ctx.beleg(a.rank), "de") | textcheck.numbers(ctx.beleg(a.rank), "en")
    if a.rank is None:
        allowed |= textcheck.numbers(ctx.beleg(None), "de") | textcheck.numbers(ctx.beleg(None), "en")
    allowed |= {f"{n:g}" for n in range(0, ctx.n + 2)}
    allowed |= {str(ctx.heute.year), str(ctx.heute.year - 1)} | textcheck.digits(ctx.titles)
    extra = textcheck.numbers(satz, a.lang) - allowed
    if extra:
        return [_befund("zahl_ohne_beleg", a, satz, "Zahl(en) " + ", ".join(sorted(extra)[:3]) + " stehen nicht im Beleg.")]
    return []


def regel_zeitbezug(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    if ctx.facts:
        has_year = re.search(r"\b(?:1[5-9]|20)\d{2}\b", satz)
        trigger = TIME_WORDS.search(satz) or (POP_WORDS.search(satz) and zahlen(satz, a.lang))
        if trigger and not has_year and not re.search(r"\bstand\b|\bas of\b", satz, re.I):
            years = [int(y) for y in re.findall(r"\b((?:1[5-9]|20)\d{2})\b", ctx.beleg(a.rank)) if int(y) <= ctx.heute.year]
            if years and a.art == SPRECH:
                word = TEXT[a.lang]["as_of"].format(year=max(years))
                return [_befund("zeitbezug", a, satz, f"„{trigger.group(0)}“ ohne Stand – der Beleg nennt {max(years)}.",
                                "ergaenzen", word)]
            return [_befund("zeitbezug", a, satz, f"„{trigger.group(0)}“ ohne Stand: Ob der Wert noch aktuell ist, "
                                                  f"belegt die Quelle nicht.")]
        return []
    item = ctx.items.get(a.rank) if a.rank is not None else None
    if not item or a.art != SPRECH:
        return []
    year = as_of_year(ctx.spec, item)
    if not year or ctx.heute.year - int(year) < STALE_YEARS:
        return []
    if re.search(rf"\b{year}\b|\bstand\b|\bas of\b", " ".join(saetze(a.text)), re.I):
        return []
    if satz != saetze(a.text)[-1]:
        return []                                                # nur einmal je Abschnitt melden (letzter Satz)
    return [_befund("zeitbezug", a, satz, f"Der Wert stammt von {year} und kann sich seither geändert haben – "
                                          f"der Stand fehlt im Text.", "ergaenzen", TEXT[a.lang]["as_of"].format(year=year))]


def regel_ursache(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    m = CAUSAL.search(satz)
    if not m or _in_namen(ctx, m.group(0)) or CAUSAL.search(ctx.beleg(a.rank)):
        return []
    return [_befund("ursache", a, satz, f"„{m.group(0)}“ behauptet eine Ursache; der Beleg nennt nur den Sachverhalt, "
                                        f"keinen Kausalzusammenhang.")]


def regel_verallgemeinerung(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    for m in GENERAL.finditer(satz):
        around = satz[max(0, m.start() - 12): m.end() + 22]
        if _GENERAL_OK.search(around) or _in_namen(ctx, m.group(0)) or GENERAL.search(ctx.beleg(a.rank)):
            continue
        return [_befund("verallgemeinerung", a, satz, f"„{m.group(0)}“ lässt keine Ausnahme zu; der Beleg sagt das nicht.")]
    return []


def regel_clickbait(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    out = []
    if a.art in (TITEL, COVER, BESCHREIBUNG, CAPTION):
        m = CLICKBAIT.search(satz)
        if m:
            out.append(_befund("clickbait", a, satz, f"„{m.group(0)}“ verspricht mehr, als das Video halten kann.",
                               "ersetzen" if a.art == TITEL else "streichen"))
    if a.art in (TITEL, COVER, BESCHREIBUNG, CAPTION, HOOK, SPRECH):
        m = PROMISE.search(satz)
        if m and not PROMISE.search(ctx.beleg(a.rank)) and not PROMISE.search(ctx.beleg(None)) \
                and not PROMISE.search(ctx.titles) and not _in_namen(ctx, m.group(0)):
            out.append(_befund("clickbait", a, satz, f"„{m.group(0)}“ verspricht etwas, das in den geprüften Daten nicht "
                                                      f"vorkommt.", "ersetzen" if a.art == TITEL else "streichen"))
    if a.art in (TITEL, COVER, BESCHREIBUNG, CAPTION, HOOK) and ctx.n:
        for rx in COUNT_PATTERNS:
            for m in rx.finditer(satz):
                if int(m.group(1)) != ctx.n and not (a.art == BESCHREIBUNG and re.search(r"Platz|No\.|#", satz[max(0, m.start() - 6):m.start()])):
                    out.append(_befund("anzahl", a, satz, f"Im Text steht {m.group(1)}, gezeigt werden aber {ctx.n}.",
                                       "ersetzen", re.sub(rf"\b{m.group(1)}\b", str(ctx.n), satz, count=1)))
                    return out
    return out


def regel_zitat(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    beleg = _n(ctx.beleg(a.rank) + " " + ctx.beleg(None))
    for m in QUOTE.finditer(satz):
        quote = next(g for g in m.groups() if g)
        if len(quote.split()) >= 5 and _n(quote) not in beleg:
            return [_befund("zitat", a, satz, f"Das Zitat „{quote[:50]}…“ steht nicht wörtlich in der Quelle.")]
    sources = ctx.quellen_namen()
    names = [m.group(1) for m in ATTRIBUTION.finditer(satz)] + [m.group(1) for m in ATTRIBUTION_POST.finditer(satz)]
    for name in names:
        low = name.lower().strip(".")
        if any(s in low or low in s for s in sources) or low in beleg or _in_namen(ctx, name):
            continue
        return [_befund("zitat", a, satz, f"Die Aussage wird „{name}“ zugeschrieben – die Quelle nennt das nicht.")]
    return []


def regel_bezugsgroesse(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    ref = (ctx.research.references or {}).get(a.lang) or {}
    for m in list(COMPARE_TIMES.finditer(satz)) + list(COMPARE_PCT.finditer(satz)):
        d = m.groupdict()
        name = (d.get("ref") or d.get("ref2") or "").strip()
        claim = d.get("f") or d.get("f2") or d.get("p")
        factor = _parse(claim.replace(" ", ""), a.lang) if claim else None
        if not name or factor is None:
            continue
        pct = bool(d.get("p"))
        low = _n(name)
        target = None
        if ref and ref.get("value") and any(_n(ref.get(k, "")) and (_n(ref[k]) in low or low in _n(ref[k]))
                                            for k in ("name", "short", "in")):
            target = ("Vergleichsobjekt", ref["value"], "ref")
        else:
            other = next((it for it in ctx.research.items
                          if any(_n(lab) and (_n(lab) in low or low in _n(lab)) for lab in it.labels.values())), None)
            if other is not None:
                target = ("Platz", other.value, other)
        if ctx.facts:
            if _n(name) not in _n(ctx.beleg(a.rank)):
                return [_befund("bezugsgroesse", a, satz, f"Das Vergleichsobjekt „{name}“ steht nicht im Beleg.")]
            continue
        if target is None:
            return [_befund("bezugsgroesse", a, satz, f"„{name}“ ist kein belegtes Vergleichsobjekt "
                                                      f"(weder Referenzwert noch Platz im Ranking).")]
        item = ctx.items.get(a.rank)
        if item is None or not target[1]:
            continue
        true = abs(item.value) / abs(target[1])
        claimed = 1 + factor / 100 if pct else factor
        if true and abs(claimed - true) / true > ROUND_TOLERANCE + 0.03:
            return [_befund("bezugsgroesse", a, satz, f"Faktor {claim} passt nicht: geprüft ist {true:.2f} gegenüber „{name}“.")]
    return []


def regel_quellenlage(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    if a.art in (TITEL, COVER) or (a.art in (BESCHREIBUNG, CAPTION) and satz.startswith("ℹ")):
        return []
    items = [ctx.items[a.rank]] if a.rank in ctx.items else list(ctx.research.items)
    weak = [it for it in items if ctx.schwach(it)]
    if not weak:
        return []
    m = STRONG.search(satz)
    if not m or _in_namen(ctx, m.group(0)) or STRONG.search(ctx.beleg(a.rank)):
        return []                                                # steht so in der Quelle selbst
    return [_befund("quellenlage", a, satz, f"„{m.group(0)}“ – der Wert ist nur von Wikipedia/Wikidata gestützt "
                                            f"(Platz {', '.join(str(i.rank) for i in weak[:3])}); das ist weder bewiesen noch offiziell.")]


def regel_offenlegung(ctx: Kontext, a: Aussage, satz: str) -> list[Befund]:
    if a.art not in (BESCHREIBUNG, CAPTION) or not satz.startswith("ℹ"):
        return []
    standard = {DISCLOSURE.get(a.lang), FACT_DISCLOSURE.get(a.lang)}
    if satz.strip() not in standard:
        return []
    honest = ctx.offenlegung_wahr(a.lang)
    if honest and honest != satz.strip():
        why = ("nicht alle Zahlen sind von mehreren unabhängigen Quellen bestätigt" if not ctx.facts
               else "als Quelle dienen Wikipedia-Artikel, nicht allgemein „Fachquellen“")
        return [_befund("quellenlage", a, satz, f"Die Offenlegung behauptet mehr, als geprüft ist: {why}.", "ersetzen", honest)]
    return []


RULES = [regel_superlativ, regel_zahlen, regel_zahl_ohne_beleg, regel_zeitbezug, regel_ursache, regel_verallgemeinerung,
         regel_clickbait, regel_zitat, regel_bezugsgroesse, regel_quellenlage, regel_offenlegung]


# --------------------------------------------------------------------------- Aussagen sammeln

def _line_rank(line: str) -> int | None:
    m = re.match(r"(\d+)\.\s", line)
    return int(m.group(1)) if m else None


def aussagen(ctx: Kontext, script: Script, meta: dict | None = None, cover: bool = True) -> list[Aussage]:
    spec, lang = ctx.spec, script.lang
    out: list[Aussage] = []
    for i, seg in enumerate(script.segments):
        art = HOOK if seg.kind == "intro" else SPRECH
        out.append(Aussage(lang, art, seg.text, seg.rank, i))
        sub = " ".join(w["text"] for w in seg.words)
        if sub and _n(sub) != _n(seg.text):
            out.append(Aussage(lang, UNTERTITEL, sub, seg.rank, i))
    out.append(Aussage(lang, TITEL, spec.title[lang], herkunft="spec_titel"))
    if meta:
        for t in dict.fromkeys([meta.get("title", ""), meta.get("title_chosen", ""), *(meta.get("titles") or [])]):
            if t and t != spec.title[lang]:
                out.append(Aussage(lang, TITEL, t))
        for line in str(meta.get("description", "")).splitlines():
            if line.strip() and not line.startswith(("•", "📷", "📖", "#")):
                out.append(Aussage(lang, BESCHREIBUNG, line.strip(), _line_rank(line)))
        for line in str(meta.get("caption", "")).splitlines():
            if line.strip() and not line.strip().startswith("#"):
                out.append(Aussage(lang, CAPTION, line.strip()))
    if cover:
        try:
            from .render.cover import cover_texts

            for key, text in cover_texts(spec, ctx.research, lang).items():
                if key != "image_path" and text:
                    out.append(Aussage(lang, COVER, str(text), herkunft="spec_titel" if key == "headline" else ""))
        except Exception as exc:                                  # noqa: BLE001 – Cover ohne PIL: Texte entfallen
            log.debug("Cover-Texte nicht prüfbar: %s", exc)
    return out


def befunde_von(ctx: Kontext, a: Aussage, extern: list[dict] | None = None) -> list[Befund]:
    parts = saetze(a.text) if a.art in (SPRECH, HOOK, UNTERTITEL) else [a.text]
    found: list[Befund] = []
    boilerplate = a.art in (BESCHREIBUNG, CAPTION) and a.text.strip() in ctx.offenlegungen(a.lang)
    for satz in parts:
        for rule in ([regel_offenlegung] if boilerplate else RULES):
            found += rule(ctx, a, satz)
    for e in extern or []:
        if e["lang"] == a.lang and e.get("art") == a.art and _n(e["stelle"]) in _n(a.text):
            satz = next((s for s in parts if _n(e["stelle"]) in _n(s)), parts[0] if parts else a.text)
            found.append(_befund("gegenlesen", a, satz, e["grund"]))
    seen, unique = set(), []
    for b in found:                                               # ein Befund je Satz und Regel
        key = (b.regel, b.satz)
        if key not in seen:
            seen.add(key)
            unique.append(b)
    return unique


# --------------------------------------------------------------------------- Korrektur

SAFE_OUTRO = {"de": "Das war's. Schreib es in die Kommentare und folge für mehr!",
              "en": "That's it. Tell me in the comments and follow for more!"}


def _fallback_item(ctx: Kontext, script: Script, seg) -> str | None:
    """Geprüfte Textbaustein-Fassung eines Platzes."""
    item = ctx.items.get(seg.rank)
    if item is None:
        return None
    from .script import distinct_precision, item_facts, rank_sentence, template_item_text, word_budget

    lang = script.lang
    if ctx.facts:
        kurz = item.descriptions.get(lang, "")
        return f"{rank_sentence(item.rank, item.labels[lang], lang, False)} {kurz}".strip()
    precision = distinct_precision(ctx.spec, ctx.research.items, lang)
    facts = item_facts(ctx.spec, item, lang, ctx.research.references.get(lang), precision.get(item.qid, 0))
    return template_item_text(facts, lang, word_budget(ctx.spec, ctx.research), first=False, detail=1)


def _apply_sentences(text: str, befunde: list[Befund]) -> tuple[str, list[Befund]]:
    parts = saetze(text)
    done: list[Befund] = []
    for b in befunde:
        if b.satz not in parts:
            continue
        i = parts.index(b.satz)
        if b.aktion == "ergaenzen" and b.ersatz:
            parts.insert(i + 1, b.ersatz)
            b.korrektur = f"ergänzt: „{b.ersatz}“"
        elif b.aktion == "ersetzen" and b.ersatz:
            parts[i] = b.ersatz
            b.korrektur = f"ersetzt durch „{b.ersatz}“"
        else:
            parts.pop(i)
            b.korrektur = "Satz gestrichen"
        b.korrigiert = True
        done.append(b)
    return " ".join(parts).strip(), done


class Pruefer:
    """Prüft und korrigiert die Texte eines Videos; sammelt Protokoll und Befunde des Gegenlesens."""

    def __init__(self, spec: VideoSpec, research: Research, heute: date | None = None):
        self.spec, self.research = spec, research
        self.ctx = Kontext(spec, research, heute)
        self.extern: list[dict] = []
        self.protokoll: dict[str, list[Befund]] = {}
        self.berichte: dict[str, Bericht] = {}

    # -- Prüfen -------------------------------------------------------------
    def pruefe(self, script: Script, meta: dict | None = None, cover: bool = True) -> Bericht:
        items = aussagen(self.ctx, script, meta, cover)
        bericht = Bericht(script.lang, geprueft=len(items))
        for a in items:
            bericht.offen += befunde_von(self.ctx, a, self.extern)
        bericht.korrigiert = list(self.protokoll.get(script.lang, []))
        self.berichte[script.lang] = bericht
        return bericht

    # -- Korrigieren: Sprechtext --------------------------------------------
    def korrigiere_skript(self, script: Script) -> Script:
        """Befunde in Sprechtext/Hook beheben (mutiert `script`); Sätze ersetzen/ergänzen/streichen, bei leerem Platz die
        Textbaustein-Fassung. Danach erneut prüfen, höchstens `MAX_ROUNDS` Runden."""
        for _ in range(MAX_ROUNDS):
            offen = [b for b in self.pruefe(script, None, cover=False).offen if b.art in (SPRECH, HOOK) and b.idx is not None]
            if not offen:
                break
            changed = False
            for idx in sorted({b.idx for b in offen}):
                seg = script.segments[idx]
                mine = [b for b in offen if b.idx == idx]
                new, done = _apply_sentences(seg.text, mine)
                if not done:
                    continue
                if seg.kind == "item" and (not new or len(new.split()) < 4):
                    new = _fallback_item(self.ctx, script, seg) or new
                    for b in done:
                        b.korrektur += " (Textbaustein-Fassung)"
                elif seg.kind == "intro" and not new:
                    new = f"{script.title}!"
                elif seg.kind == "outro" and not new:
                    new = SAFE_OUTRO[script.lang]
                seg.text, seg.words, seg.audio_path = new, [], None
                self.protokoll.setdefault(script.lang, []).extend(done)
                changed = True
            if not changed:
                break
        self.pruefe(script, None, cover=False)
        return script

    # -- Korrigieren: Titel, Beschreibung, Cover ----------------------------
    def korrigiere_meta(self, script: Script, meta: dict) -> dict:
        lang = script.lang
        for _ in range(MAX_ROUNDS):
            offen = [b for b in self.pruefe(script, meta).offen if b.art in (TITEL, BESCHREIBUNG, CAPTION, COVER)]
            if not offen:
                break
            changed = False
            for b in offen:
                if self._fix_meta(script, meta, b):
                    self.protokoll.setdefault(lang, []).append(b)
                    changed = True
            if not changed:
                break
        self.pruefe(script, meta)
        return meta

    def _fix_meta(self, script: Script, meta: dict, b: Befund) -> bool:
        lang = script.lang
        if b.herkunft == "spec_titel":
            if b.aktion == "ersetzen" and b.ersatz and b.regel == "anzahl":
                self.spec.title[lang] = b.ersatz
                b.korrigiert, b.korrektur = True, f"Titel im Video angepasst: „{b.ersatz}“"
                return True
            return False
        if b.art == TITEL:
            from .metadata import fit_title
            from .render.cover import clean_title

            base = fit_title(clean_title(self.spec.title[lang]))
            new = b.ersatz or base
            for key in ("title", "title_chosen"):
                if meta.get(key) == b.satz:
                    meta[key] = new
            meta["titles"] = list(dict.fromkeys(new if t == b.satz else t for t in meta.get("titles") or []))
            meta["caption"] = str(meta.get("caption", "")).replace(b.satz, new)
            b.korrigiert, b.korrektur = True, f"Titel ersetzt durch „{new}“"
            return True
        field_name = "description" if b.art == BESCHREIBUNG else "caption" if b.art == CAPTION else ""
        if not field_name:
            return False
        lines = str(meta.get(field_name, "")).splitlines()
        hit = [i for i, line in enumerate(lines) if line.strip() == b.satz]
        if not hit:
            return False
        if b.aktion in ("ersetzen", "ergaenzen") and b.ersatz:
            lines[hit[0]] = b.ersatz
            b.korrektur = f"ersetzt durch „{b.ersatz}“"
        else:
            lines.pop(hit[0])
            b.korrektur = "Zeile gestrichen"
        meta[field_name] = "\n".join(lines)
        b.korrigiert = True
        return True

    # -- Gegenlesen ---------------------------------------------------------
    def gegenlesen(self, scripts: list[Script], metas: dict[str, dict]) -> int:
        """Claude/Notbetrieb-LLM liest gegen. Übernommen werden nur Befunde mit wörtlicher Textstelle und Begründung.
        Wirft `handoff.WritingNeeded`, solange Claudes Antwort aussteht (der Auftrag läuft dann mit --weiter weiter)."""
        if not handoff.active() or not scripts:
            return 0
        pool: dict[str, str] = {}
        texts = []
        for script in scripts:
            for a in aussagen(self.ctx, script, metas.get(script.lang), cover=False):
                tid = f"{script.lang}-{len(texts)}"
                pool[tid] = a.text
                texts.append({"id": tid, "sprache": a.lang, "art": a.art, "platz": a.rank, "text": a.text, "_a": a})
        data = {"regeln": {k: v[1] for k, v in REGELN.items() if k != "gegenlesen"},
                "belege": self._belege(), "aussagen": [{k: v for k, v in t.items() if k != "_a"} for t in texts]}
        answer = handoff.request("wahrheit_pruefung", INSTRUCTIONS, data)
        found = answer.get("befunde") if isinstance(answer, dict) else answer
        accepted = 0
        for e in found if isinstance(found, list) else []:
            if not isinstance(e, dict):
                continue
            tid, stelle, grund = str(e.get("id", "")), str(e.get("stelle", "")).strip(), str(e.get("grund", "")).strip()
            text = pool.get(tid)
            if text is None or len(stelle) < 3 or len(grund) < 12 or _n(stelle) not in _n(text):
                continue                                           # zeigt auf keinen Textteil: nicht übernehmen
            art = next(t["_a"].art for t in texts if t["id"] == tid)
            self.extern.append({"lang": tid.split("-")[0], "stelle": stelle, "grund": grund[:300], "art": art})
            accepted += 1
        return accepted

    def _belege(self) -> list[dict]:
        out = []
        for it in sorted(self.research.items, key=lambda i: i.rank):
            lang = self.spec.langs[0]
            out.append({"platz": it.rank, "name": it.labels.get(lang) or it.labels.get("en", ""),
                        "wert": None if self.ctx.facts else self.ctx.anzeige(it), "stand": it.value_date,
                        "status": (it.verification or {}).get("status"),
                        "nur_wikipedia_wikidata": self.ctx.schwach(it),
                        "beleg": it.fact.get("beleg") if self.ctx.facts else (it.summary.get(lang) or "")[:400]})
        return out

    # -- Bericht ------------------------------------------------------------
    def schwache(self, lang: str) -> list[str]:
        out = []
        for it in sorted(self.research.items, key=lambda i: i.rank):
            if self.ctx.schwach(it):
                name = it.labels.get(lang) or it.labels.get("en", "")
                v = it.verification or {}
                out.append(f"Platz {it.rank} ({name}): nur von Wikipedia/Wikidata gestützt"
                           + (f" – Status „{v.get('status')}“" if v.get("status") else ""))
        return out


INSTRUCTIONS = (
    "Du bist Faktenprüfer für Kurzvideos. Lies „aussagen“ (alle Texte des Videos: Sprechtext, Hook, Titel, Beschreibung) "
    "gegen „belege“ (die geprüften Daten) und die „regeln“. Melde NUR konkrete, begründete Befunde: Aussagen, die falsch "
    "sind, die Wahrheit anders verstehen lassen (Rundung, „über/fast/bis zu“, Zeitbezug, Ursache statt Zusammenhang, "
    "Verallgemeinerung, Superlativ, erfundenes Zitat, falsche Bezugsgröße, überzeichnete Quellenlage) oder etwas versprechen, "
    "das nicht im Video vorkommt. Neugier ist erlaubt („Platz 1 wird dich überraschen“), eine falsche Behauptung nicht. "
    "Melde nichts aus Geschmack und nichts, was korrekt belegt ist. Jeder Befund nennt die „id“ der Aussage, die „stelle“ "
    "(wörtlich kopierter Textteil) und den „grund“ (ein Satz). Gibt es nichts zu melden, antworte mit einer leeren Liste. "
    "Antwort: JSON {\"befunde\": [{\"id\": \"…\", \"stelle\": \"…\", \"grund\": \"…\"}]}."
)


# --------------------------------------------------------------------------- Prüfbericht

def review_section(pruefer: Pruefer, extra_gruende: dict[str, list[str]] | None = None) -> str:
    """Abschnitt „Wahrheits-Prüfung“ für review.md: geprüfte Aussagen, Befunde, Korrekturen, Quellenlage."""
    out = ["## Wahrheits-Prüfung", "",
           "Jede Aussage (Sprechtext, Hook, Untertitel, Titel, Cover, Beschreibung, TikTok-Text) wird gegen die geprüften "
           "Daten gehalten – Regeln: " + ", ".join(v[0] for k, v in REGELN.items() if k != "gegenlesen") + ".", ""]
    for lang, b in pruefer.berichte.items():
        state = "bestanden" if b.ok else "NICHT bestanden"
        out.append(f"**{lang.upper()}:** {b.geprueft} Aussagen geprüft, {len(b.korrigiert)} Befund(e) korrigiert, "
                   f"{len(b.offen)} offen – {state}.")
    out.append("")
    for lang, b in pruefer.berichte.items():
        for f in b.korrigiert:
            out.append(f"- Korrigiert ({lang.upper()}, {f.art}{f' Platz {f.rank}' if f.rank is not None else ''}, "
                       f"{REGELN.get(f.regel, (f.regel,))[0]}): „{f.satz}“ – {f.grund} → {f.korrektur or 'korrigiert'}")
        for f in b.offen:
            out.append(f"- **Offen** ({lang.upper()}, {f.art}{f' Platz {f.rank}' if f.rank is not None else ''}, "
                       f"{REGELN.get(f.regel, (f.regel,))[0]}): „{f.satz}“ – {f.grund}")
    for lang, reasons in (extra_gruende or {}).items():
        out += [f"- Endabnahme ({lang.upper()}): {r}" for r in reasons]
    weak = pruefer.schwache(pruefer.spec.langs[0])
    out += ["", "**Quellenlage (nur Wikipedia/Wikidata):** " + ("" if weak else "keine Plätze betroffen.")]
    out += [f"- {w}" for w in weak]
    return "\n".join(out) + "\n"


def in_review(review: str, section: str) -> str:
    """Abschnitt vor die Detail-Tabellen setzen (der App-Bericht ist gekürzt, das Wichtige steht vorn)."""
    for marker in ("\n## Ranking\n", "\n## Fakten-Ranking (Belege)\n"):
        if marker in review:
            head, tail = review.split(marker, 1)
            return head.rstrip() + "\n\n" + section + "\n" + marker.lstrip("\n").rstrip("\n") + "\n" + tail
    return review.rstrip() + "\n\n" + section
