"""Gemeinsame Prüfungen für Texte von Claude (Ranking-Erzählung, Story-Lektorat): Zahlen werttreu vergleichen,
erfundene Personen erkennen, Wörter nur durch ganze Wörter belegen."""

from __future__ import annotations

import re

# Zahlwörter je Sprache („one“/„ein“ fehlen absichtlich: zu oft Pronomen oder Artikel)
NUMBER_WORDS = {
    "en": dict(two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10, eleven=11, twelve=12,
               thirteen=13, fourteen=14, fifteen=15, sixteen=16, seventeen=17, eighteen=18, nineteen=19, twenty=20,
               thirty=30, forty=40, fifty=50, sixty=60, seventy=70, eighty=80, ninety=90, hundred=100, thousand=1000,
               dozen=12, million=1_000_000),
    "de": {"zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
           "elf": 11, "zwölf": 12, "dreizehn": 13, "vierzehn": 14, "fünfzehn": 15, "sechzehn": 16, "siebzehn": 17,
           "achtzehn": 18, "neunzehn": 19, "zwanzig": 20, "dreißig": 30, "vierzig": 40, "fünfzig": 50, "sechzig": 60,
           "siebzig": 70, "achtzig": 80, "neunzig": 90, "hundert": 100, "tausend": 1000, "dutzend": 12,
           "million": 1_000_000, "millionen": 1_000_000},
}


def numbers(text: str, lang: str = "en") -> set[str]:
    """Alle Zahlen eines Textes werttreu: „1.5“ ≠ „15“, „two“ = „2“ = „zwei“, Tausender je Sprache („1,500“ en)."""
    thousands, decimal = (".", ",") if lang == "de" else (",", ".")
    out = set()
    for tok in re.findall(r"\d+(?:[.,]\d+)*", text):
        if re.fullmatch(rf"\d{{1,3}}(?:{re.escape(thousands)}\d{{3}})+", tok):
            tok = tok.replace(thousands, "")
        tok = tok.replace(thousands, "").replace(decimal, ".") if tok.count(decimal) <= 1 else tok.replace(decimal, "")
        try:
            value = float(tok)
        except ValueError:
            continue
        out.add(f"{value:g}")
    words = NUMBER_WORDS.get(lang, {})
    out |= {f"{float(words[w]):g}" for w in re.findall(r"[a-zäöüß]+", text.lower()) if w in words}
    return out


def digits(text: str) -> set[str]:          # bleibt für Titel/Einstieg ohne Sprachangabe
    return numbers(text, "en") | numbers(text, "de")


# Häufige Vornamen (en/de): tauchen sie im Lektorat auf, aber nicht im Original, ist es eine erfundene Person –
# auch in übersetzten Fassungen, wo Großschreibung (deutsche Hauptwörter) nichts verrät.
FIRST_NAMES = set("""james john robert michael william david richard joseph thomas charles chris christopher daniel
    matthew anthony mark donald steven paul andrew joshua kenneth kevin brian george timothy ronald edward jason jeff
    jeffrey ryan jacob gary nicholas eric jonathan stephen larry justin scott brandon benjamin samuel gregory frank
    alexander raymond patrick jack dennis jerry tyler aaron jose adam henry nathan douglas zachary peter kyle walter
    ethan jeremy harold keith christian roger noah gerald carl terry sean austin arthur lawrence jesse dylan bryan joe
    jordan billy bruce albert willie gabriel logan alan juan wayne roy ralph randy eugene vincent russell elijah louis
    bobby philip johnny mary patricia jennifer linda elizabeth barbara susan jessica sarah karen lisa nancy betty
    margaret sandra ashley kimberly emily donna michelle carol amanda dorothy melissa deborah stephanie rebecca sharon
    laura cynthia kathleen amy angela shirley anna brenda pamela emma nicole helen samantha katherine christine debra
    rachel carolyn janet catherine maria heather diane ruth julie olivia joyce virginia victoria kelly lauren christina
    joan evelyn judith megan andrea cheryl hannah jacqueline martha gloria teresa ann sara madison frances kathryn janice
    jean abigail alice judy sophia grace denise amber doris marilyn danielle beverly isabella theresa diana natalie
    brittany charlotte marie kayla alexis lori mike tom tim jim bob ben sam max tony nick alex kate katie jen jenny meg
    lukas leon finn jonas elias luis felix maximilian paul ben luca noah julian tim niklas jan tobias florian stefan
    andreas markus martin thorsten jürgen klaus uwe sabine petra monika ursula claudia andrea anja katrin julia lena
    leonie mia lea laura lisa sophie hannah marie emilia johanna nina jana""".split())


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zäöüß0-9]+", text.lower()))


def known(word: str, tokens: set[str]) -> bool:
    """Wort im Original belegt? Ganze Wörter, bei längeren Wörtern auch gebeugt („Jessicas“) – nie als Teilwort
    („Mark“ ist durch „market“ nicht belegt)."""
    low = word.lower().strip("'’-")
    low = re.sub(r"['’]s$", "", low)
    if low in tokens:
        return True
    return len(low) >= 5 and any(len(t) >= 5 and (t.startswith(low[:5]) and low.startswith(t[:5])) and
                                 abs(len(t) - len(low)) <= 2 for t in tokens)


def invented_people(text: str, source: str) -> list[str]:
    """Vornamen im neuen Text, die im Original nicht vorkommen (sprachunabhängig)."""
    known_words = tokens(source)
    return [w for w in re.findall(r"[A-ZÄÖÜ][a-zäöüß]+", text) if w.lower() in FIRST_NAMES and not known(w, known_words)]


# --------------------------------------------------------------------------- allgemeine Wörter
# Häufigste 50 000 Wörter je Sprache (FrequencyWords von Hermit Dave, aus OpenSubtitles, CC BY-SA 4.0).
# Sie belegen nichts – sie erlauben nur Alltagswörter („Café“, „Gehirn“) in erzählenden Sätzen, deren Aussage
# selbst am wörtlichen Beleg hängt. Zahlen und Personennamen prüfen eigene, strenge Regeln.
# `everyday_word`: nur deutsche Alltagswörter, die es so nicht auch im Englischen gibt – Eigennamen („Harvard“,
# „Miller“, „Berlin“) sind in beiden Sprachen gleich und bleiben deshalb belegpflichtig; englische Texte bekommen
# keine Ausnahme (Großschreibung mitten im Satz heißt dort fast immer Name).
_COMMON: dict[str, dict] = {}


def common_words(lang: str) -> dict[str, int]:
    """Häufige Wörter einer Sprache mit Rang (0 = häufigstes)."""
    if lang not in _COMMON:
        import gzip
        from pathlib import Path
        path = Path(__file__).with_name("wortlisten") / f"words_{lang}.txt.gz"
        try:
            words = gzip.decompress(path.read_bytes()).decode("utf-8").split()
        except OSError:
            words = []
        ranks: dict[str, int] = {}
        for i, w in enumerate(words):
            if w not in FIRST_NAMES:
                ranks.setdefault(w, i)
        _COMMON[lang] = ranks
    return _COMMON[lang]


GERMAN_ENDINGS = ("en", "es", "em", "n", "s", "e")       # ohne „-er“: sonst wird „Müller“ zu „Müll“


COMMON_RANK, PART_RANK = 30000, 30000     # Einzelwort / Teil eines zusammengesetzten Worts: so häufig muss es sein
# Deutsche Eigennamen, die die Häufigkeitslisten nicht von Wörtern unterscheiden: häufigste Nachnamen, Städte, Länder
GERMAN_NAMES = set("""müller schmidt schneider fischer weber meyer meier wagner becker schulz hoffmann schäfer koch bauer
    richter klein wolf schröder neumann schwarz zimmermann braun krüger hofmann hartmann lange schmitt werner schmitz
    krause meier lehmann schmid schulze maier köhler herrmann könig walter mayer huber kaiser fuchs peters lang scholz
    möller weiß jung hahn schubert vogel friedrich keller günther frank berger winkler roth beck lorenz baumann franke
    albrecht schuster simon ludwig böhm winter kraus martin schumacher krämer vogt stein jäger otto sommer groß seidel
    heinrich brandt haas schreiber graf dietrich ziegler kuhn kühn pohl engel horn busch bergmann thomas voigt sauer arnold
    berlin hamburg münchen köln frankfurt stuttgart düsseldorf leipzig dortmund essen bremen dresden hannover nürnberg
    duisburg bochum wuppertal bielefeld bonn münster mannheim karlsruhe augsburg wiesbaden aachen kiel lübeck rostock
    erfurt mainz kassel freiburg heidelberg potsdam wien graz linz salzburg innsbruck zürich genf basel bern luzern
    deutschland österreich schweiz frankreich italien spanien england amerika russland china japan indien europa afrika
    asien bayern sachsen hessen preußen bauhaus""".split())
NAME_ENDINGS = ("mann", "berg", "burg", "dorf", "stein", "feld", "hausen", "ingen", "heim", "bach", "stadt", "furt",
                "thal")
TAIL_RANK = 50000                       # zweiter Teil einer Zusammensetzung („-folgern“) darf seltener sein


def _german_everyday(part: str, max_rank: int = COMMON_RANK) -> bool:
    """Deutsches Alltagswort: häufig im Deutschen und deutlich seltener im Englischen. Eigennamen („Harvard“,
    „London“) sind in beiden Listen ähnlich häufig, seltene Namen („Zürich“) nicht häufig genug – beide bleiben
    belegpflichtig."""
    de, en = common_words("de"), common_words("en")
    rank = de.get(part)
    if rank is None or rank >= max_rank:
        return False
    return part not in en or en[part] > 3 * rank + 1000


SEPARABLE = ("zurück", "durch", "unter", "nach", "über", "auf", "aus", "ein", "mit", "vor", "weg", "zu", "ab", "an",
             "um", "los")                            # „Zubeißen“, „Aufwachen“
PREFIXES = ("urur", "ur", "un")                      # „Ururgroßeltern“, „Unruhe“


def _german_known(part: str, extra: frozenset = frozenset(), depth: int = 0) -> bool:
    """Alltagswort – auch gebeugt („Alltags“), zusammengesetzt („Faustregel“, „Eismeer“, „Schleifpapier“), mit
    trennbarer Vorsilbe („Zubeißen“) oder aus Wörtern der Quelle gebildet („Haihaut“, wenn „Hai“ in der Quelle steht)."""
    if part in GERMAN_NAMES:
        return False
    en, de = common_words("en"), common_words("de")
    if part in en and not (part in de and en[part] > 3 * de[part] + 1000):
        return False                                   # internationales Wort/Name („London“, „Paris“, „Trick“)
    if _german_everyday(part):
        return True

    def forms(x: str) -> list[str]:
        out = [x] + [x[: -len(e)] for e in GERMAN_ENDINGS if x.endswith(e) and len(x) - len(e) >= 3]
        if x.endswith(("ung", "ungen")):                # „Erkennung“ → „erkennen“
            out.append(x[: x.rindex("ung")] + "en")
        return out

    def known(x: str, rank: int) -> bool:
        return any(f in extra or _german_everyday(f, rank) for f in forms(x))

    if any(_german_everyday(f) for f in forms(part)[1:]):
        return True
    if part.endswith(NAME_ENDINGS):                    # „Hoffmann“, „Heidelberg“: als Zusammensetzung belegpflichtig
        return False
    if depth < 2:
        for pre in PREFIXES + SEPARABLE:
            rest = part[len(pre):]
            if part.startswith(pre) and len(rest) >= 4 and (known(rest, TAIL_RANK) or _german_known(rest, extra, depth + 1)):
                return True
    for i in range(3, len(part) - 3):                  # zwei Teile: vorne ≥ 3, hinten ≥ 4 Buchstaben (Fugen-s erlaubt)
        head, tail = part[:i], part[i:]
        heads = [head] + ([head[:-1]] if head.endswith("s") and len(head) > 4 else []) + [head + "en", head + "e"]
        if any(h in extra or _german_everyday(h, PART_RANK) for h in heads) and known(tail, TAIL_RANK):
            return True
    return False


def everyday_word(word: str, lang: str, extra=None) -> bool:
    """`extra`: Wörter der Quellen (klein geschrieben) – dürfen Teil einer Zusammensetzung sein."""
    parts = [p for p in re.split(r"[-'’]", word.lower()) if p]
    extra = frozenset(w for w in (extra or ()) if len(w) >= 3)
    return lang == "de" and bool(parts) and all(_german_known(p, extra) for p in parts)
