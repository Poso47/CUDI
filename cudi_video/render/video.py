"""Szenen parallel rendern, Tonspur mischen, alles zu einem MP4 zusammensetzen."""

from __future__ import annotations

import logging
import subprocess
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .. import config
from ..models import Research, Script
from ..script import extras_lines, format_date
from ..spec import VideoSpec
from ..units import quantity

log = logging.getLogger(__name__)

SAMPLE_RATE = 48_000
LEAD = {"intro": 0.25, "item": 0.45, "outro": 0.35}   # Pause vor dem Sprechen (Animation startet)
TAIL = {"intro": 0.35, "item": 0.55, "outro": 1.6}    # Pause danach


def _short_credit(credit: str | None) -> str | None:
    if not credit:
        return None
    artist, license_name = (credit.split(" – ") + ["", ""])[:2]
    return f"{artist} ({license_name})" if license_name else artist


def build_jobs(spec: VideoSpec, research: Research, script: Script, work: Path) -> list[dict]:
    lang = script.lang
    items = {it.rank: it for it in research.items}
    displays = [quantity(it.value, it.unit, spec.unit).value for it in research.items]
    max_display = max((abs(v) for v in displays), default=1.0)
    top = items.get(1)
    rows = [(it.rank, it.labels[lang], quantity(it.value, it.unit, spec.unit).display(lang))
            for it in sorted(research.items, key=lambda i: i.rank)]
    sources = "Wikidata · Wikipedia" + (" · Wikimedia Commons" if any(i.image_path for i in research.items) else "")
    as_of = format_date(research.fetched_at[:10], lang)
    sources_line = (f"Quellen: {sources} · Abgerufen am {as_of}" if lang == "de"
                    else f"Sources: {sources} · Retrieved {as_of}")

    jobs = []
    for i, seg in enumerate(script.segments):
        lead, tail = LEAD[seg.kind], TAIL[seg.kind]
        frames = int(round((lead + seg.duration + tail) * config.FPS))
        job = {
            "index": i, "kind": seg.kind, "lang": lang, "title": script.title,
            "text": seg.text, "words": seg.words, "lead": lead,
            "frames": frames, "duration": frames / config.FPS, "fps": config.FPS,
            "n_items": len(research.items), "max_display": max_display,
            "out": str(work / f"part_{i:02d}.mp4"),
        }
        if seg.kind == "intro" and top:
            job["intro"] = {"si_value": top.value, "unit": top.unit, "wanted": spec.unit}
        elif seg.kind == "item":
            it = items[seg.rank]
            job["item"] = {
                "rank": it.rank, "name": it.labels[lang],
                "si_value": it.value, "unit": it.unit, "wanted": spec.unit,
                "value_label": spec.value_label.get(lang, ""),
                "as_of": it.value_date[:4] if it.value_date else None,
                "extras": extras_lines(spec, it, lang),
                "image_path": it.image_path, "credit_short": _short_credit(it.image_credit),
            }
        elif seg.kind == "outro":
            job["outro"] = {"rows": rows, "sources_line": sources_line}
        jobs.append(job)
    return jobs


def render_part(job: dict) -> str:
    """Wird in einem eigenen Prozess ausgeführt: Szene Bild für Bild an ffmpeg übergeben."""
    from .scenes import make_scene

    scene = make_scene(job)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{config.WIDTH}x{config.HEIGHT}", "-r", str(job["fps"]),
        "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-g", str(job["fps"] * 2),
        job["out"],
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for n in range(job["frames"]):
            frame = scene.frame(n / job["fps"])
            proc.stdin.write(frame.convert("RGB").tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg-Fehler bei Szene {job['index']}")
    return job["out"]


def render_frame(job: dict, t: float, path: Path) -> None:
    from .scenes import make_scene

    make_scene(job).frame(t).convert("RGB").save(path, quality=92)


# --------------------------------------------------------------------------- Audio

def _decode(path: str) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def _whoosh(seconds: float = 0.45) -> np.ndarray:
    """Synthetischer Übergangs-Sound (rauschbasiert, lizenzfrei)."""
    n = int(SAMPLE_RATE * seconds)
    rng = np.random.default_rng(3)
    noise = rng.standard_normal(n).astype(np.float32)
    # einfacher Tiefpass mit wanderndem Koeffizienten -> "Wusch"
    out = np.zeros(n, dtype=np.float32)
    acc = 0.0
    for i in range(n):
        p = i / n
        a = 0.04 + 0.5 * np.sin(np.pi * p) ** 2
        acc += a * (noise[i] - acc)
        out[i] = acc
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5
    out *= env
    return out / (np.abs(out).max() + 1e-9) * 0.22


def _music_track(length: int) -> np.ndarray | None:
    music_dir = config.ASSETS_DIR / "music"
    files = sorted(music_dir.glob("*.mp3")) + sorted(music_dir.glob("*.wav")) if music_dir.exists() else []
    if not files:
        return None
    track = _decode(str(files[0]))
    if len(track) == 0:
        return None
    reps = int(np.ceil(length / len(track)))
    return np.tile(track, reps)[:length]


def build_audio(script: Script, jobs: list[dict], out_path: Path) -> None:
    total = int(sum(j["duration"] for j in jobs) * SAMPLE_RATE) + SAMPLE_RATE
    voice = np.zeros(total, dtype=np.float32)
    fx = np.zeros(total, dtype=np.float32)
    whoosh = _whoosh()
    t = 0.0
    for job, seg in zip(jobs, script.segments):
        start = int((t + job["lead"]) * SAMPLE_RATE)
        clip = _decode(seg.audio_path)
        voice[start:start + len(clip)] += clip[: max(0, total - start)]
        if job["index"] > 0:
            s = int(t * SAMPLE_RATE)
            fx[s:s + len(whoosh)] += whoosh[: max(0, total - s)]
        t += job["duration"]
    mix = voice + fx
    music = _music_track(total)
    if music is not None:
        # Musik leiser, während gesprochen wird ("Ducking").
        env = np.convolve(np.abs(voice), np.ones(4800) / 4800, mode="same")
        duck = np.where(env > 0.01, 0.35, 1.0).astype(np.float32)
        duck = np.convolve(duck, np.ones(9600) / 9600, mode="same")
        mix += music / (np.abs(music).max() + 1e-9) * 0.16 * duck
    peak = np.abs(mix).max() or 1.0
    mix = mix / peak * 0.89
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())


# --------------------------------------------------------------------------- Untertitel-Datei

def _srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def write_srt(script: Script, jobs: list[dict], path: Path, words_per_cue: int = 6) -> None:
    cues, t = [], 0.0
    for job, seg in zip(jobs, script.segments):
        offset = t + job["lead"]
        words = seg.words
        for i in range(0, len(words), words_per_cue):
            group = words[i:i + words_per_cue]
            cues.append((offset + group[0]["start"], offset + group[-1]["end"], " ".join(w["text"] for w in group)))
        t += job["duration"]
    lines = []
    for n, (a, b, text) in enumerate(cues, start=1):
        lines += [str(n), f"{_srt_time(a)} --> {_srt_time(b)}", text, ""]
    path.write_text("\n".join(lines), "utf-8")


# --------------------------------------------------------------------------- Gesamt

def render_video(spec: VideoSpec, research: Research, script: Script, out_dir: Path, progress_cb=None) -> dict:
    work = out_dir / f"work_{script.lang}"
    work.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(spec, research, script, work)

    done = 0
    with ProcessPoolExecutor(max_workers=config.RENDER_WORKERS) as pool:
        for _ in pool.map(render_part, jobs):
            done += 1
            if progress_cb:
                progress_cb(done / len(jobs))

    concat_list = work / "parts.txt"
    concat_list.write_text("".join(f"file '{Path(j['out']).name}'\n" for j in jobs), "utf-8")
    video_only = work / "video_only.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                    "-c", "copy", str(video_only)], check=True)

    audio = work / "audio.wav"
    build_audio(script, jobs, audio)

    final = out_dir / f"{spec.id}_{script.lang}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video_only), "-i", str(audio),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                    str(final)], check=True)

    cover = out_dir / f"{spec.id}_{script.lang}_cover.jpg"
    render_frame(jobs[0], min(2.2, jobs[0]["duration"] - 0.1), cover)
    srt = out_dir / f"{spec.id}_{script.lang}.srt"
    write_srt(script, jobs, srt)
    return {
        "video": final.name, "cover": cover.name, "subtitles": srt.name,
        "duration": round(sum(j["duration"] for j in jobs), 1),
    }
