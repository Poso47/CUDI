"""Stimmungen: woher die Storys kommen und wie sie erzählt werden (Stimme, Tempo, Musik, Look).

Eine Beschreibung wie „gruselige Story über einen Stalker im Wald“ wird ohne KI in einen Suchplan
übersetzt: Stimmung → passende Subreddits, Stichwörter (für die Suche ins Englische übertragen).
"""

from __future__ import annotations

import re

# Stimme: (Name, Tempo, Tonhöhe). Pause: längste erlaubte Pause zwischen Sätzen (Grusel braucht Luft).
MOODS: dict[str, dict] = {
    "creepy": {
        "label": {"de": "Gruselig", "en": "Creepy"}, "icon": "👻",
        # r/shortscarystories: höchstens 500 Wörter – ideal für 1–3 Minuten; r/nosleep eher für Teile
        "subreddits": ["shortscarystories", "nosleep", "LetsNotMeet", "creepyencounters", "Thetruthishere"],
        "words": ["grusel", "gruselig", "horror", "creepy", "scary", "unheimlich", "spuk", "geist", "angst",
                  "schaurig", "paranormal", "dämon", "albtraum", "nosleep", "gänsehaut"],
        "signals": ["scream", "blood", "shadow", "whisper", "footsteps", "knock", "figure", "ghost", "dead",
                    "corpse", "basement", "woods", "eyes", "smile", "door", "night", "dark", "creature",
                    "stalk", "watching", "noise", "cold", "silence"],
        "voice": {"de": ("de-DE-KillianNeural", "-12%", "-6Hz"), "en": ("en-US-ChristopherNeural", "-12%", "-6Hz")},
        "pause": 0.6, "music": "drone",
        # KI-Bilder sind schon düster – nur entsättigen, leicht Kontrast, Vignette und Korn (nicht abdunkeln)
        "grade": "eq=saturation=0.45:brightness=-0.01:contrast=1.08,vignette=PI/4.5,noise=alls=6:allf=t",
        "colors": {"text": "FFFFFF", "highlight": "E8283A", "card": (20, 20, 24)},
        "image_style": "dark cinematic horror photograph, eerie atmosphere, fog, low light, muted colors, film grain",
        "default_queries": ["dark forest night", "abandoned house", "dark hallway", "foggy road night", "flickering light"],
        "outro": {"de": "Wärst du geblieben – oder gerannt? Schreib es in die Kommentare.",
                  "en": "Would you have stayed... or run? Tell me in the comments."},
    },
    "suspense": {
        "label": {"de": "Spannend", "en": "Suspense"}, "icon": "⚡",
        "subreddits": ["LetsNotMeet", "Thetruthishere", "UnresolvedMysteries", "TrueOffMyChest"],
        "words": ["spannend", "spannung", "thriller", "krimi", "mysteriös", "rätsel", "verfolgt", "suspense",
                  "mystery", "thrilling", "verschwunden", "polizei"],
        "signals": ["police", "followed", "stranger", "missing", "car", "phone", "call", "detective", "suddenly",
                    "found", "investigation", "chase", "locked", "secret"],
        "voice": {"de": ("de-DE-ConradNeural", "-3%", "-2Hz"), "en": ("en-US-GuyNeural", "-3%", "-2Hz")},
        "pause": 0.45, "music": "pulse",
        "grade": "eq=saturation=0.75:contrast=1.12:brightness=-0.03,vignette=PI/4.5",
        "colors": {"text": "FFFFFF", "highlight": "F5B700", "card": (24, 26, 32)},
        "image_style": "cinematic thriller still, tense atmosphere, dramatic shadows, teal and orange, shallow depth of field",
        "default_queries": ["city night street", "car driving night", "phone screen dark", "rain window night"],
        "outro": {"de": "Was hättest du an dieser Stelle getan? Schreib es in die Kommentare.",
                  "en": "What would you have done? Let me know in the comments."},
    },
    "funny": {
        "label": {"de": "Lustig", "en": "Funny"}, "icon": "😂",
        "subreddits": ["tifu", "StoriesAboutKevin", "IDontWorkHereLady", "TalesFromRetail", "talesfromtechsupport"],
        "words": ["lustig", "witzig", "komisch", "peinlich", "funny", "hilarious", "lachen", "humor", "tifu",
                  "fail", "dumm", "kevin", "absurd"],
        "signals": ["laugh", "lol", "hilarious", "embarrass", "accidentally", "awkward", "fart", "poop", "oops",
                    "funny", "dumb", "idiot", "kevin", "ridiculous", "joke"],
        "voice": {"de": ("de-DE-FlorianMultilingualNeural", "+8%", "+2Hz"), "en": ("en-US-BrianNeural", "+8%", "+2Hz")},
        "pause": 0.3, "music": "pluck",
        "grade": "eq=saturation=1.3:brightness=0.03:contrast=1.04",
        "colors": {"text": "FFFFFF", "highlight": "FFD400", "card": (255, 255, 255)},
        "image_style": "bright colorful comedic photo, funny situation, vivid colors, sharp, cheerful lighting",
        "default_queries": ["office people laughing", "funny dog", "city street day", "people laughing"],
        "outro": {"de": "Ist dir schon mal was Peinlicheres passiert? Ab in die Kommentare damit!",
                  "en": "Has something even more embarrassing happened to you? Drop it in the comments!"},
    },
    "drama": {
        "label": {"de": "Drama", "en": "Drama"}, "icon": "🔥",
        "subreddits": ["AmItheAsshole", "AITAH", "relationship_advice", "BestofRedditorUpdates", "TrueOffMyChest"],
        "subreddits_de": ["BinIchDasArschloch", "beziehungen", "Ratschlag"],      # deutsch – ohne Übersetzung
        "words": ["drama", "streit", "beziehung", "familie", "hochzeit", "schwiegermutter", "betrug", "fremdgehen",
                  "aita", "arschloch", "ex", "trennung", "affäre"],
        "signals": ["wife", "husband", "boyfriend", "girlfriend", "wedding", "mother-in-law", "cheat", "divorce",
                    "sister", "brother", "family", "aita", "fiance", "parents", "inheritance"],
        "voice": {"de": ("de-DE-KatjaNeural", "+4%", "+0Hz"), "en": ("en-US-AriaNeural", "+4%", "+0Hz")},
        "pause": 0.35, "music": "pad",
        "grade": "eq=saturation=0.9:contrast=1.06,colorbalance=bs=0.04:rs=-0.02",
        "colors": {"text": "FFFFFF", "highlight": "FF4D8D", "card": (255, 255, 255)},
        "image_style": "cinematic emotional drama still, natural light, realistic people, moody colors",
        "default_queries": ["couple arguing", "family dinner", "woman thinking window", "wedding"],
        "outro": {"de": "Wer ist hier im Unrecht? Stimm in den Kommentaren ab!",
                  "en": "Who's in the wrong here? Vote in the comments!"},
    },
    "revenge": {
        "label": {"de": "Rache", "en": "Revenge"}, "icon": "😈",
        "subreddits": ["ProRevenge", "pettyrevenge", "MaliciousCompliance", "NuclearRevenge"],
        "words": ["rache", "revenge", "karma", "heimzahlen", "vergeltung", "petty", "genugtuung", "chef",
                  "vermieter", "nachbar"],
        "signals": ["revenge", "karma", "boss", "landlord", "hoa", "manager", "complied", "policy", "fired",
                    "neighbor", "entitled", "lawyer", "payback"],
        "voice": {"de": ("de-DE-ConradNeural", "+5%", "+0Hz"), "en": ("en-US-AndrewNeural", "+5%", "+0Hz")},
        "pause": 0.32, "music": "beat",
        "grade": "eq=saturation=1.05:contrast=1.14,vignette=PI/5",
        "colors": {"text": "FFFFFF", "highlight": "36E27A", "card": (255, 255, 255)},
        "image_style": "cinematic photo, confident mood, dramatic lighting, office or suburban setting, sharp",
        "default_queries": ["office meeting", "boss office", "suburban street", "handshake deal"],
        "outro": {"de": "Hättest du es genauso gemacht? Schreib es in die Kommentare.",
                  "en": "Would you have done the same? Tell me in the comments."},
    },
    "wholesome": {
        "label": {"de": "Herzerwärmend", "en": "Wholesome"}, "icon": "💛",
        "subreddits": ["MadeMeSmile", "BestofRedditorUpdates", "TrueOffMyChest", "CasualConversation"],
        "words": ["herzerwärmend", "schön", "rührend", "wholesome", "glücklich", "hilfsbereit", "freundlich",
                  "dankbar", "liebe", "positiv", "berührend"],
        "signals": ["kind", "grateful", "stranger", "helped", "thank", "tears", "smile", "love", "donated",
                    "surprise", "hug", "proud", "adopted"],
        "voice": {"de": ("de-DE-SeraphinaMultilingualNeural", "+0%", "+0Hz"), "en": ("en-US-AvaNeural", "+0%", "+0Hz")},
        "pause": 0.4, "music": "warm",
        "grade": "colorbalance=rs=0.06:gs=0.02:bs=-0.05,eq=saturation=1.1:brightness=0.03",
        "colors": {"text": "FFFFFF", "highlight": "FFB547", "card": (255, 255, 255)},
        "image_style": "warm heartwarming photo, golden hour light, soft focus, kind people, gentle colors",
        "default_queries": ["sunset friends", "people hugging", "helping hand", "family happy"],
        "outro": {"de": "Hat dich das auch berührt? Erzähl uns von deiner schönsten Begegnung.",
                  "en": "Did this make you smile too? Tell us about your kindest encounter."},
    },
}

DEFAULT_MOOD = "creepy"

# Häufige Wörter aus deutschen Beschreibungen -> englische Suchbegriffe (die Storys sind meist englisch)
DE_EN = {
    "wald": "woods", "wälder": "woods", "haus": "house", "nacht": "night", "nachbar": "neighbor", "nachbarin": "neighbor",
    "geist": "ghost", "geister": "ghost", "keller": "basement", "dachboden": "attic", "auto": "car", "camping": "camping",
    "zelt": "tent", "hotel": "hotel", "krankenhaus": "hospital", "schule": "school", "arbeit": "work", "job": "job",
    "chef": "boss", "chefin": "boss", "hochzeit": "wedding", "schwiegermutter": "mother-in-law", "freundin": "girlfriend",
    "freund": "boyfriend", "mann": "husband", "frau": "wife", "schwester": "sister", "bruder": "brother",
    "mutter": "mom", "vater": "dad", "hund": "dog", "katze": "cat", "baby": "baby", "kind": "kid", "puppe": "doll",
    "spiegel": "mirror", "telefon": "phone", "anruf": "call", "handy": "phone", "fenster": "window", "tür": "door",
    "straße": "road", "see": "lake", "berg": "mountain", "hütte": "cabin", "zug": "train", "flugzeug": "plane",
    "nachtschicht": "night shift", "tankstelle": "gas station", "babysitter": "babysitter", "fremder": "stranger",
    "fremde": "stranger", "stalker": "stalker", "verfolger": "stalker", "friedhof": "cemetery", "kirche": "church",
    "vermieter": "landlord", "kollege": "coworker", "kollegin": "coworker", "kunde": "customer", "kundin": "customer",
    "restaurant": "restaurant", "laden": "store", "supermarkt": "store", "urlaub": "vacation", "reise": "trip",
    "erbe": "inheritance", "geld": "money", "polizei": "police", "einbrecher": "intruder", "clown": "clown",
    "bauernhof": "farm", "wohnung": "apartment", "aufzug": "elevator", "parkplatz": "parking lot", "schiff": "ship",
}
STOPWORDS = {
    "eine", "einen", "einem", "einer", "ein", "der", "die", "das", "den", "dem", "des", "und", "oder", "über", "von",
    "mit", "im", "in", "am", "an", "auf", "für", "zu", "zum", "zur", "story", "storys", "stories", "geschichte",
    "geschichten", "reddit", "video", "bitte", "mach", "mache", "irgendwas", "etwas", "so", "wie", "the", "a", "an",
    "about", "with", "of", "and", "or", "in", "on", "at", "for", "to", "some", "story", "please", "make",
    "something", "eher", "sehr", "richtig", "echt", "mal", "noch", "wo", "was", "wer", "ich", "mir", "mich",
    "lange", "kurze", "kurz", "lang", "teil", "teile", "minuten", "sekunden",
    *(f"{p}{e}" for p in ("mein", "dein", "sein", "ihr", "unser", "euer") for e in ("", "e", "en", "em", "er", "es")),
    "my", "your", "his", "her", "their", "our",
}


# Reine Stimmungswörter – sie bestimmen die Stimmung, sind aber kein Suchbegriff („gruselig“, nicht „Geist“)
GENERIC_MOOD_WORDS = (
    "grusel", "horror", "creepy", "scary", "unheimlich", "schaurig", "gänsehaut", "spannend", "spannung",
    "thriller", "krimi", "mysteriös", "suspense", "mystery", "thrilling", "lustig", "witzig", "komisch",
    "funny", "hilarious", "lachen", "humor", "absurd", "drama", "rache", "revenge", "herzerwärmend", "schön",
    "rührend", "wholesome", "glücklich", "positiv", "berührend", "dankbar",
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zäöüß0-9'-]+", text.lower())


def mood_from_words(text: str) -> str | None:
    """Stimmung aus einer Beschreibung („gruselig“, „lustig“ …) oder None."""
    tokens = _tokens(text)
    best, best_hits = None, 0
    for key, mood in MOODS.items():
        hits = sum(1 for t in tokens for w in mood["words"] if t.startswith(w))
        if hits > best_hits:
            best, best_hits = key, hits
    return best


GERMAN_HINTS = {"und", "ich", "nicht", "die", "der", "das", "ist", "mit", "ein", "eine", "auch", "aber", "mein", "wir"}
ENGLISH_HINTS = {"and", "the", "not", "was", "with", "my", "it", "that", "but", "this", "she", "he", "we", "they"}


def language_of(text: str) -> str:
    """„de“ oder „en“ anhand häufiger Funktionswörter."""
    tokens = _tokens(text[:3000])
    de = sum(t in GERMAN_HINTS for t in tokens)
    en = sum(t in ENGLISH_HINTS for t in tokens)
    return "de" if de > en else "en"


def subreddits_for(mood: str, lang: str) -> list[str]:
    """Deutsche Videos: zuerst deutschsprachige Subreddits (keine Übersetzung nötig), dann englische."""
    m = MOODS[mood]
    return [*m.get("subreddits_de", []), *m["subreddits"]] if lang == "de" else list(m["subreddits"])


def plan_from_description(description: str, lang: str = "en") -> dict:
    """„gruselige Story über einen Stalker im Wald“ -> Stimmung, Subreddits, Stichwörter (de + en)."""
    text = description.strip()
    subreddit = re.search(r"\br/([A-Za-z0-9_]{2,21})", text)
    mood = mood_from_words(text) or DEFAULT_MOOD
    keywords = []
    for token in _tokens(re.sub(r"\br/[A-Za-z0-9_]+", " ", text)):
        if token in STOPWORDS or len(token) < 3 or token.startswith(GENERIC_MOOD_WORDS):
            continue
        english = DE_EN.get(token) or DE_EN.get(token.rstrip("ns")) or token
        for word in (english, token):            # englisch für englische Storys, deutsch für deutsche
            if word not in keywords:
                keywords.append(word)
    return {
        "mood": mood,
        "subreddits": [subreddit.group(1)] if subreddit else subreddits_for(mood, lang),
        "keywords": keywords[:8],
        "description": text,
    }


SUBREDDIT_MOOD = {sub.lower(): key for key, mood in MOODS.items() for sub in mood["subreddits"]}


def detect_mood(subreddit: str, title: str, text: str) -> str:
    """Stimmung einer konkreten Story: zuerst über den Subreddit, sonst über typische Wörter."""
    tokens = _tokens(f"{title} {title} {text[:4000]}")
    scores = {key: sum(1 for t in tokens for s in mood["signals"] if t.startswith(s)) for key, mood in MOODS.items()}
    by_sub = SUBREDDIT_MOOD.get((subreddit or "").lower())
    if by_sub and by_sub != "suspense":       # gemischte Subreddits (Spannung) entscheiden über die Wörter
        return by_sub
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else (by_sub or DEFAULT_MOOD)


def voice_for(mood: str, lang: str) -> tuple[str, str, str]:
    return MOODS[mood]["voice"][lang]


WORDS_PER_SECOND = {"de": 2.25, "en": 2.55}      # gesprochen bei normalem Tempo (edge-tts)
WORDS_PER_SENTENCE = 14


def rate_factor(rate: str) -> float:
    match = re.match(r"([+-]\d+)%", rate or "+0%")
    return 1 + int(match.group(1)) / 100 if match else 1.0


def seconds_per_word(mood: str, lang: str) -> float:
    """Sprechdauer pro Wort inkl. Satzpausen – Grusel wird langsamer erzählt als ein lustiger Fail."""
    _, rate, _ = MOODS[mood]["voice"][lang]
    return 1 / (WORDS_PER_SECOND[lang] * rate_factor(rate)) + MOODS[mood]["pause"] * 0.8 / WORDS_PER_SENTENCE
