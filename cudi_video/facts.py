"""Fakten-Ranking: jedes Thema lässt sich ranken – auch ohne messbare Zahl.

„5 coole Fakten über das Unterbewusstsein“ wird zu einem Countdown im gewohnten Ranking-Aussehen. Ablauf:

1. Claude wählt beim Planen 1–3 Fachartikel je Sprache (Wikipedia), der Code lädt deren Text.
2. Claude schreibt aus genau diesen Texten die Fakten – je Fakt mit einem WÖRTLICH kopierten Beleg-Satz.
3. Der Code prüft jeden Fakt streng: Beleg steht so in der Quelle, Zahlen im Text stehen im Beleg UND in einer
   zweiten Quelle (Fakten werden verglichen, nicht einfach übernommen), keine erfundenen Namen/Hauptwörter,
   keine Wertungen. Wer durchfällt, fliegt raus (Claude liefert dafür einige Fakten mehr).
4. Platz 1 ist der stärkste Fakt nach dem genannten Kriterium (z. B. „verblüffendste“) – ehrlich als
   redaktionelle Auswahl, nicht als Messwert.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from . import bildcheck, handoff, media, net, textcheck, themen
from .models import RankItem, Research
from .spec import VideoSpec

log = logging.getLogger(__name__)

ARTICLE_CHARS = 10000          # je Artikel – bis zu 4 spezifische Artikel je Sprache (je Aspekt einer)
WEAK_CLIP = 0.8                # Clip mit schwächerem Bildprüfungswert muss sich gegen ein Foto messen lassen
EXTRA_FACTS = 3                # Claude liefert so viele Fakten mehr, falls einzelne die Prüfung nicht bestehen
MIN_ARTICLE_CHARS = 1200
_NUM = (r"(?:ein|zwei|drei|vier|fünf|sechs|sieb|sieben|acht|neun|zehn|elf|zwölf|zwanzig|dreißig|vierzig|fünfzig|"
        r"sechzig|siebzig|achtzig|neunzig|hundert|tausend|und)")
COMPOUND_NUMBER = re.compile(rf"^{_NUM}{_NUM}+$")          # deutsche Zahlwörter aus mehreren Teilen („zweihundert“)

INSTRUCTIONS = (
    "Schreibe ein Fakten-Ranking für TikTok/YouTube Shorts zum Thema „thema“: genau „anzahl“ Fakten (das sind "
    "absichtlich mehr, als das Video zeigt – die Reserve ersetzt Fakten, die die Prüfung nicht bestehen; liefere "
    "trotzdem alle), sortiert nach „kriterium“ (rang 1 = am stärksten, er kommt im Video zuletzt). "
    + themen.TOPIC_RULES + " Jeder Fakt gehört zu einem Aspekt aus „aspekte“; verteile die Fakten auf möglichst "
    "verschiedene Aspekte. Verwende NUR Aussagen, die in den Texten unter „quellen“ stehen – nichts dazuerfinden, "
    "keine Zahl, die dort nicht steht (auch nicht ausgeschrieben oder errechnet), keine Gesundheits- oder "
    "Heilversprechen, keine Wertungen über Menschen oder Politik. Je Fakt: „beleg“ = EIN Satz, Zeichen für Zeichen "
    "WÖRTLICH aus einem Quelltext kopiert (die Kernaussage); „belege“ = 0–3 weitere wörtlich kopierte Sätze, auf "
    "denen die Erklärung beruht; „quelle“ = die „id“ des Quelltexts von „beleg“; „aspekt“ = einer der „aspekte“; für "
    "jede Sprache in „sprachen“: „titel_<sprache>“ (Überschrift, höchstens 45 Zeichen), „kurz_<sprache>“ "
    "(Kernaussage, höchstens 70 Zeichen) und „text_<sprache>“ (Sprechertext, ungefähr „woerter“ Wörter, direkte "
    "Ansprache mit „du“, kurze Sätze, nichts übertreiben; Namen von Personen, Orten, Studien oder Einrichtungen nur, "
    "wenn sie im Quelltext stehen). " + themen.KNOWLEDGE_STRUCTURE + " " + themen.AHA_FACTS + " "
    "Bild: „motiv“ = das KONKRETE, sichtbare Objekt des Fakts auf Englisch (2–3 Wörter, z. B. „shark teeth“, "
    "„shark skin denticles“, „megalodon fossil tooth“ – bei einem Zahn-Fakt also der Zahn, nicht das ganze Tier); "
    "„suche“ = Liste mit 2–3 englischen Suchbegriffen (je 2–4 Wörter) für passende Stockvideos/Fotos zu genau "
    "diesem Motiv. Antwort: "
    "{\"fakten\": [{\"rang\": 1, \"aspekt\": \"…\", \"beleg\": \"…\", \"belege\": [\"…\"], \"quelle\": \"…\", "
    "\"titel_de\": \"…\", \"kurz_de\": \"…\", \"text_de\": \"…\", \"aha_de\": \"…\", \"motiv\": \"…\", "
    "\"suche\": [\"…\", \"…\"]}]}."
)

INSTRUCTIONS_FIX = (
    "Einige Fakten wurden von der Prüfung abgelehnt. Unter „abgelehnt“ steht je Fakt dein Vorschlag („fakt“) und der "
    "Grund („grund“). Schreibe jeden neu, sodass er die Regeln aus „regeln“ erfüllt – bei „nicht belegt: …“ diese "
    "Wörter weglassen oder durch Wörter aus dem Quelltext ersetzen; bei „zu kurz“ mehr erklären (wie/warum, was es "
    "für dich bedeutet – belegt mit weiteren wörtlichen Sätzen in „belege“); bei „passt nicht zum Themenkern“ einen "
    "Fakt zu einem der „aspekte“ wählen; bei „Zahlen nur in einer Quelle“ oder einem "
    "Beleg, der nicht wörtlich passt, einen anderen Beleg-Satz aus „quellen“ wählen (ruhig ein anderer Fakt). "
    "Behalte „rang“ bei. Antwort im selben Format: {\"fakten\": [{\"rang\": …, \"beleg\": \"…\", …}]}."
)
INSTRUCTIONS_FIX2 = (
    " Letzte Runde: Wähle für jeden abgelehnten Platz einen Fakt OHNE Zahlen, dessen Beleg-Satz wörtlich im Quelltext "
    "steht, und verwende im Sprechertext nur Wörter, die in den Quelltexten vorkommen, oder ganz alltägliche Wörter "
    "– keine Namen, die nicht im Quelltext stehen."
)


def _norm(text: str) -> str:
    text = text.replace(" ", " ").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("„", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def article_text(lang: str, title: str, limit: int = ARTICLE_CHARS) -> tuple[str, str]:
    """Klartext eines Wikipedia-Artikels (gekürzt) und sein endgültiger Titel; leer, wenn es ihn nicht gibt."""
    data = net.get_json(f"https://{lang}.wikipedia.org/w/api.php",
                        params={"action": "query", "prop": "extracts", "explaintext": 1, "titles": title,
                                "redirects": 1, "format": "json", "formatversion": 2},
                        cache_hours=24 * 7, retries=4, max_wait=40)
    pages = data.get("query", {}).get("pages", [])
    page = pages[0] if pages else {}
    if page.get("missing") or page.get("invalid"):
        return "", title
    text = re.sub(r"\n=+ [^\n]*(Literatur|Weblinks|Einzelnachweise|References|External links|See also|Siehe auch|"
                  r"Further reading|Notes)[^\n]*=+\n.*", "", page.get("extract") or "", flags=re.S)
    return text[:limit], page.get("title", title)


def gather_sources(spec: VideoSpec) -> list[dict]:
    sources = []
    for lang, titles in (spec.facts.get("articles") or {}).items():
        for title in titles[:4]:
            try:
                text, real = article_text(lang, title)
            except net.FetchError as exc:
                log.warning("Artikel %s (%s) nicht abrufbar: %s", title, lang, exc)
                continue
            if len(text) >= MIN_ARTICLE_CHARS:
                sources.append({"id": f"{lang}:{real}", "sprache": lang, "titel": real, "text": text,
                                "url": f"https://{lang}.wikipedia.org/wiki/{real.replace(' ', '_')}"})
    return sources


def word_budget(spec: VideoSpec) -> int:
    seconds = max(8.0, (spec.target_seconds - 18) / max(1, spec.count))
    return max(22, min(60, int(seconds * 2.1) - 6))


def _digits(text: str) -> set[str]:
    return {d.replace(".", "").replace(",", "") for d in re.findall(r"\d[\d.,]*", text)}


def _numbers_near(text: str, numbers: set[str], window: int = 600) -> bool:
    """Stehen alle Zahlen nah beieinander (sonst wäre es ein Zufallstreffer in einem langen Text)?"""
    occ = [(m.start(), m.group().replace(".", "").replace(",", "")) for m in re.finditer(r"\d[\d.,]*", text)]
    for pos, num in occ:
        if num in numbers and numbers <= {n for p, n in occ if abs(p - pos) <= window}:
            return True
    return False


OTHER_LANGS = ("en", "de", "fr", "es", "it", "nl", "pt", "pl")


def _langlinks(home: dict) -> list[tuple[str, str]]:
    lang, title = home["id"].split(":", 1)
    try:
        data = net.get_json(f"https://{lang}.wikipedia.org/w/api.php",
                            params={"action": "query", "prop": "langlinks", "titles": title, "lllimit": 500,
                                    "redirects": 1, "format": "json", "formatversion": 2},
                            cache_hours=24 * 7, retries=2, max_wait=20)
    except net.FetchError:
        return []
    pages = data.get("query", {}).get("pages", [])
    links = {l.get("lang"): l.get("title") for l in (pages[0].get("langlinks", []) if pages else [])}
    return [(code, links[code]) for code in OTHER_LANGS if code != lang and links.get(code)]


def _study_abstracts(home: dict, numbers: set[str]) -> str | None:
    """Originalstudien aus den Einzelnachweisen (DOI/PubMed) über Europe PMC: nennt die Zusammenfassung die Zahlen?
    Jahreszahlen gelten auch über das Erscheinungsjahr der Studie als bestätigt."""
    from urllib.parse import unquote

    lang, title = home["id"].split(":", 1)
    try:
        data = net.get_json(f"https://{lang}.wikipedia.org/w/api.php",
                            params={"action": "query", "prop": "extlinks", "titles": title, "ellimit": 500,
                                    "redirects": 1, "format": "json", "formatversion": 2},
                            cache_hours=24 * 7, retries=2, max_wait=20)
    except net.FetchError:
        return None
    urls = [unquote(l.get("url", "")) for p in data.get("query", {}).get("pages", []) for l in p.get("extlinks", [])]
    dois = sorted({m.group(1).rstrip(".") for u in urls for m in [re.search(r"doi\.org/(10\.\d{4,9}/[^?#\s\"]+)", u)] if m})
    pmids = sorted({m.group(1) for u in urls for m in [re.search(r"(?:pubmed/|pubmed\.ncbi\.nlm\.nih\.gov/)(\d+)", u)] if m})
    terms = [f'DOI:"{d}"' for d in dois[:25]] + [f"EXT_ID:{p}" for p in pmids[:15]]
    if not terms:
        return None
    try:
        found = net.get_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                             params={"query": " OR ".join(terms), "resultType": "core", "format": "json", "pageSize": 50},
                             cache_hours=24 * 7, retries=2, max_wait=20)
    except net.FetchError:
        return None
    for paper in found.get("resultList", {}).get("result", []):
        abstract = paper.get("abstractText") or ""
        years = {n for n in numbers if re.fullmatch(r"1[5-9]\d\d|20\d\d", n) and n == str(paper.get("pubYear"))}
        rest = numbers - years
        if rest and _numbers_near(abstract, rest, window=800):
            return f"Studie: {(paper.get('title') or '')[:80]} ({paper.get('pubYear')})"
    return None


def confirm_numbers(numbers: set[str], home: dict, sources: list[dict]) -> str | None:
    """Zweite Quelle für die Zahlen eines Belegs: geladene Artikel, andere Sprachfassungen desselben Artikels,
    dann die Webseiten aus seinen Einzelnachweisen. Gibt die bestätigende Quelle zurück oder None."""
    for s in sources:
        if s is not home and _numbers_near(s["text"], numbers):
            return s["titel"]
    from . import config

    if not config.CHECK_WEB:                    # ohne Netzabgleich (Tests, CUDI_CHECK_WEB=0): nur geladene Artikel
        return None
    loaded = {s["id"] for s in sources}
    for code, title in _langlinks(home)[:5]:
        if f"{code}:{title}" in loaded:
            continue
        try:
            text, _ = article_text(code, title, limit=200_000)
        except net.FetchError:
            continue
        if _numbers_near(text, numbers):
            return f"Wikipedia ({code}): {title}"
    study = _study_abstracts(home, numbers)
    if study:
        return study
    from types import SimpleNamespace

    from .verify.checkers import ExternalSourcesChecker as Web

    lang, title = home["id"].split(":", 1)
    item = SimpleNamespace(wiki_titles={lang: title})
    for url in Web.links(item)[:Web.MAX_PAGES]:
        try:
            text = Web.page_text(url)
        except Exception:                       # Webseiten sind beliebig kaputt – nur Bestätigung, nie Pflicht
            continue
        if _numbers_near(text, numbers, window=800):
            from urllib.parse import urlparse
            return f"Webseite: {urlparse(url).netloc}"
    return None


_WORDS: dict = {}


def source_words(sources: list[dict], beleg: str) -> frozenset:
    """Alle Wörter der Quellen (klein) – Bausteine für Zusammensetzungen wie „Haihaut“."""
    key = tuple(s["id"] for s in sources)
    if key not in _WORDS:
        _WORDS.clear()
        _WORDS[key] = frozenset(re.findall(r"[a-zäöüß]{3,}", " ".join(s["text"] for s in sources).lower()))
    return _WORDS[key] | frozenset(re.findall(r"[a-zäöüß]{3,}", beleg.lower()))


def check_fact(fact: dict, sources: list[dict], langs: list[str], budget: int,
               aspects: list[str] | None = None) -> tuple[str | None, str]:
    """(Grund der Ablehnung oder None, Prüfstatus). Status „bestätigt“ = Zahlen auch in einer zweiten Quelle."""
    from .narrate import RANK_CLAIM, unknown_words
    from .script import NOT_NEUTRAL
    from .textcheck import invented_people

    if not isinstance(fact, dict):
        return "kein Fakt", ""
    beleg = str(fact.get("beleg") or "").strip()
    home = next((s for s in sources if s["id"] == fact.get("quelle")), None)
    home = home or next((s for s in sources if _norm(beleg) and _norm(beleg) in _norm(s["text"])), None)
    if len(beleg) < 25 or not home or _norm(beleg) not in _norm(home["text"]):
        return "Beleg steht nicht wörtlich in der Quelle", ""
    extra = [str(b).strip() for b in (fact.get("belege") or []) if str(b).strip()][:3] \
        if isinstance(fact.get("belege"), list) else []
    every = _norm(" ".join(s["text"] for s in sources))
    if any(_norm(b) not in every for b in extra):
        return "weiterer Beleg steht nicht wörtlich in der Quelle", ""
    if not themen.matches_aspect(str(fact.get("aspekt") or ""), aspects or []):
        return "passt nicht zum Themenkern (kein Aspekt aus „aspekte“)", ""
    beleg_all = " ".join([beleg, *extra])
    for lang in langs:
        text = str(fact.get(f"text_{lang}") or "").strip()
        title = str(fact.get(f"titel_{lang}") or "").strip()
        short = str(fact.get(f"kurz_{lang}") or "").strip()
        if not text or not title:
            return f"Text oder Titel ({lang}) fehlt", ""
        said = f"{title} {short} {text}"
        # werttreu und auch ausgeschrieben („zwei“ = „2“); zusammengesetzte Zahlwörter („zweihundert“) nur wörtlich
        backed = textcheck.numbers(beleg_all, "de") | textcheck.numbers(beleg_all, "en")
        compound = {w for w in re.findall(r"[a-zäöüß]+", said.lower()) if COMPOUND_NUMBER.search(w) and w not in textcheck.NUMBER_WORDS["de"]}
        if not textcheck.numbers(said, lang) <= backed or not compound <= set(re.findall(r"[a-zäöüß]+", beleg_all.lower())):
            return f"Zahl ohne Beleg ({lang})", ""
        if NOT_NEUTRAL.search(said) or RANK_CLAIM.search(said):
            return "Wertung oder Rang-Aussage", ""
        if len(text.split()) > budget * 1.4 + 8 or len(title) > 60 or len(short) > 90:
            return f"zu lang ({lang})", ""
        if len(text.split()) < budget * 0.6:
            return f"zu kurz ({lang}) – erkläre mehr als den nackten Fakt", ""
        unknown = invented_people(text, home["text"]) or unknown_words(
            text, {"sprache": lang, "beleg": beleg_all, "quelle": " ".join(s["text"] for s in sources)})
        words = source_words(sources, beleg_all)
        unknown = [w for w in unknown if not textcheck.everyday_word(w, lang, words)]
        if unknown:
            return "nicht belegt: " + ", ".join(unknown[:3]), ""
    fact["_aha"] = checked_aha(fact, langs, beleg_all, sources, home)
    numbers = {d for d in _digits(beleg_all) if len(d) >= 2}
    if numbers:
        second = confirm_numbers(numbers, home, sources)
        if not second:
            return "Zahlen nur in einer Quelle – nicht abgeglichen", ""
        fact["_zweitquelle"] = second
        return None, "bestätigt"
    return None, "eine Fachquelle (Wortlaut geprüft)"


AHA_MAX_WORDS = 22


def checked_aha(fact: dict, langs: list[str], beleg_all: str, sources: list[dict], home: dict) -> dict:
    """„aha_<sprache>“ (ein Satz: Was weiß man jetzt Neues?) mit denselben Prüfungen wie der Sprechertext: keine Zahl
    ohne Beleg, keine erfundenen Namen/Wörter, keine Wertung. Ein schlechter Aha-Satz lehnt den Fakt nicht ab – er wird
    nur nicht als „Heute gelernt“ gesprochen."""
    from .narrate import RANK_CLAIM, unknown_words
    from .script import NOT_NEUTRAL
    from .textcheck import invented_people

    out = {}
    for lang in langs:
        aha = re.sub(r"\s+", " ", str(fact.get(f"aha_{lang}") or "")).strip()
        if not 3 <= len(aha.split()) <= AHA_MAX_WORDS:
            continue
        own = " ".join(str(fact.get(f"{k}_{lang}") or "") for k in ("titel", "kurz", "text"))
        backed = textcheck.numbers(f"{beleg_all} {own}", "de") | textcheck.numbers(f"{beleg_all} {own}", "en")
        if not textcheck.numbers(aha, lang) <= backed or NOT_NEUTRAL.search(aha) or RANK_CLAIM.search(aha):
            continue
        compound = {w for w in re.findall(r"[a-zäöüß]+", aha.lower()) if COMPOUND_NUMBER.search(w)
                    and w not in textcheck.NUMBER_WORDS["de"]}
        if not compound <= set(re.findall(r"[a-zäöüß]+", f"{beleg_all} {own}".lower())):
            continue
        # Namen und Hauptwörter müssen im Fakt selbst (Beleg + Sprechertext) stehen, nicht nur irgendwo in den Quellen
        unknown = invented_people(aha, f"{beleg_all} {own}") or unknown_words(
            aha, {"sprache": lang, "beleg": f"{beleg_all} {own}", "quelle": ""})
        words = source_words(sources, beleg_all)
        if [w for w in unknown if not textcheck.everyday_word(w, lang, words)]:
            continue
        out[lang] = aha
    return out


def _facts_of(answer) -> list[dict]:
    facts = answer.get("fakten") if isinstance(answer, dict) else None
    return [f for f in facts if isinstance(f, dict)] if isinstance(facts, list) else []


def _check_all(facts: list[dict], sources: list[dict], langs: list[str], budget: int, aspects=None):
    """(bestandene Fakten mit Prüfstatus, abgelehnte Fakten mit Grund) – nach Rang sortiert."""
    kept, rejected = [], []
    for fact in sorted(facts, key=lambda f: int(f.get("rang") or 99)):
        reason, status = check_fact(fact, sources, langs, budget, aspects)
        if reason:
            rejected.append((fact, reason))
        else:
            kept.append((fact, status))
    return kept, rejected


def research_facts(spec: VideoSpec, langs: list[str]) -> Research:
    """Quellen laden, Claude die Fakten schreiben lassen, jeden Fakt prüfen. Wirft handoff.WritingNeeded, solange
    Claudes Antwort fehlt (der Auftrag läuft danach mit --weiter weiter)."""
    sources = gather_sources(spec)
    if not sources:
        raise ValueError("Zu diesem Thema fanden sich keine Fachartikel. Bitte das Thema etwas anders formulieren.")
    budget = word_budget(spec)
    data = {"thema": spec.title.get("de") or next(iter(spec.title.values())),
            "anzahl": spec.count + EXTRA_FACTS, "kriterium": spec.facts.get("criterion", {}),
            "sprachen": langs, "woerter": budget, **themen.focus(spec, langs[0]),
            "quellen": [{k: s[k] for k in ("id", "sprache", "titel", "text")} for s in sources]}
    warnings: list[str] = []
    aspects = data["aspekte"]
    kept, rejected = _check_all(_facts_of(handoff.request("fakten", INSTRUCTIONS, data)), sources, langs, budget, aspects)
    if not kept and not rejected:
        raise handoff.ModelUnavailable("Es kamen keine Fakten zurück (Sprachmodell nicht erreichbar oder Antwort unbrauchbar). "
                                       "Erfunden wird nichts – bitte später erneut versuchen.")
    for task, extra in (("fakten_korrektur", ""), ("fakten_korrektur2", INSTRUCTIONS_FIX2)):
        if len(kept) >= spec.count or not rejected:
            break
        # mit Begründung zurück an Claude – die zweite Runde nur, wenn es danach immer noch zu wenige sind
        retry = {**data, "regeln": INSTRUCTIONS, "abgelehnt": [{"fakt": f, "grund": r} for f, r in rejected]}
        fixed, still = _check_all(_facts_of(handoff.request(task, INSTRUCTIONS_FIX + extra, retry)),
                                  sources, langs, budget, aspects)
        taken = {int(f.get("rang") or 99) for f, _ in kept}
        kept += [(f, st) for f, st in fixed if int(f.get("rang") or 99) not in taken]
        fixed_ranks = {int(f.get("rang") or 99) for f, _ in fixed}
        rejected = [(f, r) for f, r in rejected if int(f.get("rang") or 99) not in fixed_ranks] + \
            [(f, r) for f, r in still if int(f.get("rang") or 99) not in taken]
    for fact, reason in rejected:
        name = str(fact.get(f"titel_{langs[0]}") or fact.get("beleg", ""))[:60]
        warnings.append(f"Fakt „{name}“ verworfen: {reason}.")
    kept = sorted(kept, key=lambda fs: int(fs[0].get("rang") or 99))[:spec.count]
    if len(kept) < min(3, spec.count):
        why = "; ".join(sorted({r for _, r in rejected}))[:300]
        raise ValueError(f"Nur {len(kept)} Fakten bestanden die Prüfung – zu wenig für ein ehrliches Ranking"
                         + (f" (Gründe: {why})." if why else "."))
    if len(kept) < spec.count:
        warnings.append(f"Nur {len(kept)} von {spec.count} Fakten geprüft – Video zeigt die Top {len(kept)}.")
        spec.shrink_to(len(kept))
    items = []
    n = len(kept)
    for rank, (fact, status) in enumerate(kept, start=1):
        home = next((s for s in sources if s["id"] == fact.get("quelle")), None) or next(
            s for s in sources if _norm(fact["beleg"]) in _norm(s["text"]))
        items.append(RankItem(
            qid=f"F{rank}", value=float(n + 1 - rank), unit="Q199", rank=rank,
            labels={lang: str(fact[f"titel_{lang}"]).strip() for lang in langs},
            descriptions={lang: str(fact.get(f"kurz_{lang}") or "").strip() for lang in langs},
            summary={lang: str(fact[f"text_{lang}"]).strip() for lang in langs},
            fact={"beleg": fact["beleg"].strip(), "quelle": home["titel"], "url": home["url"],
                  "zweitquelle": str(fact.get("_zweitquelle") or ""),
                  "suche": (searches(fact) or [""])[0], "suchen": searches(fact),
                  "motiv": str(fact.get("motiv") or "").strip()[:60], "aha": dict(fact.get("_aha") or {}),
                  "aspekt": str(fact.get("aspekt") or "")[:60],
                  "belege": [str(b).strip() for b in fact.get("belege") or [] if str(b).strip()][:3]
                  if isinstance(fact.get("belege"), list) else []},
            verification={"status": status, "sources": [home["titel"]], "evidence": [], "outliers": []},
        ))
    research = Research(spec_id=spec.id, fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        items=items, warnings=warnings)
    _visuals(research)
    return research


def searches(fact: dict) -> list[str]:
    """Suchbegriffe des Fakts: „suche“ als Liste (neu) oder als einzelner Text (alte Antworten)."""
    raw = fact.get("suchen") or fact.get("suche")
    raw = raw if isinstance(raw, list) else [raw]
    return [str(q).strip()[:60] for q in raw if q and str(q).strip()][:3]


def _stock_clips(queries: list[str], used: set, match, motif: str = "", limit: int = 2) -> list[dict]:
    from .story.visuals import pexels, pixabay

    clips: list[dict] = []
    for query in queries:
        for _ in range(4):                       # bis zu 2 Clips, fast schwarze werden übersprungen
            try:
                found = pexels(query, used, match, motif) or pixabay(query, used, match, motif)
            except net.FetchError:
                found = None
            if not found:
                break
            if media.too_dark(found.path):
                continue
            clips.append({"path": found.path, "credit": found.credit, "duration": 0, "kind": "video",
                          "score": found.score})
            if len(clips) == limit:
                return clips
        if clips:
            break
    return clips


def _first_photo(finders, queries: list[str], used: set, match, motif: str = ""):
    for query in queries:
        for find in finders:
            try:
                photo = find(query, used, match, motif)
            except net.FetchError:
                photo = None
            if photo:
                return photo
    return None


def find_visuals(fact: dict, fallback: str, used: set) -> dict:
    """Bild/Clip, das den Fakt zeigt. Reihenfolge: passender Clip -> passendes Foto (Pexels/Pixabay) -> Commons-Bild
    zum Motiv -> allgemeiner Themenclip/-foto als „Stimmungsbild“.
    Prüfung: Mit Bildprüfung (bildcheck, CLIP) muss das Motiv im Bild zu sehen sein; der Tag-Abgleich ist dann nur ein
    lockerer Vorfilter (Hauptwort). Ohne Modell: strenger Tag-Abgleich (ALLE Kernwörter in Tags/Adresse/Titel).
    Ergebnis: {clips, photo, passt, quelle, motiv, wert}; ohne „motiv“ (alte Antworten) wird nur nach „suche“
    gesucht (passt = None, nicht geprüft)."""
    from .story.visuals import commons_photo, pexels_photo, pixabay_photo

    motif = str(fact.get("motiv") or "").strip()
    queries = searches(fact) or ([fallback] if fallback else [])
    out = {"clips": [], "photo": None, "passt": None, "quelle": "ungeprüft", "motiv": motif, "wert": None}

    def score(clips, photo):
        values = [c.get("score") for c in clips] + [photo.score if photo else None]
        values = [v for v in values if v is not None]
        return max(values) if values else None

    if motif:
        seeing = bildcheck.available()
        match = lambda text: media.motif_matches(motif, text, loose=seeing)          # noqa: E731
        check = motif if seeing else ""
        tries = list(dict.fromkeys([motif, *queries]))
        clips = _stock_clips(tries, used, match, check)
        clip_score = score(clips, None)
        if clips and (clip_score is None or clip_score >= WEAK_CLIP):
            return {**out, "clips": clips, "passt": True, "quelle": "Clip", "wert": clip_score}
        photo = _first_photo((pexels_photo, pixabay_photo), tries, used, match, check)
        if clips and not (photo and (photo.score or 0) > (clip_score or 0)):     # schwacher Clip schlägt kein schwaches Foto
            return {**out, "clips": clips, "passt": True, "quelle": "Clip", "wert": clip_score}
        if photo:
            return {**out, "photo": photo, "passt": True, "quelle": "Foto", "wert": score([], photo)}
        try:
            photo = commons_photo(motif, used, match, check)
        except net.FetchError:
            photo = None
        if photo:
            return {**out, "photo": photo, "passt": True, "quelle": "Wikimedia Commons", "wert": score([], photo)}
    # letzte Stufe: Stimmungsbild zum Thema – wenigstens das Hauptthema (erstes Kernwort, z. B. „shark“) muss zu
    # sehen bzw. in der Beschreibung zu lesen sein
    subject = (media.motif_words(motif) or [""])[0]
    mood = (lambda text: media.motif_matches(subject, text)) if subject else None          # noqa: E731
    check = subject if subject and bildcheck.available() else ""
    clips = _stock_clips(queries, used, mood, check)
    photo = None if clips else _first_photo((pexels_photo,), queries, used, mood, check)
    return {**out, "clips": clips, "photo": photo, "passt": False if motif else None, "wert": score(clips, photo),
            "quelle": ("Stimmungsbild" if motif else "ungeprüft") if clips or photo else "kein Bild"}


def _visuals(research: Research) -> None:
    """Passende Stockclips (Pexels/Pixabay) bzw. Fotos je Fakt – das Bild muss den Fakt zeigen (Motiv), erst zuletzt
    gibt es ein Stimmungsbild (im Prüfbericht vermerkt)."""
    used: set = set()
    for item in research.items:
        found = find_visuals(item.fact, item.labels.get("en") or "", used)
        item.clips = found["clips"]
        if found["photo"] and not found["clips"]:
            item.image_path, item.image_credit = found["photo"].path, found["photo"].credit
        item.fact["bild"] = {"motiv": found["motiv"], "passt": found["passt"], "quelle": found["quelle"],
                             "wert": found["wert"]}
