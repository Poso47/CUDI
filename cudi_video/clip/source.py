"""Quelle: lokale Datei oder URL (yt-dlp)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from . import ClipError

_ENDUNGEN = (".mp4", ".mkv", ".webm", ".mov")


def ist_url(quelle: str) -> bool:
    return bool(re.match(r"^https?://", quelle.strip(), re.I))


def slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-._")
    return (s or "clip")[:60]


def beschaffen(quelle: str, arbeitsordner: Path) -> Path:
    """Gibt den Pfad der Videodatei zurück (lädt URLs nach `arbeitsordner`)."""
    arbeitsordner.mkdir(parents=True, exist_ok=True)
    if not ist_url(quelle):
        p = Path(quelle).expanduser()
        if not p.is_file():
            raise ClipError(f"Datei nicht gefunden: {quelle}")
        return p
    if not shutil.which("yt-dlp"):
        raise ClipError("yt-dlp ist nicht installiert (pip install yt-dlp) – oder eine lokale Datei angeben.")
    for alt in sorted(arbeitsordner.glob("quelle.*")):
        if alt.suffix in _ENDUNGEN:
            return alt
    cmd = ["yt-dlp", "--no-playlist", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4",
           "-o", str(arbeitsordner / "quelle.%(ext)s"), quelle]
    res = subprocess.run(cmd, capture_output=True, text=True)
    files = [f for f in arbeitsordner.glob("quelle.*") if f.suffix in _ENDUNGEN]
    if res.returncode != 0 or not files:
        err = (res.stderr or res.stdout or "").strip().splitlines()
        letzte = err[-1] if err else "unbekannter Fehler"
        hinweis = ""
        if re.search(r"sign in|bot|403|429|blocked|HTTP Error", res.stderr or "", re.I):
            hinweis = (" Hinweis: YouTube & Co. sperren Cloud-/Rechenzentrums-IPs oft – "
                       "Video lokal herunterladen und die Datei übergeben.")
        raise ClipError(f"Download fehlgeschlagen ({letzte[:200]}).{hinweis}")
    return files[0]
