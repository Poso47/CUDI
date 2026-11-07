"""Clip-Engine: Podcast-/Streamer-Clips im Hochformat (1080x1920) mit Hook, Sprecher-Zuschnitt und Untertiteln.

Ablauf (siehe `pipeline.make_clip`): Quelle -> Spracherkennung (faster-whisper) -> Höhepunkt/Hook (Regeln, keine KI)
-> Pausen schneiden -> Sprecher-Zuschnitt 9:16 -> ASS-Untertitel -> Render.
"""


class ClipError(ValueError):
    """Fehler mit verständlicher Meldung für den Nutzer. `wiederholbar`: später nochmal versuchen sinnvoll
    (z. B. Download gesperrt) – steuert, ob der Auftragslauf einen zweiten Versuch macht."""

    def __init__(self, msg: str, wiederholbar: bool = False):
        super().__init__(msg)
        self.wiederholbar = wiederholbar


W, H, FPS = 1080, 1920, 30
MAX_SECONDS = 179
