"""Zentrale Einstellungen. Alles lässt sich über Umgebungsvariablen überschreiben."""

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent

OUTPUT_DIR = Path(os.environ.get("CUDI_VIDEO_OUTPUT", PROJECT_DIR / "video_output"))
CACHE_DIR = Path(os.environ.get("CUDI_VIDEO_CACHE", PROJECT_DIR / ".video_cache"))
PRESETS_DIR = Path(os.environ.get("CUDI_VIDEO_PRESETS", PROJECT_DIR / "presets"))
ASSETS_DIR = Path(os.environ.get("CUDI_VIDEO_ASSETS", PROJECT_DIR / "video_assets"))

# Wikimedia verlangt einen aussagekräftigen User-Agent mit Kontaktmöglichkeit.
USER_AGENT = os.environ.get(
    "CUDI_VIDEO_USER_AGENT",
    "CUDI-Video/0.1 (https://github.com/poso47/cudi; video research bot)",
)

# Video
WIDTH = 1080
HEIGHT = 1920
FPS = int(os.environ.get("CUDI_VIDEO_FPS", "30"))
RENDER_WORKERS = int(os.environ.get("CUDI_VIDEO_WORKERS", str(max(1, (os.cpu_count() or 2) - 1))))

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

# Zugangsschutz für die Web-Oberfläche (wichtig in der Cloud).
WEB_TOKEN = os.environ.get("CUDI_VIDEO_TOKEN", "")

SUPPORTED_LANGS = ("de", "en")

# Quellen-Abgleich: Wikipedia-Sprachversionen aus verschiedenen Weltregionen.
CHECK_LANGS = [l for l in os.environ.get("CUDI_CHECK_LANGS", "fr,es,ru,ar,zh,ja").split(",") if l]
OVERPASS_URL = os.environ.get("CUDI_OVERPASS_URL", "https://overpass-api.de/api/interpreter")
FACTCHECK_API_KEY = os.environ.get("CUDI_FACTCHECK_API_KEY", "")   # Google Fact Check Tools (kostenlos)
