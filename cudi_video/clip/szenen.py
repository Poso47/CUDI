"""Harte Bildschnitte erkennen (Episoden-Grenzen).

Reaction- und Best-of-Videos bestehen aus Episoden: jeder gezeigte Clip beginnt mit einem Schnitt. Ein guter
Kurzclip ist genau eine Episode – er beginnt am Schnitt und hört vor dem nächsten auf. Idee aus dem privaten
Clipper des Nutzers, hier mit ffmpeg-Szenenerkennung und Zwischenspeicher neu geschrieben.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

SCHWELLE = 0.35      # ffmpeg-Szenenwert; darunter sind es Kameraschwenks, keine Schnitte


def erkenne(video: Path, arbeit: Path, schwelle: float = SCHWELLE) -> list[float]:
    """Zeitpunkte harter Schnitte (Sekunden); zwischengespeichert als szenen.json. Bei Fehler leere Liste."""
    cache = arbeit / "szenen.json"
    try:
        return json.loads(cache.read_text("utf-8"))
    except (OSError, ValueError):
        pass
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(video), "-an", "-vf",
           f"fps=5,scale=160:-2,select='gt(scene,{schwelle})',metadata=print", "-f", "null", "-"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=600)
    except (OSError, subprocess.SubprocessError):
        return []
    schnitte = sorted({round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", res.stderr)})
    try:
        arbeit.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(schnitte), "utf-8")
    except OSError:
        pass
    return schnitte
