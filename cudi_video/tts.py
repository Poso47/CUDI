"""KI-Stimme mit edge-tts (kostenlos) inklusive Wort-Zeitstempeln für die Untertitel.

Fällt der Gratis-Dienst aus, spricht Piper (quelloffen, offline, ebenfalls kostenlos) das ganze Video."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import ssl
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import edge_tts
import edge_tts.communicate

from . import config, net
from .models import Script

log = logging.getLogger(__name__)

# edge-tts nutzt fest das certifi-Bundle. Hinter Firmen-/Cloud-Proxys mit eigenem
# Zertifikat (SSL_CERT_FILE) muss dieses verwendet werden.
if os.environ.get("SSL_CERT_FILE"):
    edge_tts.communicate._SSL_CTX = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])

TICKS_PER_SECOND = 10_000_000  # edge-tts liefert Offsets in 100-ns-Einheiten


TTS_ATTEMPTS = 6        # der Gratis-Dienst liefert zeitweise „No audio was received“ – meist klappt es kurz danach


async def _synthesize(text: str, voice: str, out_path: Path, rate: str, pitch: str = "+0Hz",
                      volume: str = "+0%") -> list[dict]:
    words: list[dict] = []
    last = "keine Audiodaten"
    for attempt in range(TTS_ATTEMPTS):
        if attempt:
            await asyncio.sleep(min(2 ** attempt, 30))     # 2, 4, 8, 16, 30 s ≈ 1 Minute Geduld
        words.clear()
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume, boundary="WordBoundary")
            with open(out_path, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start = chunk["offset"] / TICKS_PER_SECOND
                        words.append({
                            "text": chunk["text"],
                            "start": round(start, 3),
                            "end": round(start + chunk["duration"] / TICKS_PER_SECOND, 3),
                        })
            if out_path.stat().st_size > 0:
                return words
            last = "keine Audiodaten"
        except Exception as exc:  # Netzwerk-/Dienstfehler -> erneut versuchen
            last = f"{type(exc).__name__}: {exc}"
            log.warning("TTS-Versuch %d fehlgeschlagen: %s", attempt + 1, exc)
    raise RuntimeError(f"Sprachausgabe fehlgeschlagen für: {text[:60]}… ({last[:160]})")


SAMPLE_RATE = 48_000
MAX_PAUSE = 0.28        # edge-tts pausiert nach jedem Punkt ~1 s – für Shorts zu langsam
SILENCE_RMS = 0.01      # ~ -40 dB


def tighten_pauses(mp3: Path, words: list[dict], wav: Path, max_pause: float = MAX_PAUSE) -> tuple[list[dict], float]:
    """Lange Pausen kürzen und die Wort-Zeitstempel entsprechend verschieben."""
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(mp3), "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True, check=True,
    ).stdout
    audio = np.frombuffer(raw, dtype=np.float32)
    win = SAMPLE_RATE // 100                                    # 10-ms-Fenster
    n_win = len(audio) // win
    rms = np.sqrt(np.mean(audio[: n_win * win].reshape(n_win, win) ** 2, axis=1))
    silent = rms < SILENCE_RMS
    keep = np.ones(len(audio), dtype=bool)
    cuts: list[tuple[float, float]] = []                       # (Zeitpunkt, entfernte Sekunden)
    max_win = int(max_pause * 100)
    i = 0
    while i < n_win:
        if silent[i]:
            j = i
            while j < n_win and silent[j]:
                j += 1
            if j - i > max_win and i > 0 and j < n_win:         # nur Pausen zwischen Wörtern
                a = (i + max_win // 2) * win
                b = (j - max_win // 2) * win
                keep[a:b] = False
                cuts.append((a / SAMPLE_RATE, (b - a) / SAMPLE_RATE))
            i = j
        else:
            i += 1

    def shift(t: float) -> float:
        return t - sum(removed for at, removed in cuts if at < t)

    new_words = [{**w, "start": round(shift(w["start"]), 3), "end": round(shift(w["end"]), 3)} for w in words]
    pcm = (np.clip(audio[keep], -1, 1) * 32767).astype(np.int16)
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())
    return new_words, len(pcm) / SAMPLE_RATE


# --------------------------------------------------------------------------- Ersatzstimme (Piper)
# Kostenlose, quelloffene Stimmen, die offline laufen (Modell einmalig von Hugging Face, ~60 MB).
# Ein Video bekommt dann durchgehend die Ersatzstimme – kein Stimmwechsel mitten im Video.
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
PIPER_VOICES = {("de", "m"): "de/de_DE/thorsten/medium/de_DE-thorsten-medium",
                ("de", "f"): "de/de_DE/kerstin/low/de_DE-kerstin-low",
                ("en", "m"): "en/en_US/ryan/medium/en_US-ryan-medium",
                ("en", "f"): "en/en_US/amy/medium/en_US-amy-medium"}
FEMALE_VOICES = ("amala", "katja", "seraphina", "aria", "emma", "ava", "jenny", "michelle", "sonia", "libby")
PUNCT = ".,!?;:…\"'„“”«»()–-"
NOTES: list[str] = []            # Hinweise fürs Ergebnis (z. B. Ersatzstimme) – abholen mit take_notes()
_piper_cache: dict = {}


def take_notes() -> list[str]:
    notes = list(dict.fromkeys(NOTES))
    NOTES.clear()
    return notes


def piper_key(edge_voice: str) -> tuple[str, str]:
    """Sprache und Geschlecht der edge-Stimme (z. B. de-DE-KatjaNeural -> ("de", "f"))."""
    lang = "de" if edge_voice.lower().startswith("de-") else "en"
    return lang, ("f" if edge_voice.split("-")[-1].lower().startswith(FEMALE_VOICES) else "m")


def _pip_install(package: str) -> None:
    for extra in ([], ["--break-system-packages"]):
        if subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", *extra,
                           package], capture_output=True).returncode == 0:
            return


def _piper_voice(key: tuple[str, str]):
    if key in _piper_cache:
        return _piper_cache[key]
    try:
        from piper import PiperVoice
    except ImportError:                                   # nur bei Bedarf installieren
        _pip_install("piper-tts")
        from piper import PiperVoice
    folder = config.OUTPUT_DIR / "_piper"
    folder.mkdir(parents=True, exist_ok=True)
    name = PIPER_VOICES[key]
    model = folder / (Path(name).name + ".onnx")
    for path, url in ((model, PIPER_BASE + name + ".onnx"),
                      (model.with_name(model.name + ".json"), PIPER_BASE + name + ".onnx.json")):
        if not path.exists() or path.stat().st_size < 1000:
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(net.get(url, timeout=300, retries=4).content)
            tmp.replace(path)
    _piper_cache[key] = PiperVoice.load(str(model))
    return _piper_cache[key]


def _piper_config(length_scale: float):
    from piper import SynthesisConfig
    return SynthesisConfig(length_scale=length_scale)


def _percent(value: str) -> float:
    m = re.match(r"\s*([+-]?\d+(?:\.\d+)?)\s*%", value or "")
    return float(m.group(1)) if m else 0.0


def piper_synthesize(text: str, edge_voice: str, out_wav: Path, rate: str = "+0%") -> list[dict]:
    """Text mit Piper vertonen. Wortzeiten: je Satz exakt, im Satz nach Wortlänge verteilt."""
    voice = _piper_voice(piper_key(edge_voice))
    cfg = _piper_config(min(2.0, max(0.5, 1.0 / (1.0 + _percent(rate) / 100))))
    sample_rate = voice.config.sample_rate
    pcm, words, t = [], [], 0.0
    for sentence in (s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s.strip()):
        audio = b"".join(c.audio_int16_bytes for c in voice.synthesize(sentence, syn_config=cfg))
        duration = len(audio) / 2 / sample_rate
        tokens = [w.strip(PUNCT) for w in sentence.split() if w.strip(PUNCT)]
        weights = [len(w) + 2 for w in tokens]
        total, pos = sum(weights) or 1, t
        for word, weight in zip(tokens, weights):
            part = duration * weight / total
            words.append({"text": word, "start": round(pos, 3), "end": round(pos + 0.9 * part, 3)})
            pos += part
        pcm.append(audio)
        t += duration
    if not pcm or not any(pcm):
        raise RuntimeError(f"Ersatzstimme lieferte nichts für: {text[:60]}…")
    with wave.open(str(out_wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(b"".join(pcm))
    return words


async def _speak_all(texts: list[str], out_dir: Path, voice: str, rate: str, pitch: str,
                     parallel: int = 2, prosody: list[tuple[str, str, str]] | None = None
                     ) -> list[tuple[Path, list[dict]]]:
    """Alle Texte mit edge-tts; liefert ein Text nichts, alle mit der Ersatzstimme (einheitlicher Klang).
    `prosody` (je Text: rate, pitch, volume) überschreibt die gemeinsamen Werte – für betonte Teilsätze."""
    sem = asyncio.Semaphore(parallel)

    async def one(i: int, text: str):
        async with sem:
            mp3 = out_dir / f"{i:03d}.mp3"
            if prosody is None:
                return mp3, await _synthesize(text, voice, mp3, rate, pitch)
            r, p, v = prosody[i]
            return mp3, await _synthesize(text, voice, mp3, r, p, v)

    tasks = [asyncio.create_task(one(i, t)) for i, t in enumerate(texts)]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    failed = next((t.exception() for t in done if t.exception() is not None), None)
    if failed is None:
        return [t.result() for t in tasks]
    for t in pending:                                       # Dienst ist aus: nicht auf jeden Abschnitt warten
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    log.warning("edge-tts liefert nichts (%s) – Ersatzstimme Piper für alle Abschnitte", failed)
    try:
        spoken = []
        for i, text in enumerate(texts):
            path = out_dir / f"{i:03d}.piper.wav"
            spoken.append((path, piper_synthesize(text, voice, path, prosody[i][0] if prosody else rate)))
    except Exception as exc:
        raise RuntimeError(f"Sprachausgabe fehlgeschlagen ({failed}); Ersatzstimme ebenfalls: "
                           f"{type(exc).__name__}: {exc}"[:400]) from exc
    NOTES.append("Ersatzstimme (Piper) verwendet: Der kostenlose Microsoft-Sprachdienst antwortete gerade nicht.")
    return spoken


# --------------------------------------------------------------------------- Betonung
# Spannung wird GESPROCHEN, nicht schneller gesprochen: Der Text wird in Teile geteilt (Satz, Teilsatz an „–“/„…“,
# Zahl- und „Platz“-Teil), jeder Teil bekommt Tempo, Tonhöhe und Lautstärke und vor den wichtigen Stellen eine kurze
# Spannungspause. Aus den Teilen wird mit echter Stille ein Abschnitt gebaut; die Wortzeiten wandern mit.
@dataclass
class Part:
    text: str
    rate: int = 0               # Prozentpunkte zum Grundtempo (negativ = langsamer)
    pitch: int = 0              # Hz relativ zur Stimme
    volume: int = 0             # Prozent
    pause: float = 0.0          # Stille davor (Sekunden)
    role: str = "normal"        # normal | hook | frage | platz | zahl | superlativ


PAUSE_SENTENCE = 0.20           # normaler Satzwechsel
PAUSE_AFTER_QUESTION = 0.45     # Zuhörer darf kurz raten
PAUSE_BEFORE_PLACE = 0.40       # vor „Platz 1“
PAUSE_BEFORE_NUMBER = 0.32      # vor der Zahl
PAUSE_BEFORE_SUPERLATIVE = 0.30
PAUSE_AFTER_BREAK = 0.35        # nach „–“ und „…“
ROLE_PROSODY = {                # (Tempo, Tonhöhe, Lautstärke) je Rolle
    "normal": (0, 0, 0),
    "hook": (-6, -3, 0),
    "frage": (-8, -4, 0),
    "platz": (-6, -2, 4),
    "zahl": (-9, -2, 6),
    "superlativ": (-5, -1, 3),
}
ABBREVIATIONS = ("ca.", "z. b.", "z.b.", "nr.", "bzw.", "d. h.", "usw.", "etc.", "mio.", "mrd.", "st.", "dr.", "vs.", "no.")
QUALIFIERS = {"rund", "etwa", "ungefähr", "ca.", "über", "mehr", "als", "genau", "knapp", "fast", "bis", "zu", "mit", "von",
              "um", "auf", "about", "around", "over", "nearly", "almost", "up", "to", "with", "of", "than", "more"}
PLACE_RE = re.compile(r"\b(?:Platz|Rang|Nummer|Place|Number|Rank)\s+(?:\d+|eins|zwei|drei|vier|fünf|one|two|three|four|five)\b",
                      re.IGNORECASE)
SUPERLATIVE_RE = re.compile(
    r"\b(?:größt|höchst|längst|tiefst|schnellst|stärkst|ältest|schwerst|kleinst|meist|gefährlichst|heißest|kältest|"
    r"giftigst|bekanntest|weitest|breitest|biggest|largest|tallest|longest|deepest|fastest|strongest|oldest|heaviest|"
    r"smallest|deadliest|hottest|most)\w*|mehr als|Rekord|weltweit|record|worldwide", re.IGNORECASE)


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for piece in re.split(r"(?<=[.!?…])\s+", text.strip()):
        if not piece:
            continue
        if out and out[-1].lower().endswith(ABBREVIATIONS):         # „ca. 300“ nicht trennen
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    return out


def _break_split(sentence: str) -> list[tuple[str, str]]:
    """Teilsätze an „ – “ und „…“: (Text, trennendes Zeichen vor dem folgenden Teil)."""
    pieces = [p.strip() for p in re.split(r"\s[–—]\s|\s-\s", sentence)]
    parts: list[tuple[str, str]] = []
    for k, piece in enumerate(pieces):
        sub = [x.strip() for x in re.split(r"(?<=…)\s*(?=\S)|(?<=\.\.\.)\s*(?=\S)", piece) if x.strip()]
        for m, x in enumerate(sub):
            last = m == len(sub) - 1
            parts.append((x, "–" if (last and k < len(pieces) - 1) else ("…" if not last else "")))
    return parts


def _split_before(sentence: str) -> list[tuple[str, str]]:
    """Vor „Platz N“ bzw. vor der ersten Zahl (samt „rund“, „mehr als“ …) teilen: [(Text, Rolle des Teils)]."""
    tokens = sentence.split()
    if len(tokens) < 4:
        return [(sentence, "")]
    place = PLACE_RE.search(sentence)
    if place and place.start() > 0 and len(sentence[:place.start()].split()) >= 3:
        return [(sentence[:place.start()].strip(), ""), (sentence[place.start():].strip(), "platz")]
    skip = len(sentence[:place.end()].split()) if place and place.start() == 0 else 0     # „Platz 1:“ ist keine Zahl-Stelle
    k = next((i for i, t in enumerate(tokens) if i >= skip and re.search(r"\d", t)), None)
    if k is None:
        return [(sentence, "")]
    i = k
    while i > skip and tokens[i - 1].lower().strip(",") in QUALIFIERS:
        i -= 1
    if i >= max(3, skip + 2) and len(tokens) - i >= 2:
        return [(" ".join(tokens[:i]), ""), (" ".join(tokens[i:]), "zahl")]
    return [(sentence, "")]


def _role(text: str, forced: str, first: bool, kind: str) -> str:
    if forced:
        return forced
    if text.rstrip().endswith("?"):
        return "frage"
    if PLACE_RE.match(text):
        return "platz"
    if re.search(r"\d", text):
        return "zahl"
    if SUPERLATIVE_RE.search(text):
        return "superlativ"
    if first and kind == "intro":
        return "hook"
    return "normal"


def plan_parts(text: str, kind: str = "item") -> list[Part]:
    """Text in betonte Teile zerlegen (siehe oben). Nie leer; die Wörter bleiben in der Reihenfolge des Textes."""
    raw: list[tuple[str, str, str, float]] = []        # (Text, erzwungene Rolle, Pause-Quelle, Mindestpause)
    for sentence in _sentences(text):
        for piece, sep in _break_split(sentence):
            subs = _split_before(piece)
            for k, (chunk, forced) in enumerate(subs):
                if chunk.strip():
                    raw.append((chunk.strip(), forced, sep if k == len(subs) - 1 else "", 0.0))
    if not raw:
        return [Part(text.strip() or " ")]
    parts: list[Part] = []
    prev_end, prev_sep = "", ""
    for i, (chunk, forced, sep, _) in enumerate(raw):
        role = _role(chunk, forced, i == 0, kind)
        rate, pitch, volume = ROLE_PROSODY[role]
        pause = 0.0
        if i > 0:
            pause = PAUSE_AFTER_QUESTION if prev_end.endswith("?") else PAUSE_SENTENCE
            if prev_sep:
                pause = max(pause, PAUSE_AFTER_BREAK)
            if role == "platz":
                pause = max(pause, PAUSE_BEFORE_PLACE)
            elif role == "zahl":
                pause = max(pause, PAUSE_BEFORE_NUMBER)
            elif role == "superlativ":
                pause = max(pause, PAUSE_BEFORE_SUPERLATIVE)
        # winzige Teile (ein Wort ohne Zahl) hängen am Vorgänger – sonst klingt es abgehackt
        if parts and len(chunk.split()) < 2 and not re.search(r"\d", chunk) and role == "normal":
            parts[-1].text += " " + chunk
        else:
            parts.append(Part(chunk, rate, pitch, volume, round(pause, 2), role))
        prev_end, prev_sep = chunk, sep
    if kind == "outro" and parts[-1].role == "normal":
        parts[-1].rate, parts[-1].pitch = -4, -1       # Schluss ruhig, einladend
    return parts[:8]


def _rate_text(base: str, delta: int) -> str:
    value = max(-45, min(45, round(_percent(base) + delta)))
    return f"{value:+d}%"


def part_prosody(part: Part, base_rate: str) -> tuple[str, str, str]:
    return _rate_text(base_rate, part.rate), f"{part.pitch:+d}Hz", f"{part.volume:+d}%"


def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as f:
        return np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32767


def _trim(audio: np.ndarray, lead: float = 0.04, tail: float = 0.07) -> tuple[np.ndarray, float]:
    """Stille am Anfang/Ende wegnehmen (kleiner Rand bleibt); liefert Audio und die vorn entfernten Sekunden."""
    win = SAMPLE_RATE // 100
    n_win = len(audio) // win
    if n_win < 2:
        return audio, 0.0
    rms = np.sqrt(np.mean(audio[: n_win * win].reshape(n_win, win) ** 2, axis=1))
    loud = np.flatnonzero(rms >= SILENCE_RMS)
    if not len(loud):
        return audio, 0.0
    a = max(0, int(loud[0] * win - lead * SAMPLE_RATE))
    b = min(len(audio), int((loud[-1] + 1) * win + tail * SAMPLE_RATE))
    return audio[a:b], a / SAMPLE_RATE


def assemble_parts(parts: list[Part], spoken: list[tuple[Path, list[dict]]], wav: Path,
                   max_pause: float = MAX_PAUSE) -> tuple[list[dict], float]:
    """Gesprochene Teile mit den geplanten Pausen zu einem Abschnitt zusammensetzen; Wortzeiten verschieben sich mit."""
    chunks: list[np.ndarray] = []
    words: list[dict] = []
    t = 0.0
    for i, (part, (src, part_words)) in enumerate(zip(parts, spoken)):
        tmp = wav.with_name(f"{wav.stem}.p{i}.wav")
        shifted, _ = tighten_pauses(src, part_words, tmp, max_pause)
        audio, cut = _trim(_read_wav(tmp))
        tmp.unlink(missing_ok=True)
        if i and part.pause > 0:
            chunks.append(np.zeros(int(part.pause * SAMPLE_RATE), dtype=np.float32))
            t += int(part.pause * SAMPLE_RATE) / SAMPLE_RATE
        length = len(audio) / SAMPLE_RATE
        for w in shifted:
            start = min(max(0.0, w["start"] - cut), length)
            end = min(max(start, w["end"] - cut), length)
            words.append({**w, "start": round(t + start, 3), "end": round(t + end, 3)})
        chunks.append(audio)
        t += length
    pcm = (np.clip(np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())
    return words, len(pcm) / SAMPLE_RATE


async def _voice_script(script: Script, out_dir: Path, voice: str, rate: str, parallel: int = 3,
                        expressive: bool = True) -> None:
    plans = [plan_parts(seg.text, seg.kind) if expressive else [Part(seg.text)] for seg in script.segments]
    flat = [part for plan in plans for part in plan]
    spoken = await _speak_all([part.text for part in flat], out_dir, voice, rate, "+0Hz", parallel,
                              [part_prosody(part, rate) for part in flat])
    pos = 0
    for i, (seg, plan) in enumerate(zip(script.segments, plans)):
        wav = out_dir / f"{i:02d}_{seg.kind}.wav"
        seg.words, seg.duration = assemble_parts(plan, spoken[pos:pos + len(plan)], wav)
        seg.audio_path = str(wav)
        pos += len(plan)


def voice_script(script: Script, out_dir: Path, voice: str | None = None, rate: str | None = None) -> Script:
    out_dir.mkdir(parents=True, exist_ok=True)
    voice = voice or config.VOICES[script.lang]
    asyncio.run(_voice_script(script, out_dir, voice, rate or config.VOICE_RATE))
    return script


async def _voice_texts(texts: list[str], out_dir: Path, voice: str, rate: str, pitch: str, max_pause: float,
                       parallel: int = 2) -> list[tuple[Path, list[dict], float]]:
    spoken = await _speak_all(texts, out_dir, voice, rate, pitch, parallel)
    result = []
    for i, (src, words) in enumerate(spoken):
        wav = out_dir / f"{i:03d}.wav"
        new_words, duration = tighten_pauses(src, words, wav, max_pause)
        result.append((wav, new_words, duration))
    return result


def voice_texts(texts: list[str], out_dir: Path, voice: str, rate: str = "+0%", pitch: str = "+0Hz",
                max_pause: float = MAX_PAUSE) -> list[tuple[Path, list[dict], float]]:
    """Mehrere Texte vertonen (z. B. Story-Szenen): je Text (WAV, Wort-Zeitstempel, Dauer)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_voice_texts(texts, out_dir, voice, rate, pitch, max_pause))
