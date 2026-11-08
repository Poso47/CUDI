"""Erklärvideo rendern: Stimme (Wortzeiten) → Szenen als eigene Prozesse → Ton → fertiges MP4."""

from __future__ import annotations

import subprocess
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .. import config
from ..render import audio, video
from ..tts import voice_texts

# Sprechprofil „erklaer“: ruhig, etwas tiefer und langsamer, längere Atempausen als bei Rankings
PROFILE = {"rate": "-6%", "pitch": "-2Hz", "pause": 0.5}
LEAD, TAIL = 0.7, 0.9
STYLE = {"name": "manuskript", "format": "manuskript", "motion": "gleiten"}


def voice_name(lang: str) -> str:
    return config.VOICES.get(lang, config.VOICES["de"])


def build_jobs(script: dict, voiced: list[tuple[Path, list[dict], float]], work: Path) -> list[dict]:
    jobs = []
    for i, (sz, (wav, words, dur)) in enumerate(zip(script["szenen"], voiced)):
        frames = int(round((LEAD + dur + TAIL) * config.FPS))
        jobs.append({
            "index": i, "kind": "erklaer", "lang": script["sprache"], "title": script["titel"], "text": sz["text"],
            "words": words, "lead": LEAD, "voice_dur": dur, "frames": frames, "duration": frames / config.FPS,
            "fps": config.FPS, "n_items": len(script["szenen"]), "channel": "", "voice_path": str(wav), "mascot": False,
            "out": str(work / f"part_{i:02d}.mp4"), "style": STYLE, "szene": sz,
        })
    return jobs


def build_audio(jobs: list[dict], path: Path, music_style: str | None = None, seed_key: str = "") -> None:
    """Nur Stimme (kein Übergangs-Rauschen: die Szenen blenden weich ineinander)."""
    rate = video.SAMPLE_RATE
    total = int(sum(j["duration"] for j in jobs) * rate) + rate
    track = np.zeros(total, dtype=np.float32)
    t = 0.0
    for job in jobs:
        clip = video._decode(job["voice_path"])
        s = int((t + job["lead"]) * rate)
        track[s:s + len(clip)] += clip[: max(0, total - s)]
        t += job["duration"]
    if music_style is not None and audio.enabled():
        music = video._music_track(total)
        if music is None:
            music = audio.generate_music(music_style, total / rate, path.parent, seed_key, video._decode)
        track += audio.mix_music(track, music)
    track = track / (np.abs(track).max() or 1.0) * 0.89
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(track, -1, 1) * 32767).astype(np.int16).tobytes())


def render_erklaerung(script: dict, out_dir: Path | None = None, progress=None) -> dict:
    """Skript (validiert) -> Video. Gibt {"video", "cover", "duration", "folder"} zurück."""
    out_dir = out_dir or config.new_output_folder(script["id"])
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    texts = [sz["text"] for sz in script["szenen"]]
    voiced = voice_texts(texts, work / "audio", voice_name(script["sprache"]), PROFILE["rate"], PROFILE["pitch"],
                         PROFILE["pause"])
    jobs = build_jobs(script, voiced, work)
    done = 0
    with ProcessPoolExecutor(max_workers=config.RENDER_WORKERS) as pool:
        for _ in pool.map(video.render_part, jobs):
            done += 1
            if progress:
                progress(done / len(jobs))
    concat = work / "parts.txt"
    concat.write_text("".join(f"file '{Path(j['out']).name}'\n" for j in jobs), "utf-8")
    silent = work / "video_only.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy",
                    str(silent)], check=True)
    audio_file = work / "audio.wav"
    build_audio(jobs, audio_file, music_style=audio.music_style("erklaer", STYLE.get("format", "manuskript"), script["titel"]),
                seed_key=script["id"])
    final = out_dir / f"{script['id']}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(audio_file), "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", str(video.SAMPLE_RATE), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(final)], check=True)
    from .. import qa
    qa_block = qa.safe_check(final, "erklaer", config.STORY_MAX_SECONDS)
    cover = out_dir / f"{script['id']}_cover.jpg"
    try:                                                   # gestaltetes Cover (Titel, Look des Videos), sonst Standbild
        from ..render import cover as cover_mod
        cover_mod.make_cover(cover, headline=cover_mod.clean_title(script["titel"]), style=jobs[0]["style"],
                             lang=script["sprache"])
    except Exception:                                      # noqa: BLE001
        video.render_frame(jobs[0], min(2.5, jobs[0]["duration"] - 0.1), cover)
    return {"video": final.name, "cover": cover.name, "duration": round(sum(j["duration"] for j in jobs), 1),
            "folder": str(out_dir), "qa": qa_block}
