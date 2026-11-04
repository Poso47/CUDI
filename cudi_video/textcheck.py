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
