"""Endkontrolle vor der Auslieferung: schwarze Stellen, Standbilder, Lautheit, Dauer, Auflösung, Safe-Zones, Sync.

Befunde sind Hinweise (nie Abbruch). Nur die Lautheit wird – genau einmal – automatisch korrigiert (loudnorm
zweistufig, nur die Tonspur, das Bild wird nicht neu gerendert).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

TARGET_LUFS = -14.0
LUFS_TOLERANCE = 1.0
MAX_TRUE_PEAK = -1.0
BLACK_MIN = 0.5            # s
BLACK_EDGE = 0.6           # s: Blenden am Anfang/Ende sind gewollt
FREEZE_MIN = 3.0           # s (nur Ranking/Fakten)
SYNC_MAX = 0.25            # s Unterschied Bild/Ton
UI_BOTTOM = 0.20           # TikTok/Shorts: unten ca. 20 % verdeckt
UI_RIGHT = 0.12            # rechts ca. 12 %
BOX_TOLERANCE = 24         # px


def _run(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def probe(path: Path) -> dict:
    """Breite, Höhe, Dauer von Bild und Ton."""
    out = _run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration",
                "-show_entries", "format=duration", "-of", "json", str(path)])
    data = json.loads(out.stdout or "{}")
    info = {"breite": 0, "hoehe": 0, "dauer": float(data.get("format", {}).get("duration") or 0.0),
            "bild_dauer": None, "ton_dauer": None}
    for st in data.get("streams", []):
        dur = float(st["duration"]) if st.get("duration") not in (None, "N/A") else None
        if st.get("codec_type") == "video":
            info["breite"], info["hoehe"], info["bild_dauer"] = st.get("width", 0), st.get("height", 0), dur
        elif st.get("codec_type") == "audio":
            info["ton_dauer"] = dur
    return info


def measure_loudness(path: Path) -> dict:
    """Integrierte Lautheit (LUFS) und True Peak (dBTP) über ebur128."""
    err = _run(["ffmpeg", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    summary = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    lufs = re.search(r"\bI:\s+(-?[\d.]+|-inf)\s+LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[\d.]+|-inf)\s+dBFS", summary)
    num = lambda m: float(m.group(1)) if m and m.group(1) != "-inf" else None   # noqa: E731
    return {"lufs": num(lufs), "true_peak": num(peak)}


def detect_video_faults(path: Path) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """(schwarze Abschnitte, Standbilder) mit Start/Ende in Sekunden – ein Durchlauf."""
    err = _run(["ffmpeg", "-nostats", "-i", str(path), "-an", "-vf",
                f"blackdetect=d={BLACK_MIN}:pix_th=0.10,freezedetect=n=-60dB:d={FREEZE_MIN}", "-f", "null", "-"]).stderr
    black = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+)\s+black_end:([\d.]+)", err)]
    starts = [float(x) for x in re.findall(r"freeze_start:\s*([\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"freeze_end:\s*([\d.]+)", err)]
    total = probe(path)["dauer"]
    freeze = [(s, ends[i] if i < len(ends) else total) for i, s in enumerate(starts)]
    return black, freeze


def layout_findings(boxes: dict[str, tuple[float, float, float, float]] | None = None) -> list[str]:
    """Texte in den UI-Zonen von TikTok/Shorts? Boxen (x0, y0, x1, y1) aus den Render-Konstanten; kein OCR nötig."""
    from .render import theme as T
    if boxes is None:
        boxes = {
            "Untertitel": (T.X0 + 60, T.SUB_Y - 100, T.X0 + T.CONTENT_W - 60, T.SUB_Y + 100),
            "Inhaltsspalte": (T.X0, 0, T.X0 + T.CONTENT_W, T.SUB_Y + 100),
        }
    zone_y, zone_x = T.H * (1 - UI_BOTTOM), T.W * (1 - UI_RIGHT)
    found = []
    for name, (x0, y0, x1, y1) in boxes.items():
        if y1 > zone_y + BOX_TOLERANCE:
            found.append(f"{name} ragt in die untere Bedienzone (ab y={zone_y:.0f}).")
        if x1 > zone_x + BOX_TOLERANCE:
            found.append(f"{name} ragt in die rechte Bedienzone (ab x={zone_x:.0f}).")
    return found


def loudness_ok(m: dict) -> bool:
    return (m["lufs"] is not None and abs(m["lufs"] - TARGET_LUFS) <= LUFS_TOLERANCE
            and (m["true_peak"] is None or m["true_peak"] <= MAX_TRUE_PEAK))


def loudnorm_filter(audio: Path) -> str:
    """Zweistufiges (lineares) loudnorm-Filter für eine Tonspur – gemessen wird nur der Ton (Sekunden), so liegt die
    Lautheit schon beim ersten Muxen im Ziel und qa muss das Video nicht noch einmal anfassen. Ausfall: einstufig wie bisher."""
    single = f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11"
    try:
        first = _run(["ffmpeg", "-nostats", "-i", str(audio), "-vn", "-af", single + ":print_format=json", "-f", "null", "-"]).stderr
        blob = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", first, re.S)
        if not blob:
            return single
        m = json.loads(blob.group(0))
        return (f"{single}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
                f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    except Exception:  # noqa: BLE001 - Messung ist nur Optimierung
        return single


def normalize_loudness(path: Path) -> bool:
    """Zweistufiges loudnorm nur auf die Tonspur; ersetzt die Datei. True bei Erfolg."""
    first = _run(["ffmpeg", "-nostats", "-i", str(path), "-vn", "-af",
                  f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    blob = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", first, re.S)
    if not blob:
        return False
    m = json.loads(blob.group(0))
    af = (f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    tmp = path.with_name(path.stem + "_ln" + path.suffix)
    done = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-af", af, "-ar", "48000", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)])
    if done.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        return False
    os.replace(tmp, path)
    return True


def check(path: Path, kind: str = "", max_seconds: float | None = None, fix: bool = True) -> dict:
    """Prüft ein fertiges MP4, korrigiert die Lautheit höchstens einmal und liefert den qa-Block."""
    path = Path(path)
    limit = max_seconds or config.STORY_MAX_SECONDS
    info = probe(path)
    befunde: list[str] = []
    qa = {"ok": True, "dauer": round(info["dauer"], 1), "aufloesung": f"{info['breite']}x{info['hoehe']}",
          "lufs_vor": None, "lufs_nach": None, "true_peak": None, "korrigiert": False,
          "schwarz": [], "standbild": [], "befunde": befunde}

    if (info["breite"], info["hoehe"]) != (config.WIDTH, config.HEIGHT):
        befunde.append(f"Auflösung {info['breite']}x{info['hoehe']} statt {config.WIDTH}x{config.HEIGHT}.")
    if info["dauer"] > limit + 0.5:
        befunde.append(f"Dauer {info['dauer']:.0f} s überschreitet die Grenze von {limit:.0f} s.")
    if info["bild_dauer"] and info["ton_dauer"] and abs(info["bild_dauer"] - info["ton_dauer"]) > SYNC_MAX:
        befunde.append(f"Bild ({info['bild_dauer']:.2f} s) und Ton ({info['ton_dauer']:.2f} s) laufen auseinander.")

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:        # Tempo: Bildprüfung und Lautheitsmessung laufen gleichzeitig
        loud_job = pool.submit(measure_loudness, path)
        black, freeze = detect_video_faults(path)
        m = loud_job.result()
    qa["schwarz"] = [[round(a, 1), round(b, 1)] for a, b in black
                     if a > BLACK_EDGE and b < info["dauer"] - BLACK_EDGE]
    if qa["schwarz"]:
        befunde.append("Schwarze Stelle(n) bei " + ", ".join(f"{a}–{b} s" for a, b in qa["schwarz"]) + ".")
    if kind in ("ranking", "numbers", "facts", "fakten"):
        qa["standbild"] = [[round(a, 1), round(b, 1)] for a, b in freeze]
        if qa["standbild"]:
            befunde.append("Standbild über 3 s bei " + ", ".join(f"{a}–{b} s" for a, b in qa["standbild"]) + ".")
    befunde.extend(layout_findings())

    qa["lufs_vor"], qa["true_peak"] = m["lufs"], m["true_peak"]
    if m["lufs"] is None:
        befunde.append("Lautheit nicht messbar (keine Tonspur?).")
    elif not loudness_ok(m):
        if fix and normalize_loudness(path):
            qa["korrigiert"] = True
            m2 = measure_loudness(path)
            qa["lufs_nach"], qa["true_peak"] = m2["lufs"], m2["true_peak"]
            if not loudness_ok(m2):
                befunde.append(f"Lautheit nach Korrektur {m2['lufs']} LUFS (Ziel {TARGET_LUFS:.0f}).")
        else:
            befunde.append(f"Lautheit {m['lufs']} LUFS weicht vom Ziel {TARGET_LUFS:.0f} ab.")
    if not qa["korrigiert"]:
        qa["lufs_nach"] = m["lufs"]
    qa["ok"] = not befunde
    return qa


def safe_check(path: Path, kind: str = "", max_seconds: float | None = None) -> dict | None:
    """Wie check(), aber nie ein Abbruch: Fehler der Prüfung selbst werden nur protokolliert."""
    try:
        return check(path, kind, max_seconds)
    except Exception as exc:  # noqa: BLE001 - Endkontrolle darf die Auslieferung nie verhindern
        log.warning("Endkontrolle fehlgeschlagen: %s", exc)
        return None
