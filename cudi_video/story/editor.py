"""Lektorat: aus einem Reddit-Post wird ein Story-Skelett (Szenen, Teile, Bildideen, Stimme).

Regeln wie bei einem Profi-Sprecher: Meta-Kram raus (Edits, TL;DR, „sorry for formatting“),
Abkürzungen ausschreiben, auf Wunsch Kraftausdrücke entschärfen, in Szenen und – wenn nötig –
Teile mit Cliffhanger gliedern. Inhaltlich wird nichts hinzugefügt; jede Änderung landet in den Notizen.
"""

from __future__ import annotations

import logging
import re

from .. import config, handoff, llm
from .moods import MOODS, WORDS_PER_SECOND, detect_mood, language_of, narrator_gender, rate_factor, voice_for
from .sources import LENGTHS, Post, rights_note
from .visuals import FIGURES

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- Bereinigung

CUT_SECTION = re.compile(r"^\s*(?:\*\*|__)?\s*(edit\s*\d*|e\.?t\.?a|tl\s*;?\s*dr|update\s*\d*)\b\s*[:\-–.]", re.I)
META_LINE = re.compile(
    r"(throw\s*away|sorry for (the )?(formatting|format|grammar|spelling|length)|on mobile|english (is|isn'?t) "
    r"(not )?my first language|long post ahead|first time posting|trigger warning|\btw:|\bcw:|"
    r"wegwerf|sorry für (die )?(formatierung|rechtschreibung|länge)|(vom|am) handy geschrieben|"
    r"wird (etwas|ein bisschen) länger|mein erster post)", re.I)


def clean_text(text: str) -> tuple[str, list[str]]:
    """Markdown, Links und Meta-Absätze entfernen. Gibt (Text, Notizen) zurück."""
    notes: list[str] = []
    text = text.replace("\r\n", "\n").replace("​", "").replace("&nbsp;", " ").replace("&amp;", "&")
    lines, removed_meta, cut = [], 0, None
    for line in text.split("\n"):
        if CUT_SECTION.match(line):
            body = " ".join(lines).split()
            if len(body) >= 60:                      # nur am Ende abschneiden, nie die eigentliche Story
                cut = CUT_SECTION.match(line).group(1).strip().upper().replace(" ", "")
                break
        if META_LINE.search(line) and len(line.split()) < 25:
            removed_meta += 1
            continue
        lines.append(line)
    if cut:
        notes.append(f"Nachträge ab „{cut}“ entfernt (Edit/Update/TL;DR gehören nicht zur Erzählung).")
    if removed_meta:
        notes.append(f"{removed_meta} Meta-Zeile(n) entfernt (z. B. „sorry for formatting“).")
    text = "\n".join(lines)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", text)          # [Text](Link) -> Text
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"(\*\*|__|~~|\^)", "", text)
    text = re.sub(r"(?<!\w)[*_](?=\S)(.+?)(?<=\S)[*_](?!\w)", r"\1", text)    # *kursiv*
    text = re.sub(r"^\s*(#+|>+|[-*•]\s)\s*", "", text, flags=re.M)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, notes


# --------------------------------------------------------------------------- Vorlesbar machen

ABBREVIATIONS = {
    "AITAH": "Am I the A-hole", "AITA": "Am I the A-hole", "WIBTA": "Would I be the A-hole",
    "TIFU": "Today I messed up", "NTA": "not the A-hole", "YTA": "you're the A-hole", "ESH": "everyone sucks here",
    "MIL": "mother-in-law", "FIL": "father-in-law", "SIL": "sister-in-law", "BIL": "brother-in-law",
    "BF": "boyfriend", "GF": "girlfriend", "SO": "partner", "DH": "husband", "DW": "wife", "LDR": "long-distance relationship",
    "IIRC": "if I remember correctly", "TBH": "to be honest", "IMO": "in my opinion", "IMHO": "in my opinion",
    "IDK": "I don't know", "NGL": "not gonna lie", "BTW": "by the way", "FYI": "for your information",
    "WTF": "what the heck", "OMG": "oh my god", "IRL": "in real life", "ASAP": "as soon as possible",
    "WFH": "working from home", "PTO": "time off", "ETA": "arrival time",
}
DROP_TOKENS = re.compile(r"\s*\b(lol|lmao|lmfao|rofl|smh|jk)\b", re.I)
SLANG = {r"\bu\b": "you", r"\bur\b": "your", r"\brn\b": "right now", r"\bb/c\b": "because", r"\bbc\b": "because",
         r"\bw/o\b": "without", r"\bw/\s?": "with ", r"\bppl\b": "people", r"\bthx\b": "thanks", r"\bpls\b": "please"}
# Kurzformen ohne Apostroph („im“, „didnt“) – die Stimme läse sonst „im“ wie das deutsche Wort
CONTRACTIONS = {
    "im": "I'm", "ive": "I've", "dont": "don't", "didnt": "didn't", "doesnt": "doesn't", "cant": "can't",
    "wont": "won't", "isnt": "isn't", "wasnt": "wasn't", "werent": "weren't", "arent": "aren't",
    "couldnt": "couldn't", "wouldnt": "wouldn't", "shouldnt": "shouldn't", "havent": "haven't", "hasnt": "hasn't",
    "hadnt": "hadn't", "youre": "you're", "theyre": "they're", "thats": "that's", "whats": "what's",
    "theres": "there's", "hes": "he's", "shes": "she's", "youve": "you've", "theyve": "they've",
}
AGE_TAG = re.compile(r"\s*[\(\[]\s*(?:(\d{1,2})\s*(?:[mfwdMFWD]|nb|NB|enby)?|(?:[mfwdMFWD]|nb|NB)\s*(\d{1,2}))\s*[\)\]]")
ABBREVIATIONS_DE = {
    "BIDA": "Bin ich das A-Loch", "WIBTA": "Wäre ich das A-Loch", "SchwiMu": "Schwiegermutter",
    "SchwiPa": "Schwiegerpapa", "SchwiVa": "Schwiegervater", "Ex-Freundin": "Ex-Freundin",
    "evtl.": "eventuell", "bzw.": "beziehungsweise", "z.B.": "zum Beispiel", "z. B.": "zum Beispiel",
    "usw.": "und so weiter", "ca.": "circa", "ggf.": "gegebenenfalls", "inkl.": "inklusive",
}
SOFTEN_DE = [
    (r"\barschl(o|ö)ch(er)?\b", r"A-L\1ch\2"), (r"\bschei(ß|ss)e\b", "Mist"), (r"\bschei(ß|ss)", "Mist-"),
    (r"\bfick(en|t)?\b", "verdammt"), (r"\bwichser\b", "Idiot"), (r"\bhurensohn\b", "Mistkerl"),
]

SOFTEN = [
    (r"\bmotherfuck(er|ers|ing)\b", r"mother-freak\1"), (r"\bfuck(ing|ed|er|ers|s)?\b", r"freak\1"),
    (r"\bbullshit\b", "nonsense"), (r"\bshit(ty)?\b", r"crap\1"), (r"\bbitch(es|y)?\b", r"jerk\1"),
    (r"\bassholes?\b", "A-hole"), (r"\bdick(s)?\b", r"jerk\1"), (r"\bbastards?\b", "jerk"),
    (r"\bpiss(ed)? off\b", r"tick\1 off"),
]

# Heikle Stellen andeuten statt aussprechen – die Handlung bleibt, nur die Wörter werden TikTok-tauglich.
# Ersetzungen sind so gewählt, dass der Satz grammatisch bleibt („we had sex“ -> „we got intimate“).
_HAVE = {"had": "got", "have": "get", "having": "getting", "has": "gets"}
_MOLEST = {"molest": "abuse", "molested": "abused", "molesting": "abusing", "molester": "abuser"}
SENSITIVE_EN = [
    (r"\bsexual (harassment|assault|abuse)\b", r"\1"), (r"\bsexually (harassed|assaulted|abused)\b", r"\1"),
    (r"\b(had|have|having|has) sex\b", lambda m: f"{_HAVE[m.group(1).lower()]} intimate"),
    (r"\bsexually\b", "intimately"), (r"\bsexual\b", "intimate"), (r"\bsex\b", "intimacy"),
    (r"\bporn\w*\b", "adult videos"), (r"\b(naked|nude)\b", "without clothes"), (r"\bhorny\b", "in the mood"),
    (r"\b(boobs?|breasts?)\b", "chest"), (r"\b(penis|vagina|genitals?)\b", "private parts"),
    (r"\bmasturbat\w*\b", "touching themselves"), (r"\borgasm\w*\b", "climax"), (r"\bblowjobs?\b", "something intimate"),
    (r"\brapist\b", "attacker"), (r"\braped\b", "assaulted"), (r"\braping\b", "assaulting"), (r"\brapes?\b", "assault"),
    (r"\b(molest|molested|molesting|molester)\b", lambda m: _MOLEST[m.group(1).lower()]),
    (r"\bcommit(?:ted|s)? suicide\b", "unalived themselves"), (r"\bsuicidal\b", "in a very dark place"),
    (r"\bsuicide\b", "unaliving"), (r"\b(kill|killed) (myself|himself|herself|themselves)\b",
                                    lambda m: f"{'unalived' if m.group(1).lower() == 'killed' else 'unalive'} {m.group(2)}"),
    (r"\bself[- ]harm\w*\b", "hurting themselves"),
]
_SEXUELL = {"sexuell": "intim", "sexuelle": "intime", "sexuellen": "intimen", "sexueller": "intimer", "sexuelles": "intimes"}
_SEX_VERB = {"haben": "intim werden", "hatten": "intim wurden", "hatte": "intim wurde", "gehabt": "intim geworden",
             "hat": "intim wird"}
_HATTEN = {"hatten": "wurden", "hatte": "wurde", "haben": "werden", "hat": "wird", "habt": "werdet"}
SENSITIVE_DE = [
    (r"\b(sexuelle[nmrs]?) (Belästigung|Übergriff\w*|Missbrauch\w*|Gewalt)\b", r"\2"),
    (r"\b(hatten|hatte|haben|hat|habt) Sex\b", lambda m: f"{_HATTEN[m.group(1)]} intim"),
    (r"\bSex (haben|hatten|hatte|gehabt|hat)\b", lambda m: _SEX_VERB[m.group(1)]),
    (r"\b(sexuell|sexuelle|sexuellen|sexueller|sexuelles)\b", lambda m: _SEXUELL[m.group(1).lower()]),
    (r"\bSex\b", "Intimität"), (r"\bPorno\w*\b", "Erwachsenenfilm"), (r"\bnackt\b", "unbekleidet"),
    (r"\bBrüste\b", "Oberkörper"), (r"\b(Penis|Vagina|Genitalien)\b", "Intimbereich"),
    (r"\bvergewaltigt\b", "angegriffen"), (r"\bvergewaltigen\b", "angreifen"), (r"\bVergewaltigung(en)?\b", "Übergriff"),
    (r"\b(Selbstmord|Suizid) begangen\b", "sich das Leben genommen"), (r"\b(Selbstmord|Suizid)\b", "Freitod"),
    (r"\bsuizidal\b", "an einem sehr dunklen Punkt"), (r"\britzen\b", "sich verletzen"),
]


def soften_sensitive(text: str, lang: str = "en") -> tuple[str, int]:
    """Heikle Wörter umschreiben (angedeutet statt ausgesprochen). Gibt (Text, Anzahl) zurück."""
    count = 0
    for pattern, repl in (SENSITIVE_DE if lang == "de" else SENSITIVE_EN):
        text, n = re.subn(pattern, repl, text, flags=0 if lang == "de" else re.I)
        count += n
    return text, count


def speakable(text: str, soften: bool = True, lang: str = "en") -> tuple[str, list[str]]:
    """Abkürzungen ausschreiben, Altersangaben glätten, optional Kraftausdrücke entschärfen."""
    notes: list[str] = []
    expanded = []
    for abbr, full in (ABBREVIATIONS_DE if lang == "de" else ABBREVIATIONS).items():
        if abbr == "SO":                         # nur „my SO“ – sonst ist „SO“ meist ein lautes „so“
            text, n = re.subn(r"\b(my|our|her|his)\s+SO\b", rf"\1 {full}", text, flags=re.I)
            if n:
                expanded.append(abbr)
            continue
        if abbr.endswith("."):
            pattern = rf"(?<!\w){re.escape(abbr)}"
        else:
            pattern = rf"\b{re.escape(abbr)}\b"
        if re.search(pattern, text):
            text = re.sub(pattern, full, text)
            expanded.append(abbr)
    if lang == "en":
        for pattern, repl in SLANG.items():
            text = re.sub(pattern, repl, text)
        fixed = 0
        for short, full in CONTRACTIONS.items():
            text, n = re.subn(rf"\b{short}\b", full, text)          # nur kleingeschrieben: „IM“ bleibt
            fixed += n
        text, n = re.subn(r"(?<![\w'’])i(?![\w'’])", "I", text)
        fixed += n
        if fixed:
            notes.append(f"{fixed} Kurzform(en) ohne Apostroph korrigiert (z. B. „im“ → „I'm“).")
    text = DROP_TOKENS.sub("", text)
    ages = len(AGE_TAG.findall(text))
    text = AGE_TAG.sub(lambda m: f", {m.group(1) or m.group(2)},", text)
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r",\s*([.!?;:])", r"\1", text)
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    if expanded:
        notes.append(f"Abkürzungen ausgeschrieben: {', '.join(a.rstrip('.') for a in expanded)}.")
    if ages:
        notes.append(f"{ages} Altersangabe(n) wie „(25F)“ vorlesbar gemacht.")
    if soften:
        count = 0
        for pattern, repl in (SOFTEN_DE if lang == "de" else SOFTEN):
            text, n = re.subn(pattern, repl, text, flags=re.I)
            count += n
        if count:
            notes.append(f"{count} Kraftausdruck/-ausdrücke entschärft (TikTok/YouTube werten sonst ab).")
        text, count = soften_sensitive(text, lang)
        if count:
            notes.append(f"{count} heikle Stelle(n) umschrieben – angedeutet statt ausgesprochen, "
                         "die Handlung bleibt gleich.")
    return text, notes


# --------------------------------------------------------------------------- Szenen und Teile

SENTENCE_END = re.compile(r"(?<=[.!?…])[\"”’']?\s+(?=[\"“‘'(]?[A-ZÄÖÜ0-9])")


def sentences(paragraph: str) -> list[str]:
    return [s.strip() for s in SENTENCE_END.split(paragraph) if s.strip()]


def make_scenes(text: str, target_words: int = 38, max_words: int = 60) -> list[str]:
    """Absätze als Szenen; kurze zusammenlegen, lange an Satzgrenzen teilen."""
    scenes: list[str] = []
    buffer: list[str] = []
    for paragraph in [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]:
        for sentence in sentences(paragraph):
            buffer.append(sentence)
            if len(" ".join(buffer).split()) >= target_words:
                scenes.append(" ".join(buffer))
                buffer = []
        if buffer and len(" ".join(buffer).split()) >= target_words * 0.6:   # Absatzende = guter Schnitt
            scenes.append(" ".join(buffer))
            buffer = []
    if buffer:
        if scenes and len(" ".join(buffer).split()) < target_words * 0.5:
            scenes[-1] += " " + " ".join(buffer)
        else:
            scenes.append(" ".join(buffer))
    # sehr lange Einzelszenen (ein Satz-Monster) bleiben, werden aber nicht weiter zerhackt
    return [s for s in scenes if s]


def estimate_seconds(text: str, lang: str, rate: str, pause: float) -> float:
    words = len(text.split())
    n_sentences = max(1, len(sentences(text)))
    return words / (WORDS_PER_SECOND[lang] * rate_factor(rate)) + n_sentences * pause * 0.8


def split_parts(scene_seconds: list[float], max_seconds: float, overhead: float = 9.0) -> list[list[int]]:
    """Szenen-Indizes je Teil: möglichst gleich lange Teile, jeder unter max_seconds (inkl. Titel/Abspann)."""
    total = sum(scene_seconds)
    budget = max_seconds - overhead
    n_parts = max(1, -(-int(total) // int(budget)))          # aufrunden
    while True:
        target = total / n_parts
        parts, current, length = [], [], 0.0
        for i, sec in enumerate(scene_seconds):
            if current and (length + sec > budget or (length >= target and len(parts) < n_parts - 1)):
                parts.append(current)
                current, length = [], 0.0
            current.append(i)
            length += sec
        parts.append(current)
        if all(sum(scene_seconds[i] for i in p) <= budget for p in parts) or n_parts > 12:
            return parts
        n_parts += 1


# --------------------------------------------------------------------------- Bilder/Clips je Szene

DARK_MOODS = frozenset({"creepy", "suspense"})

# (Muster im Text, Suchbegriff für Stockvideos, Motiv für KI-Bilder[, nur bei diesen Stimmungen])
VISUALS = [
    (r"\b(argu\w*|fight\w*|yell\w*|scream\w* at|furious|angry|streit\w*|stress|wütend|sauer|vorwürfe?)\b",
     "couple arguing", "two people arguing in a living room, tense body language"),
    (r"\b(cr(y|ied|ying)|tears|sobb\w*|weinen|weinte|geweint|tränen)\b", "person crying",
     "a person crying alone by a window"),
    (r"\b(laugh\w*|giggl\w*|lachen|lachte|gelacht)\b", "people laughing", "friends laughing together"),
    (r"\b(thinking|wonder\w*|realiz\w*|überleg\w*|nachgedacht|nachdenk\w*|verstehe nicht)\b", "person thinking window",
     "a person lost in thought looking out of a window"),
    (r"\b(hug\w*|embrac\w*|umarm\w*)\b", "people hugging", "two people hugging warmly"),
    (r"\b(basement|cellar|keller)\b", "dark basement stairs", "a dark basement with a single hanging light bulb"),
    (r"\b(attic|dachboden)\b", "dusty attic", "a dusty attic with old boxes and a small window"),
    (r"\b(cemetery|graveyard|grave|friedhof|grab)\b", "cemetery fog", "an old cemetery covered in fog"),
    (r"\b(telescope|scope|stars?|sky|skies|nebula|galaxy|planets?|space|teleskop|sterne?n?|himmel)\b", "night sky stars",
     "a vast night sky full of stars above a lonely field"),
    (r"\b(moon|moonlight|mond)\b", "full moon night", "a pale full moon behind thin clouds"),
    (r"\b(sunset|dusk|horizon|twilight|sonnenuntergang|dämmerung|horizont)\b", "sunset horizon",
     "a dark horizon at dusk with the last light fading"),
    (r"\b(woods|forest|trees|wald|wäldern|bäume)\b", "dark forest", "a dense forest with tall trees and a narrow path"),
    (r"\b(cabin|hut|shack|hütte)\b", "cabin in woods", "a small wooden cabin in the woods"),
    (r"\b(tent|camping|campfire|campsite|zelt)\b", "campfire night", "a campsite with a tent and a campfire"),
    (r"\b(lake|river|pond|fluss|teich)\b", "lake mist", "a calm lake with mist over the water"),
    (r"\b(ocean|sea|beach|waves|meer|strand)\b", "ocean waves", "dark ocean waves under a grey sky"),
    (r"\b(field|farm|barn|cornfield|feld|bauernhof)\b", "farm field", "an empty farm field with an old barn"),
    (r"\b(hospital|nurse|doctor|krankenhaus|klinik|arzt|ärztin)\b", "hospital corridor", "an empty hospital corridor with fluorescent lights"),
    (r"\b(gas station|tankstelle)\b", "gas station night", "a lonely gas station at night"),
    (r"\b(hotel|motel)\b", "hotel hallway", "a long hotel hallway with patterned carpet"),
    (r"\b(elevator|aufzug)\b", "elevator interior", "the inside of an old elevator"),
    (r"\b(hallway|corridor|flur)\b", "dark hallway", "a long dark hallway with doors"),
    (r"\b(bathroom|shower|bathtub|badezimmer|dusche)\b", "bathroom mirror", "a bathroom with a fogged mirror"),
    (r"\b(mirror|reflection|spiegel)\b", "mirror reflection", "a mirror reflecting a dim room"),
    # Grusel-Motive nur bei Grusel/Spannung („in meinen Augen“ im Drama ist kein Augen-Close-up)
    (r"\b(eyes?|pupils?|stare|staring|stared|watching)\b", "eye close up", "a close-up of a human eye in dim light",
     DARK_MOODS),
    (r"\b(shadow|figure|silhouette|ghost|gestalt|schatten|geist)\b", "shadow silhouette",
     "a dark silhouette standing at the end of a room", DARK_MOODS),
    (r"\b(blood|knife|wound|blut|messer)\b", "red light dark", "a dim room lit by red light", DARK_MOODS),
    (r"\b(doll|puppe|clown|mask|maske)\b", "old doll", "an old porcelain doll on a shelf", DARK_MOODS),
    (r"\b(window|fenster)\b", "window night", "a window at night with something outside"),
    (r"\b(door|knock|knocking|doorbell|tür|klopfen|klingel)\b", "door opening", "a half-open door in a dim house"),
    (r"\b(stairs|staircase|treppe)\b", "staircase", "an old wooden staircase"),
    (r"\b(phone|texted|text message|voicemail|handy|anruf|nachricht)\b", "phone screen", "a smartphone screen glowing in the dark"),
    (r"\b(computer|laptop|screen|monitor|bildschirm)\b", "computer screen", "a computer screen glowing in a dark room"),
    (r"\b(camera|footage|photo|picture|kamera|foto)\b", "security camera", "a security camera in a corner"),
    (r"\b(car|drove|driving|truck|highway|auto|autobahn)\b", "driving at night", "a car driving on an empty road"),
    (r"\b(train|subway|zug|bahnhof)\b", "train station", "a train station platform"),
    (r"\b(plane|flight|airport|flugzeug|flughafen)\b", "airport", "an airport terminal"),
    (r"\b(school|classroom|teacher|student|schule|lehrer|lehrerin)\b", "school hallway", "a school hallway with lockers"),
    (r"\b(office|boss|manager|coworkers?|büro|chef|chefin|kollegen?)\b", "office", "a modern office with desks"),
    (r"\b(store|shop|customer|cashier|retail|laden|kunden?|kasse)\b", "store aisle", "a store aisle with shelves"),
    (r"\b(restaurant|waiter|waitress|diner|cafe)\b", "restaurant", "a restaurant table"),
    (r"\b(kitchen|cooking|küche|kochen)\b", "kitchen", "a home kitchen"),
    (r"\b(bedroom|bed|woke|schlafzimmer|bett)\b", "bedroom night", "a bedroom at night"),
    (r"\b(wedding|bride|groom|hochzeit|braut)\b", "wedding", "a wedding ceremony"),
    (r"\b(party|birthday|feier|geburtstag)\b", "party", "a party with lights"),
    (r"\b(dog|puppy|hund)\b", "dog", "a dog looking at the camera"),
    (r"\b(cat|kitten|katze)\b", "cat", "a cat in a house"),
    (r"\b(baby|toddler|kid|child|children|kind|kinder)\b", "child playing", "a child's room with toys"),
    (r"\b(police|cops?|officer|polizei)\b", "police lights", "police car lights at night"),
    (r"\b(money|rent|salary|cash|savings|debt|geld|miete|kosten|ersparnisse|finanz\w*|schulden)\b", "money",
     "money and bills on a kitchen table"),
    (r"\b(rain|storm|thunder|regen|gewitter)\b", "rain storm", "heavy rain against a window"),
    (r"\b(snow|blizzard|winter|schnee)\b", "snow", "a snowy landscape"),
    (r"\b(apartment|neighbou?rs?|wohnung|nachbarn?)\b", "apartment building", "an apartment building at dusk"),
    (r"\b(city|downtown|stadt)\b", "city street", "a city street"),
    (r"\b(light|glow|glowing|licht|leuchten)\b", "light in darkness", "a single light glowing in darkness"),
]


def visual_for(text: str, mood: str, index: int, avoid: set | frozenset = frozenset()) -> tuple[str, str]:
    """(Suchbegriff für Stockvideos, Bild-Prompt) zur Szene – nach dem häufigsten passenden Motiv.

    `avoid`: Motive der vorigen Szenen – damit nicht fünfmal hintereinander dasselbe Bild kommt."""
    low = text.lower()
    ranked = sorted(((len(re.findall(entry[0], low)), -i, entry[1], entry[2])
                     for i, entry in enumerate(VISUALS) if len(entry) < 4 or mood in entry[3]), reverse=True)
    m = MOODS[mood]
    options = [(query, subject) for hits, _, query, subject in ranked if hits > 0]
    defaults = m["default_queries"][index % len(m["default_queries"]):] + m["default_queries"]
    options += [(q, q) for q in defaults]
    query, subject = next((o for o in options if o[0] not in avoid), options[0])
    if mood in ("creepy", "suspense") and "night" not in query and "dark" not in query:
        query = f"{query} dark"
    return query, f"{subject}, {m['image_style']}, vertical composition, no text"


# --------------------------------------------------------------------------- Übersetzung

def translate(texts: list[str], target: str, source: str = "en") -> tuple[list[str], str]:
    """Übersetzt Szenen. Reihenfolge: Sprachmodell, DeepL (kostenloser Schlüssel), MyMemory (begrenzt)."""
    from . import translate as tr

    return tr.translate(texts, target, source)


# --------------------------------------------------------------------------- Skelett

INTRO_PART = {"de": "Teil {n}.", "en": "Part {n}."}
OUTRO_NEXT = {"de": "Teil {n} kommt bald – folge, damit du ihn nicht verpasst!",
              "en": "Part {n} is coming soon – follow so you don't miss it!"}
FOLLOW = {"de": "Folge für mehr Storys.", "en": "Follow for more stories."}


def build_skeleton(post: Post, lang: str = "de", mood: str | None = None, length: str = "3min",
                   visuals: str = "videos", soften: bool = True, use_llm: bool | None = None) -> dict:
    """Story-Skelett zum Prüfen und Anpassen – danach wird daraus das Video."""
    mood = mood or detect_mood(post.subreddit, post.title, post.text)
    source_lang = language_of(post.text)
    text, notes = clean_text(post.text)
    text, more = speakable(text, soften, source_lang)
    notes += more
    title, _ = speakable(clean_text(post.title)[0], soften, source_lang)
    gender = narrator_gender(post.text)
    voice, rate, pitch = voice_for(mood, lang, gender)
    if gender:
        notes.append(f"Erzählerstimme passend zum Ich-Erzähler ({'männlich' if gender == 'm' else 'weiblich'}).")
    pause = MOODS[mood]["pause"]

    use_llm = llm.available() if use_llm is None else use_llm
    scenes_src = make_scenes(text)
    editor = "Regeln"
    hook, figure = "", ""
    edited = claude_edit(title, scenes_src, lang, source_lang, mood, soften) if handoff.enabled() else None
    if edited:                                    # CUDI-App: Claude lektoriert (kostenlos), der Code prüft
        title_t, scenes_t, visuals_t, hook, edit_notes = edited[:5]
        figure = edited[5] if len(edited) > 5 else ""
        editor = "Claude-Lektorat"
        notes += edit_notes
        use_llm = False
    elif use_llm:
        try:
            title_t, scenes_t, visuals_t = _llm_edit(title, scenes_src, lang, mood, soften)
            editor = "KI-Lektorat"
            notes.append("KI-Lektorat: für die Erzählung geglättet und gekürzt, ohne neue Inhalte (geprüft).")
        except Exception as exc:                  # Lektorat per Regeln bleibt immer möglich
            log.warning("KI-Lektorat nicht möglich: %s", exc)
            use_llm = False
    if not use_llm and not edited:
        if lang != source_lang:
            translated, provider = translate([title, *scenes_src], lang, source_lang)
            title_t, scenes_t = translated[0], translated[1:]
            notes.append(f"Übersetzt mit {provider}.")
        else:
            title_t, scenes_t = title, scenes_src
        visuals_t = []
        for i, src in enumerate(scenes_src):
            recent = {v[0].removesuffix(" dark") for v in visuals_t[-2:]}      # keine direkte Wiederholung
            visuals_t.append(visual_for(src, mood, i, recent))

    seconds = [estimate_seconds(s, lang, rate, pause) for s in scenes_t]
    # Ein Einstieg (statt des Titels) verlängert Teil 1 – vorsichtshalber bei allen Teilen abziehen
    hook_extra = max(0.0, estimate_seconds(hook, lang, rate, pause) - estimate_seconds(title_t, lang, rate, pause)) \
        if hook else 0.0
    max_seconds = LENGTHS[length]["seconds"] if length in ("kurz", "lang") else config.STORY_MAX_SECONDS
    groups = split_parts(seconds, max_seconds - hook_extra)
    if len(groups) > 1:
        notes.append(f"Story ist zu lang für ein Video ({sum(seconds) / 60:.1f} min) – aufgeteilt in "
                     f"{len(groups)} Teile mit Cliffhanger.")
    parts = []
    for n, idx in enumerate(groups, start=1):
        last = n == len(groups)
        parts.append({
            "intro": title_t if n == 1 else f"{INTRO_PART[lang].format(n=n)} {title_t}",
            "scenes": [{"text": scenes_t[i], "source": scenes_src[i], "query": visuals_t[i][0],
                        "prompt": visuals_t[i][1]} for i in idx],
            "outro": (f"{MOODS[mood]['outro'][lang]} {FOLLOW[lang]}" if last
                      else OUTRO_NEXT[lang].format(n=n + 1)),
            "estimated_seconds": round(sum(seconds[i] for i in idx) + 9),
        })
    return {
        "version": 1,
        "post": post.to_dict(),
        "lang": lang,
        "mood": mood,
        "voice": {"name": voice, "rate": rate, "pitch": pitch, "pause": pause},
        "visuals": visuals,
        "title": title_t,
        "hook": hook,                       # Einstieg in Teil 1 (gesprochen, während die Story-Karte steht)
        "figur": figure or FIGURES.get(gender or "", FIGURES[""]),   # Hauptfigur der Cartoon-Bilder (englisch)
        "parts": parts,
        "notes": notes,
        "rights": rights_note(post),
        "editor": editor,
        "length": length,
    }


# --------------------------------------------------------------------------- KI-Lektorat (optional)

LLM_EDIT = (
    "Du bist ein erfahrener Sprecher und Lektor für Story-Videos auf TikTok und YouTube Shorts. "
    "Du bekommst die Szenen einer Reddit-Story. Schreibe jede Szene als gesprochenen Text in der Zielsprache "
    "um: natürlich, flüssig, {style}. Kürzen ist erlaubt (Füllsätze, Wiederholungen). VERBOTEN: neue "
    "Ereignisse, Personen, Orte, Zahlen oder Details erfinden – nur was im Original steht. Behalte die "
    "Ich-Perspektive. {soften}Antworte NUR mit JSON: {{\"title\": \"...\", \"scenes\": [{{\"text\": \"...\", "
    "\"visual\": \"englische Bildbeschreibung, 8-15 Wörter, ohne Namen\", \"query\": \"2-3 englische Wörter "
    "für eine Stockvideo-Suche\"}}]}} – genau so viele Szenen wie im Original."
)
STYLE = {
    "creepy": "langsam, unheilvoll, mit Spannungspausen – wie ein Gruselgeschichten-Erzähler",
    "suspense": "spannungsgeladen, kurze Sätze an den Höhepunkten",
    "funny": "locker, mit komischem Timing, trocken pointiert",
    "drama": "emotional, nahbar, wie eine Freundin, die das Drama erzählt",
    "revenge": "genüsslich, selbstbewusst, mit Vorfreude auf die Pointe",
    "wholesome": "warm, herzlich, ruhig",
}
SOFTEN_HINT = ("Heikle Stellen (Sex, Gewalt, Selbstverletzung, Drogen, Kraftausdrücke) TikTok-tauglich umschreiben: "
               "andeuten statt aussprechen, so dass man versteht, was gemeint ist – die Handlung bleibt gleich. ")
LLM_CHECK = (
    "Prüfe, ob die neue Fassung Inhalte enthält, die NICHT im Original stehen (neue Ereignisse, Personen, Orte, "
    "Zahlen). Kürzungen, Umformulierungen und Umschreibungen heikler Stellen sind erlaubt. Antworte NUR mit JSON: "
    "{\"added\": [Szenennummern ab 1]}."
)


def _llm_edit(title: str, scenes: list[str], lang: str, mood: str,
              soften: bool = True) -> tuple[str, list[str], list[tuple[str, str]]]:
    target = {"de": "Deutsch", "en": "Englisch"}[lang]
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(scenes, start=1))
    data = llm.chat_json(LLM_EDIT.format(style=STYLE[mood], soften=SOFTEN_HINT if soften else ""),
                         f"Zielsprache: {target}\nTitel: {title}\n\nSzenen:\n{numbered}", temperature=0.5)
    new = data["scenes"]
    if len(new) != len(scenes):
        raise ValueError(f"KI lieferte {len(new)} statt {len(scenes)} Szenen")
    check = llm.chat_json(LLM_CHECK, "ORIGINAL:\n" + numbered + "\n\nNEU:\n" +
                          "\n".join(f"{i}. {s['text']}" for i, s in enumerate(new, start=1)), temperature=0.0)
    flagged = {int(i) for i in check.get("added", [])}
    texts = []
    for i, (orig, scene) in enumerate(zip(scenes, new), start=1):
        if i in flagged:                       # erfundene Details -> Original (ggf. übersetzt) verwenden
            texts.append(orig if language_of(orig) == lang else translate([orig], lang, language_of(orig))[0][0])
        else:
            texts.append(scene["text"].strip())
    m = MOODS[mood]
    visuals = [(s.get("query") or visual_for(o, mood, i)[0],
                f"{s.get('visual') or visual_for(o, mood, i)[1]}, {m['image_style']}, vertical composition, no text")
               for i, (o, s) in enumerate(zip(scenes, new))]
    return data.get("title", title).strip() or title, texts, visuals


# --------------------------------------------------------------------------- Lektorat durch Claude (CUDI-App)

CLAUDE_EDIT = (
    "Du bist Lektor und Sprecher für Reddit-Story-Videos (TikTok/YouTube Shorts). Schreibe jede Szene aus "
    "„szenen“ als gesprochenen Text in der Zielsprache „zielsprache“ (de = Deutsch, en = Englisch) neu: natürlich, "
    "flüssig, im Stil „stil“, die Ich-Perspektive bleibt. Kürzen ist erlaubt (Füllsätze, Wiederholungen), Spannung "
    "aufbauen ist erwünscht. VERBOTEN: neue Ereignisse, Personen, Orte, Zahlen oder Details erfinden – nur was in den "
    "Szenen steht. Ist „entschaerfen“ true: heikle Stellen (Sex, Gewalt, Selbstverletzung, Drogen, Kraftausdrücke) "
    "TikTok-tauglich umschreiben – andeuten statt aussprechen, so dass man versteht, was gemeint ist; die Handlung "
    "bleibt gleich. Schreibe außerdem: „titel“ (kurz, macht neugierig, höchstens 60 Zeichen, verrät nicht das Ende) "
    "und „hook“ (1–2 kurze Sätze für die ersten Sekunden, die sofort neugierig machen – aus der Story, ohne das Ende "
    "zu verraten, keine Frage an die Zuschauer) und „figur“ (Aussehen der Hauptfigur/Erzählperson auf Englisch, "
    "8–20 Wörter, z. B. Alter, Haare, Kleidung – passend zur Story, sonst neutral; für gleichbleibende Cartoon-Bilder). "
    "Zu jeder Szene: „bild“ (englische Bildbeschreibung, 8–15 Wörter, "
    "ohne Namen) und „suche“ (2–3 englische Wörter für eine Stockvideo-Suche). Antwort: {\"titel\": \"…\", "
    "\"hook\": \"…\", \"figur\": \"…\", \"szenen\": [{\"text\": \"…\", \"bild\": \"…\", \"suche\": \"…\"}]} – genau so viele "
    "Szenen wie in „szenen“, gleiche Reihenfolge."
)
EDIT_FREE = {"i", "i'm", "i've", "i'd", "i'll", "mr", "mrs", "ms", "dr", "oh", "god", "ok", "okay", "no", "yes", "mom",
             "dad", "reddit", "tiktok"}


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


def _numbers(text: str, lang: str = "en") -> set[str]:
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


def _digits(text: str) -> set[str]:          # bleibt für Titel/Einstieg ohne Sprachangabe
    return _numbers(text, "en") | _numbers(text, "de")


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


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zäöüß0-9]+", text.lower()))


def _known(word: str, tokens: set[str]) -> bool:
    """Wort im Original belegt? Ganze Wörter, bei längeren Wörtern auch gebeugt („Jessicas“) – nie als Teilwort
    („Mark“ ist durch „market“ nicht belegt)."""
    low = word.lower().strip("'’-")
    low = re.sub(r"['’]s$", "", low)
    if low in tokens:
        return True
    return len(low) >= 5 and any(len(t) >= 5 and (t.startswith(low[:5]) and low.startswith(t[:5])) and
                                 abs(len(t) - len(low)) <= 2 for t in tokens)


def _invented_people(text: str, source: str) -> list[str]:
    """Vornamen im neuen Text, die im Original nicht vorkommen (sprachunabhängig)."""
    tokens = _tokens(source)
    return [w for w in re.findall(r"[A-ZÄÖÜ][a-zäöüß]+", text) if w.lower() in FIRST_NAMES and not _known(w, tokens)]


# Häufige Satzanfänge – andere großgeschriebene Wörter am Satzanfang könnten neue Namen sein („Jessica never …“)
STARTERS = set("""the a an i it its he she they we you my his her our their your there then than when after before
    but and so or as at on in by for with from to of this that these those what why how who whom which where while
    every each all no not nothing nobody nowhere none now later still even just maybe perhaps one two three some
    someone something somehow sometimes somewhere everyone everything everybody anyone anything anybody once twice
    again soon finally instead meanwhile outside inside behind under above below between through until since
    without within because if though although yet also only never always ever today tonight yesterday tomorrow
    here up down out over back next last first then thanks well yeah please sure right wait look hey hi hello""".split())


def _new_names(text: str, source: str) -> list[str]:
    """Englisch: großgeschriebene Wörter (Namen, Orte), die im Original nicht vorkommen – mitten im Satz immer,
    am Satzanfang, wenn sie keine üblichen Satzanfänge sind."""
    tokens = _tokens(source)
    out = []
    for sentence in re.split(r"(?<=[.!?:;\"“”—–])\s+", text):
        for i, word in enumerate(re.findall(r"[A-Za-z][\w'’-]*", sentence)):
            low = word.lower().strip("'’-")
            parts = [p for p in re.split(r"[-'’]", low) if p]
            if not word[0].isupper() or low in EDIT_FREE or all(p in EDIT_FREE or _known(p, tokens) for p in parts):
                continue
            if i == 0 and (low in STARTERS or re.search(r"(?:ly|ing|ed)$", low) or len(low) < 3):
                continue
            out.append(word)
    return out


def _edit_problem(new, source: str, lang: str, source_lang: str, context: str) -> str | None:
    """Grund, warum ein lektorierter Text nicht übernommen wird (None = in Ordnung)."""
    if not isinstance(new, str) or not new.strip():
        return "leer"
    words, src_words = len(new.split()), max(1, len(source.split()))
    if words > src_words * 1.5 + 8:
        return "zu lang"
    if words < src_words * 0.35 and src_words > 12:
        return "zu stark gekürzt"
    if not _numbers(new, lang) <= _numbers(context, source_lang):
        return "neue Zahl"
    people = _invented_people(new, context)
    if people:
        return "neue Namen: " + ", ".join(people[:3])
    if lang == "en" and source_lang == "en":
        names = _new_names(new, context)
        if names:
            return "neue Namen: " + ", ".join(names[:3])
    return None


def claude_edit(title: str, scenes: list[str], lang: str, source_lang: str, mood: str, soften: bool):
    """Lektorat durch Claude in der Auftrags-Sitzung. Rückgabe (Titel, Szenen, Bilder, Hook, Notizen, Figur) oder None.

    Jede Szene wird einzeln geprüft; eine abgelehnte Szene bekommt die Regel-Fassung (bei anderer Zielsprache
    übersetzt). Wirft handoff.WritingNeeded, solange Claude noch nicht geantwortet hat."""
    data = {"titel": title, "zielsprache": lang, "originalsprache": source_lang, "stimmung": mood,
            "stil": STYLE[mood], "entschaerfen": bool(soften), "szenen": scenes}
    answer = handoff.request("lektorat", CLAUDE_EDIT, data)
    if not isinstance(answer, dict) or not isinstance(answer.get("szenen"), list) or len(answer["szenen"]) != len(scenes):
        if answer is not None:
            log.warning("Claude-Lektorat unbrauchbar (Szenenzahl) – Regeln verwendet")
        return None
    story = " ".join([title, *scenes])
    texts, rejected = [], []
    for i, (src, new) in enumerate(zip(scenes, answer["szenen"])):
        text = new.get("text") if isinstance(new, dict) else None
        problem = _edit_problem(text, src, lang, source_lang, f"{title} {src}")
        texts.append(None if problem else text.strip())
        if problem:
            rejected.append((i, problem))
    if len(rejected) > len(scenes) // 2:        # mehr als die Hälfte daneben: lieber ganz nach Regeln
        log.warning("Claude-Lektorat verworfen (%s)", rejected)
        return None
    raw_title = answer.get("titel")
    title_ok = (isinstance(raw_title, str) and 3 <= len(raw_title.strip()) <= 80
                and _numbers(raw_title, lang) <= _numbers(story, source_lang) and not _invented_people(raw_title, story)
                and not (lang == "en" and source_lang == "en" and _new_names(raw_title, story)))
    missing = [i for i, t in enumerate(texts) if t is None]
    if missing or not title_ok:
        fill = [scenes[i] for i in missing] + ([] if title_ok else [title])
        if lang != source_lang:
            fill, _ = translate(fill, lang, source_lang)       # kann Claude um eine Übersetzung bitten
        for i, text in zip(missing, fill):
            texts[i] = text
        title_t = raw_title.strip() if title_ok else fill[-1]
    else:
        title_t = raw_title.strip()
    hook = answer.get("hook")
    if not (isinstance(hook, str) and 3 <= len(hook.split()) <= 30 and _numbers(hook, lang) <= _numbers(story, source_lang)
            and not _invented_people(hook, story) and not (lang == "en" and source_lang == "en" and _new_names(hook, story))):
        hook = ""
    m = MOODS[mood]
    visuals = []
    for i, (src, new) in enumerate(zip(scenes, answer["szenen"])):
        new = new if isinstance(new, dict) else {}
        query, picture = str(new.get("suche") or ""), str(new.get("bild") or "")
        fallback = visual_for(src, mood, i, {v[0] for v in visuals[-2:]})
        query = query.strip().lower() if re.fullmatch(r"[A-Za-z][A-Za-z ,'-]{1,40}", query.strip()) else fallback[0]
        picture = picture.strip() if 3 <= len(picture.split()) <= 30 else fallback[1]
        if not picture.endswith("no text"):
            picture = f"{picture}, {m['image_style']}, vertical composition, no text"
        visuals.append((query, picture))
    notes = ["Lektorat von Claude: im Stil der Stimmung erzählt, heikle Stellen umschrieben, Einstieg und Bildideen "
             "neu – geprüft auf neue Zahlen, Namen und Länge."]
    if rejected:
        notes.append("Szenen in Regel-Fassung (Lektorat nicht übernommen): "
                     + ", ".join(f"{i + 1} ({why})" for i, why in rejected))
    figure = answer.get("figur")
    figure = figure.strip() if isinstance(figure, str) and re.fullmatch(r"[A-Za-z0-9 ,.'’-]{10,200}", figure.strip()) \
        and 3 <= len(figure.split()) <= 30 else ""
    return title_t, texts, visuals, hook, notes, figure
