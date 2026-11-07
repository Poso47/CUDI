"""Clip-Engine: Podcast-/Streamer-Clips im Hochformat (1080x1920) mit Hook, Sprecher-Zuschnitt und Untertiteln.

Ablauf (siehe `pipeline.make_clip`): Quelle -> Spracherkennung (faster-whisper) -> Höhepunkt/Hook (Regeln, keine KI)
-> Pausen schneiden -> Sprecher-Zuschnitt 9:16 -> ASS-Untertitel -> Render.
"""


class ClipError(RuntimeError):
    """Fehler mit verständlicher Meldung für den Nutzer."""


W, H, FPS = 1080, 1920, 30
MAX_SECONDS = 179
