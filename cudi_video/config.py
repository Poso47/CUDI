"""Zentrale Einstellungen. Alles lässt sich über Umgebungsvariablen überschreiben."""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent

OUTPUT_DIR = Path(os.environ.get("CUDI_VIDEO_OUTPUT", PROJECT_DIR / "video_output"))
CACHE_DIR = Path(os.environ.get("CUDI_VIDEO_CACHE", PROJECT_DIR / ".video_cache"))
PRESETS_DIR = Path(os.environ.get("CUDI_VIDEO_PRESETS", PROJECT_DIR / "presets"))
ASSETS_DIR = Path(os.environ.get("CUDI_VIDEO_ASSETS", PROJECT_DIR / "video_assets"))


def new_output_folder(name: str) -> Path:
    """Eigener Ausgabeordner je Lauf: <Zeitstempel>_<name>, bei Gleichstand <name>-2, -3 …

    mkdir ohne exist_ok ist atomar: zwei gleichzeitige Läufe (CLI und Web-App, zwei Fenster)
    bekommen nie denselben Ordner und überschreiben sich nicht gegenseitig.
    """
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for n in range(1, 1000):
        folder = OUTPUT_DIR / (f"{stamp}_{name}" if n == 1 else f"{stamp}_{name}-{n}")
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            continue
    raise RuntimeError(f"Kein freier Ausgabeordner für {name} in {OUTPUT_DIR}")

# Wikimedia verlangt einen aussagekräftigen User-Agent mit Kontaktmöglichkeit.
USER_AGENT = os.environ.get(
    "CUDI_VIDEO_USER_AGENT",
    "CUDI-Video/0.1 (https://github.com/poso47/cudi; video research bot)",
)

# Video
WIDTH = 1080
HEIGHT = 1920
FPS = int(os.environ.get("CUDI_VIDEO_FPS", "30"))
_CPUS = os.cpu_count() or 2
# Bei vielen Kernen einen für System/ffmpeg frei lassen, bei 1–2 Kernen alle nutzen.
RENDER_WORKERS = int(os.environ.get("CUDI_VIDEO_WORKERS", str(_CPUS - 1 if _CPUS > 2 else _CPUS)))

# Stimmen (edge-tts, kostenlos). Auswahl: `edge-tts --list-voices`
VOICES = {
    "de": os.environ.get("CUDI_VOICE_DE", "de-DE-ConradNeural"),
    "en": os.environ.get("CUDI_VOICE_EN", "en-US-AndrewNeural"),
}
VOICE_RATE = os.environ.get("CUDI_VOICE_RATE", "+8%")

# Optionales Sprachmodell (OpenAI-kompatibel: Gemini, Groq, Ollama, ...).
# Ohne Schlüssel arbeitet der Generator rein mit belegten Textbausteinen.
LLM_BASE_URL = os.environ.get("CUDI_LLM_BASE_URL", "")
LLM_API_KEY = os.environ.get("CUDI_LLM_API_KEY", "")
LLM_MODEL = os.environ.get("CUDI_LLM_MODEL", "")

# Kanal-Name, z. B. "@cudi.fakten" – erscheint dezent oben im Video und im Abspann.
CHANNEL = os.environ.get("CUDI_CHANNEL", "").strip()

# Zugangsschutz für die Web-Oberfläche (wichtig in der Cloud).
WEB_TOKEN = os.environ.get("CUDI_VIDEO_TOKEN", "")

SUPPORTED_LANGS = ("de", "en")

# Quellen-Abgleich: Wikipedia-Sprachversionen aus verschiedenen Weltregionen.
CHECK_LANGS = [l for l in os.environ.get("CUDI_CHECK_LANGS", "en,de,fr,es,ru,ar,zh,ja").split(",") if l]
OVERPASS_URL = os.environ.get("CUDI_OVERPASS_URL", "https://overpass-api.de/api/interpreter")
FACTCHECK_API_KEY = os.environ.get("CUDI_FACTCHECK_API_KEY", "")   # Google Fact Check Tools (kostenlos)

# Reddit-Storys
# Reddit-Zugang (kostenlos, https://www.reddit.com/prefs/apps -> "script"-App). Ohne Zugang wird das
# öffentliche Reddit und als Ausweichweg das Archiv Arctic Shift genutzt.
REDDIT_CLIENT_ID = os.environ.get("CUDI_REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("CUDI_REDDIT_CLIENT_SECRET", "")
# Stockvideos (kostenlose Schlüssel): https://www.pexels.com/api/ und https://pixabay.com/api/docs/
PEXELS_API_KEY = os.environ.get("CUDI_PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.environ.get("CUDI_PIXABAY_API_KEY", "")
# KI-Bilder (Pollinations): ohne Zugang klein (576×1024) mit Logo und nur ein Bild gleichzeitig; mit kostenlosem
# Zugang (https://auth.pollinations.ai) groß und ohne Logo.
POLLINATIONS_TOKEN = os.environ.get("CUDI_POLLINATIONS_TOKEN", "")
# Übersetzung englischer Storys für deutsche Videos (DeepL API Free: 500.000 Zeichen/Monat kostenlos)
DEEPL_API_KEY = os.environ.get("CUDI_DEEPL_API_KEY", "")
STORY_MAX_SECONDS = float(os.environ.get("CUDI_STORY_MAX_SECONDS", "179"))   # je Teil (YouTube Shorts: 3 min)
