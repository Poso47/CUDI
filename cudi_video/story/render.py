"""Story-Video rendern: Szenenclips/-bilder mit Stimmungs-Look, Post-Karte, Karaoke-Untertitel, Musik.

Der Ablauf orientiert sich an erfolgreichen Reddit-Story-Videos: Post-Karte während der Titel gelesen
wird, große Wort-für-Wort-Untertitel in der Bildmitte, ein Bild/Clip pro Erzähl-Beat, leise Musik
unter der Stimme, bei langen Storys „Teil 1/2“ mit Cliffhanger.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .. import config
from ..render import theme
from ..tts import voice_texts
from .moods import MOODS
from .music import make_music
from .visuals import Visual

log = logging.getLogger(__name__)

W, H, FPS = config.WIDTH, config.HEIGHT, config.FPS
GAP = {"creepy": 0.5, "suspense": 0.35, "drama": 0.3, "wholesome": 0.35, "revenge": 0.25, "funny": 0.2}
LEAD, TAIL = 0.3, 1.4
CAPTION_Y = 1010                # etwas unter der Mitte – über der TikTok-Leiste, frei von der Post-Karte
CARD_Y = 520
AFMT = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg-Fehler: {proc.stderr.strip()[-600:]}")


def media_duration(path: str | Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------- Post-Karte

def _short_number(n: int, lang: str) -> str:
    if n >= 1000:
        text = f"{n / 1000:.1f}".rstrip("0").rstrip(".")
        return (text.replace(".", ",") if lang == "de" else text) + "k"
    return str(n)


def _arrow(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color) -> None:
    s = size
    draw.polygon([(x + s / 2, y), (x + s, y + s * 0.55), (x + s * 0.7, y + s * 0.55), (x + s * 0.7, y + s),
                  (x + s * 0.3, y + s), (x + s * 0.3, y + s * 0.55), (x, y + s * 0.55)], fill=color)


def _bubble(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color) -> None:
    draw.rounded_rectangle((x, y, x + size, y + size * 0.78), radius=size // 4, outline=color, width=4)
    draw.polygon([(x + size * 0.25, y + size * 0.74), (x + size * 0.2, y + size), (x + size * 0.48, y + size * 0.76)],
                 fill=color)


def post_card(skeleton: dict, part_no: int, n_parts: int, path: Path) -> Path:
    """Karte im Stil eines Reddit-Posts (ohne Reddit-Logo): Subreddit, Autor, Titel, Upvotes."""
    mood = MOODS[skeleton["mood"]]
    post, lang = skeleton["post"], skeleton["lang"]
    dark = mood["colors"]["card"][0] < 128
    bg = (*mood["colors"]["card"], 245)
    fg = (240, 240, 245) if dark else (26, 26, 27)
    muted = (150, 150, 160) if dark else (110, 112, 120)
    accent = tuple(int(mood["colors"]["highlight"][i:i + 2], 16) for i in (0, 2, 4))
    width, pad = 940, 44
    title_font, lines = theme.fit_font(skeleton["title"], "black", 58, width - 2 * pad, 5, min_size=38)
    line_h = int(sum(title_font.getmetrics()) * 1.12)
    height = pad + 84 + 26 + line_h * len(lines) + 30 + 56 + pad
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, width - 1, height - 1), radius=36, fill=bg)
    # Kopfzeile: Avatar-Kreis, r/subreddit, u/autor
    d.ellipse((pad, pad, pad + 84, pad + 84), fill=accent)
    sub = post.get("subreddit") or ""
    d.text((pad + 42, pad + 42), "r/" if sub else "★", font=theme.font("black", 34), fill=(255, 255, 255), anchor="mm")
    head = f"r/{sub}" if sub else ("Story" if lang == "en" else "Geschichte")
    d.text((pad + 104, pad + 6), head, font=theme.font("bold", 38), fill=fg)
    author = post.get("author")
    meta = f"u/{author}" if author else ""
    if n_parts > 1:
        meta = f"{meta} · {'Teil' if lang == 'de' else 'Part'} {part_no}/{n_parts}".strip(" ·")
    if meta:
        d.text((pad + 104, pad + 50), meta, font=theme.font("regular", 30), fill=muted)
    y = pad + 84 + 26
    for line in lines:
        d.text((pad, y), line, font=title_font, fill=fg)
        y += line_h
    # Fußzeile: Upvotes und Kommentare (falls bekannt)
    y += 30
    if post.get("score"):
        _arrow(d, pad, y + 6, 40, accent)
        d.text((pad + 54, y + 4), _short_number(int(post["score"]), lang), font=theme.font("bold", 36), fill=fg)
    if post.get("num_comments"):
        x = pad + 220
        _bubble(d, x, y + 8, 40, muted)
        d.text((x + 56, y + 4), _short_number(int(post["num_comments"]), lang), font=theme.font("bold", 36), fill=fg)
    card.save(path)
    return path


# --------------------------------------------------------------------------- Hintergründe je Szene

def _gradient(mood: str, path: Path, index: int) -> Path:
    accent = tuple(int(MOODS[mood]["colors"]["highlight"][i:i + 2], 16) for i in (0, 2, 4))
    base = (34, 34, 44) if mood in ("creepy", "suspense") else (40, 34, 58)
    img = theme.linear_gradient((W, H), base, tuple(int(b * 0.7 + a * 0.3) for a, b in zip(accent, base)),
                                vertical=index % 2 == 0)
    img.convert("RGB").save(path, quality=92)
    return path


def render_segment(visual: Visual, seconds: float, index: int, mood: str, out: Path) -> Path:
    """Ein Szenen-Hintergrund als Video: Clip zugeschnitten oder Bild mit Kamerafahrt, Stimmungs-Look."""
    # Farblook und Filmkorn kommen erst im letzten Durchgang dazu (Korn je Szene kodiert bläht die Dateien auf)
    fade = "" if mood == "funny" else ",fade=t=in:st=0:d=0.35"
    frames = max(1, round(seconds * FPS))
    encode = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS)]
    if visual.kind == "video" and visual.path:
        length = media_duration(visual.path)
        start = (visual.start % max(length - seconds, 1)) if length > seconds + 1 else 0
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}{fade}"
        _run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-ss", f"{start:.2f}", "-i", visual.path,
              "-frames:v", str(frames), "-vf", vf, *encode, str(out)])
        return out
    image = visual.path if visual.kind == "image" and visual.path else str(_gradient(mood, out.with_suffix(".jpg"), index))
    zoom = 0.12
    moves = [  # abwechselnd: rein, raus, Schwenk nach rechts, Schwenk nach links
        (f"1+{zoom}*on/{frames}", "iw/2-(iw/zoom/2)"),
        (f"{1 + zoom}-{zoom}*on/{frames}", "iw/2-(iw/zoom/2)"),
        (f"{1 + zoom}", f"(iw-iw/zoom)*on/{frames}"),
        (f"{1 + zoom}", f"(iw-iw/zoom)*(1-on/{frames})"),
    ]
    z, x = moves[index % len(moves)]
    big_w, big_h = int(W * 1.5), int(H * 1.5)
    vf = (f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,crop={big_w}:{big_h},setsar=1,"
          f"zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}{fade}")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", image, "-vf", vf, "-frames:v", str(frames), *encode, str(out)])
    return out


# --------------------------------------------------------------------------- Untertitel

def _ass_color(hex_rgb: str, alpha: str = "00") -> str:
    return f"&H{alpha}{hex_rgb[4:6]}{hex_rgb[2:4]}{hex_rgb[0:2]}"


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h, rest = divmod(t, 3600)
    m, s = divmod(rest, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def mark_punctuation(words: list[dict], text: str) -> list[dict]:
    """Satzzeichen aus dem Text an die Wörter der Stimme hängen – edge-tts liefert Wörter ohne sie."""
    tokens = re.findall(r"\S+", text)
    out, ti = [], 0
    for w in words:
        key = re.sub(r"\W", "", w["text"]).lower()
        punct = ""
        for j in range(ti, min(ti + 4, len(tokens))):          # kleiner Vorgriff, falls Wörter zusammengefasst sind
            if key and key in re.sub(r"\W", "", tokens[j]).lower():
                ti = j + 1
                tail = tokens[j].rstrip("\"'”’)]»")
                punct = tail[-1] if tail[-1:] in (".", ",", "!", "?", ";", ":", "…") else ""
                break
        out.append({**w, "punct": punct})
    return out


def caption_groups(words: list[dict], max_words: int = 3, max_chars: int = 18) -> list[list[dict]]:
    """Wörter zu kurzen Untertitel-Häppchen (TikTok-Stil); ein Satzende beendet immer ein Häppchen."""
    groups, current = [], []
    for w in words:
        current.append(w)
        text = " ".join(x["text"] for x in current)
        punct = w.get("punct") or w["text"][-1:]
        sentence_end = punct in (".", "!", "?", "…")
        pause = punct in (",", ";", ":")
        if len(current) >= max_words or len(text) >= max_chars or sentence_end or pause:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def build_ass(path: Path, words: list[dict], font_name: str, mood: str, label: str | None,
              end_text: str | None, end_start: float, total: float,
              credits: list[tuple[float, float, str]] = ()) -> Path:
    """ASS-Datei: Wort-für-Wort-Untertitel mit hervorgehobenem aktuellem Wort, Teil-Label, Abschluss-Text."""
    colors = MOODS[mood]["colors"]
    hi = _ass_color(colors["highlight"])
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Caption,{font_name},96,{_ass_color(colors['text'])},&H000000FF,&H00000000,&H78000000,-1,0,0,0,100,100,"
        "0,0,1,8,4,5,70,70,0,1",
        f"Style: Label,{font_name},46,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,2,0,1,5,2,8,60,60,150,1",
        f"Style: End,{font_name},104,{hi},&H000000FF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,9,4,5,70,70,0,1",
        f"Style: Credit,{font_name},26,&H30FFFFFF,&H000000FF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,3,6,0,7,40,40,230,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    groups = caption_groups(words)
    for gi, group in enumerate(groups):
        next_start = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else group[-1]["end"] + 0.5
        group_end = min(next_start, group[-1]["end"] + 0.6)
        for wi, word in enumerate(group):
            start = word["start"]
            end = group[wi + 1]["start"] if wi + 1 < len(group) else group_end
            if end <= start:
                continue
            parts = []
            for k, w in enumerate(group):
                token = _escape(w["text"])
                parts.append(f"{{\\c{hi}}}{token}{{\\c{_ass_color(colors['text'])}}}" if k == wi else token)
            pop = "\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)" if wi == 0 else ""
            text = f"{{\\an5\\pos({W // 2},{CAPTION_Y}){pop}}}" + " ".join(parts)
            lines.append(f"Dialogue: 1,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{text}")
    if label:
        lines.append(f"Dialogue: 2,{_ass_time(0)},{_ass_time(total)},Label,,0,0,0,,{_escape(label)}")
    for start, end, credit in credits:                  # Urheberangabe für frei lizenzierte Fotos
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Credit,,0,0,0,,{_escape(credit)}")
    if end_text:
        lines.append(f"Dialogue: 3,{_ass_time(end_start)},{_ass_time(total)},End,,0,0,0,,"
                     f"{{\\an5\\pos({W // 2},{CAPTION_Y - 260})\\fad(250,0)}}{_escape(end_text)}")
    path.write_text("\n".join(lines) + "\n", "utf-8")
    return path


def write_srt(path: Path, words: list[dict], per_line: int = 7) -> Path:
    def ts(t: float) -> str:
        ms = int(round(max(t, 0) * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    blocks = []
    for i in range(0, len(words), per_line):
        chunk = words[i:i + per_line]
        blocks.append(f"{len(blocks) + 1}\n{ts(chunk[0]['start'])} --> {ts(chunk[-1]['end'])}\n"
                      + " ".join(w["text"] for w in chunk) + "\n")
    path.write_text("\n".join(blocks), "utf-8")
    return path


def _font_for_ass(work: Path) -> str:
    """Fette Schrift ins Arbeitsverzeichnis kopieren (libass findet sie dort sicher, auch unter Windows)."""
    fnt = theme.font("black", 40)
    fonts = work / "fonts"
    fonts.mkdir(exist_ok=True)
    if isinstance(fnt, ImageFont.FreeTypeFont) and getattr(fnt, "path", None):
        shutil.copy(fnt.path, fonts / Path(fnt.path).name)
        return fnt.getname()[0]
    return "Sans"


# --------------------------------------------------------------------------- Ton

def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as f:
        rate = f.getframerate()
        data = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if f.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
    return data, rate


def voice_track(segments: list[tuple[Path, float]], total: float, path: Path) -> Path:
    """Sprach-Abschnitte an ihren Startzeiten zu einer Spur zusammensetzen."""
    rate = 48_000
    track = np.zeros(int(total * rate) + 1, dtype=np.float32)
    for wav, start in segments:
        data, r = _read_wav(wav)
        if r != rate:
            data = np.interp(np.arange(0, len(data), r / rate), np.arange(len(data)), data).astype(np.float32)
        i = int(start * rate)
        n = min(len(data), len(track) - i)
        track[i:i + n] += data[:n]
    pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(pcm.tobytes())
    return path


# --------------------------------------------------------------------------- ein Teil

def render_part(skeleton: dict, part_index: int, visuals: list[Visual], work: Path, out: Path,
                progress=lambda f: None) -> dict:
    """Rendert einen Teil. `visuals` gehören zu den Szenen dieses Teils."""
    mood, lang = skeleton["mood"], skeleton["lang"]
    part = skeleton["parts"][part_index]
    n_parts = len(skeleton["parts"])
    voice = skeleton["voice"]
    work.mkdir(parents=True, exist_ok=True)

    texts = [part["intro"], *[s["text"] for s in part["scenes"]], part["outro"]]
    progress(0.02)
    voiced = voice_texts(texts, work / "audio", voice["name"], voice["rate"], voice["pitch"], voice["pause"])
    progress(0.25)

    gap = GAP.get(mood, 0.3)
    starts, t = [], LEAD
    for _, _, duration in voiced:
        starts.append(t)
        t += duration + gap
    total = t - gap + TAIL
    words = [{**w, "start": w["start"] + s, "end": w["end"] + s}
             for (_, ws, _), s, text in zip(voiced, starts, texts) for w in mark_punctuation(ws, text)]
    intro_end = starts[1] - gap / 2
    story_words = [w for w in words if w["start"] >= intro_end - 0.05]        # Titel steht auf der Karte

    # Hintergründe: Szene 1 beginnt bei 0 (unter der Karte), die letzte läuft bis zum Ende
    n = len(part["scenes"])
    bounds = [0.0] + [starts[i + 1] for i in range(1, n)] + [total]
    segments = []
    for i in range(n):
        seg = render_segment(visuals[i], bounds[i + 1] - bounds[i], i, mood, work / f"seg_{i:02d}.mp4")
        segments.append(seg)
        progress(0.25 + 0.45 * (i + 1) / n)
    concat = work / "segments.txt"
    concat.write_text("".join(f"file '{p.name}'\n" for p in segments), "utf-8")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat.name, "-c", "copy",
          "visual.mp4"], cwd=work)

    voice_track([(wav, s) for (wav, _, _), s in zip(voiced, starts)], total, work / "voice.wav")
    make_music(MOODS[mood]["music"], total, work / "music.wav", seed=part_index + 1)
    post_card(skeleton, part_index + 1, n_parts, work / "card.png")
    font_name = _font_for_ass(work)
    label = (f"{'TEIL' if lang == 'de' else 'PART'} {part_index + 1}/{n_parts}") if n_parts > 1 else None
    last = part_index == n_parts - 1
    end_text = None if last else ("TEIL" if lang == "de" else "PART") + f" {part_index + 2} " + ("FOLGT" if lang == "de" else "SOON")
    credits = [(bounds[i], bounds[i + 1], visuals[i].credit.removesuffix(" – Wikimedia Commons"))
               for i in range(n) if visuals[i].credit.startswith("Foto:")]
    build_ass(work / "captions.ass", story_words, font_name, mood, label, end_text, starts[-1], total, credits)
    progress(0.75)

    filters = (
        f"[1:v]format=rgba,fade=t=in:st=0:d=0.35:alpha=1,fade=t=out:st={max(intro_end - 0.35, 0.1):.2f}:d=0.35:alpha=1[card];"
        f"[0:v]{MOODS[mood]['grade']}[graded];"
        f"[graded][card]overlay=(W-w)/2:{CARD_Y}:eof_action=pass,subtitles=captions.ass:fontsdir=fonts[v];"
        f"[2:a]{AFMT},asplit=2[vo][sc];"
        f"[3:a]loudnorm=I=-30:TP=-8:LRA=11,{AFMT}[mu];"            # Musik leise und gleich laut je Stil
        "[mu][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=450[duck];"   # beim Sprechen leiser
        f"[vo][duck]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,{AFMT}[a]"
    )
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", "visual.mp4", "-loop", "1", "-t", f"{intro_end:.2f}",
          "-i", "card.png", "-i", "voice.wav", "-i", "music.wav", "-filter_complex", filters,
          "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-maxrate", "9M",
          "-bufsize", "18M", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.2f}", "-movflags", "+faststart",
          str(out.resolve())], cwd=work)
    progress(0.95)
    cover = out.with_name(out.stem + "_cover.jpg")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(1.0, intro_end / 2):.2f}", "-i", str(out.resolve()),
          "-frames:v", "1", "-q:v", "3", str(cover.resolve())])
    srt = write_srt(out.with_suffix(".srt"), words)
    shutil.rmtree(work, ignore_errors=True)                 # Zwischendateien sind groß – nur das Ergebnis bleibt
    progress(1.0)
    return {"video": out.name, "duration": round(total, 1), "cover": cover.name, "subtitles": srt.name}
