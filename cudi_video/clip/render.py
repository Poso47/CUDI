"""Render: Einzelschnitte (Zuschnitt + Skalierung), Audio-Schnitt, Untertitel einbrennen, H.264/AAC 30 fps."""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import FPS, H, MAX_SECONDS, W, ClipError
from .cuts import Schnitt
from .reframe import Analyse, zuschnitt


def _ffmpeg(args: list[str], cwd: Path | None = None) -> None:
    res = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y"] + args, capture_output=True, text=True, cwd=cwd)
    if res.returncode != 0:
        raise ClipError("ffmpeg-Fehler: " + (res.stderr or "")[-400:])


def _schnitt_filter(s: Schnitt, an: Analyse) -> str:
    x, y, w, h = zuschnitt(an, s.person, s.a, s.b, s.zoom)
    f = f"fps={FPS},crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos"
    if s.punch:
        d = max(s.frames / FPS, 0.5)
        k = f"(1+0.12*min(t/{d:.3f},1))"
        f += f",scale=w='{W}*{k}':h='{H}*{k}':eval=frame,crop={W}:{H}"
    if s.art == "blitz":
        f += ",fade=t=in:s=0:n=3:color=white"
    return f + ",format=yuv420p"


def _render_schnitt(i: int, s: Schnitt, video: Path, an: Analyse, ordner: Path) -> Path:
    ziel = ordner / f"s{i:03d}.mp4"
    _ffmpeg(["-ss", f"{s.a:.3f}", "-i", str(video), "-frames:v", str(s.frames), "-an", "-vf", _schnitt_filter(s, an),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-r", str(FPS), "-pix_fmt", "yuv420p", str(ziel)])
    return ziel


def audio_stuecke(schnitte: list[Schnitt]) -> list[tuple[str, float, float]]:
    """Zusammenhängende Quellbereiche ("quelle", a, b) bzw. Stille ("stille", 0, dauer) in Ausgabereihenfolge."""
    out: list[tuple[str, float, float]] = []
    for s in schnitte:
        if s.art == "blitz":
            out.append(("stille", 0.0, s.frames / FPS))
        elif out and out[-1][0] == "quelle" and abs(out[-1][2] - s.a) < 1e-4:
            out[-1] = ("quelle", out[-1][1], s.b)
        else:
            out.append(("quelle", s.a, s.b))
    return out


def audio_bauen(video: Path, schnitte: list[Schnitt], ziel: Path, arbeit: Path) -> None:
    teile, labels = [], []
    for i, (art, a, b) in enumerate(audio_stuecke(schnitte)):
        if art == "stille":
            teile.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
        else:
            d = b - a
            teile.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
                         f"aformat=sample_rates=44100:channel_layouts=stereo,"
                         f"afade=t=in:d=0.012,afade=t=out:st={max(d - 0.012, 0):.3f}:d=0.012[a{i}]")
        labels.append(f"[a{i}]")
    teile.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1[aus]")
    skript = arbeit / "audio.filter"
    skript.write_text(";\n".join(teile), "utf-8")
    _ffmpeg(["-i", str(video), "-filter_complex_script", str(skript), "-map", "[aus]", "-c:a", "pcm_s16le", str(ziel)])


def rendern(video: Path, schnitte: list[Schnitt], an: Analyse, ass: Path | None, fontsdir: Path | None,
            arbeit: Path, ziel: Path) -> float:
    """Erzeugt `ziel` (clip.mp4) und gibt die Dauer in Sekunden zurück."""
    teile = arbeit / "schnitte"
    teile.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, min(4, os.cpu_count() or 2))) as pool:
        dateien = list(pool.map(lambda p: _render_schnitt(p[0], p[1], video, an, teile), enumerate(schnitte)))
    liste = arbeit / "concat.txt"
    liste.write_text("".join(f"file '{d.resolve()}'\n" for d in dateien), "utf-8")
    roh = arbeit / "video_roh.mp4"
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", str(liste), "-c", "copy", str(roh)])
    wav = arbeit / "audio.wav"
    audio_bauen(video, schnitte, wav, arbeit)
    frames = sum(s.frames for s in schnitte)
    dauer = min(frames / FPS, MAX_SECONDS)
    vf = "null"
    if ass is not None:
        vf = f"ass={ass.name}" + (f":fontsdir={fontsdir.name}" if fontsdir else "")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(["-i", str(roh.resolve()), "-i", str(wav.resolve()), "-vf", vf, "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
             "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS),
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-t", f"{dauer:.3f}",
             "-movflags", "+faststart", str(ziel.resolve())], cwd=arbeit)
    return dauer
