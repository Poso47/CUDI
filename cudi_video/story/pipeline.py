"""Ablauf für Reddit-Story-Videos.

1. Suchen: Beschreibung oder Stimmung -> passende Storys (oder Link/eigener Text)
2. Skelett: Lektorat, Szenen, Teile, Stimme, Bildideen -> story.json (zum Prüfen und Anpassen)
3. Video: Bilder/Clips holen, vertonen, rendern -> MP4 je Teil, Untertitel, Beschreibungen, Prüfbericht
"""

from __future__ import annotations

import json
import logging
import re
import zlib
from datetime import datetime
from pathlib import Path

from .. import config
from .editor import build_skeleton
from .moods import MOODS, narrator_gender, plan_from_description, subreddits_for, voice_for
from .render import render_part
from .sources import LENGTHS, Post, fetch_post, find_stories, post_from_text
from .visuals import Visual, pick_visuals

log = logging.getLogger(__name__)

TAGS = {
    "creepy": {"de": ["gruselgeschichten", "horror", "creepy", "redditstories"],
               "en": ["scarystories", "horror", "creepy", "redditstories"]},
    "suspense": {"de": ["spannend", "mystery", "redditstories", "storytime"],
                 "en": ["mystery", "suspense", "redditstories", "storytime"]},
    "funny": {"de": ["lustig", "fail", "redditstories", "storytime"], "en": ["funny", "tifu", "redditstories", "storytime"]},
    "drama": {"de": ["drama", "beziehung", "redditstories", "storytime"], "en": ["aita", "drama", "redditstories", "storytime"]},
    "revenge": {"de": ["rache", "karma", "redditstories", "storytime"], "en": ["revenge", "karma", "redditstories", "storytime"]},
    "wholesome": {"de": ["herzerwärmend", "wholesome", "redditstories", "storytime"],
                  "en": ["wholesome", "feelgood", "redditstories", "storytime"]},
}


def _slug(text: str) -> str:
    text = text.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:40] or "story"


def new_folder(title: str) -> Path:
    folder = config.OUTPUT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_story-{_slug(title)}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# --------------------------------------------------------------------------- 1. Suchen

def search(description: str = "", mood: str | None = None, lang: str = "de", length: str = "3min",
           seed: int | None = None, limit: int = 6) -> dict:
    """Storys zu einer Beschreibung oder Stimmung. Ergebnis für die Oberfläche (Liste + Hinweise)."""
    plan = plan_from_description(description, lang) if description.strip() else {
        "mood": mood or "creepy", "subreddits": subreddits_for(mood or "creepy", lang), "keywords": [],
        "description": ""}
    if mood:                                   # Knopf schlägt die Wortanalyse
        plan["mood"] = mood
        if not re.search(r"\br/\w+", description):
            plan["subreddits"] = subreddits_for(mood, lang)
    posts, notes = find_stories(plan, length=length, limit=limit, seed=seed, lang=lang)
    return {"plan": plan, "stories": [p.to_dict() for p in posts], "notes": notes}


# --------------------------------------------------------------------------- 2. Skelett

def prepare(story: dict | None = None, url: str = "", text: str = "", title: str = "", lang: str = "de",
            mood: str | None = None, length: str = "3min", visuals: str = "videos", soften: bool = True) -> tuple[dict, Path]:
    """Skelett aus einer gefundenen Story, einem Link oder eigenem Text. Speichert story.json."""
    if story:
        post = Post.from_dict(story)
    elif url:
        post = fetch_post(url)
    else:
        post = post_from_text(title, text)
    skeleton = build_skeleton(post, lang=lang, mood=mood, length=length, visuals=visuals, soften=soften)
    folder = new_folder(skeleton["title"])
    save_skeleton(folder, skeleton)
    return skeleton, folder


def save_skeleton(folder: Path, skeleton: dict) -> None:
    (folder / "story.json").write_text(json.dumps(skeleton, ensure_ascii=False, indent=1), "utf-8")
    # für die Ergebnisliste der Oberfläche (wie bei Rankings)
    (folder / "spec.json").write_text(json.dumps({"id": "story", "title": {skeleton["lang"]: skeleton["title"]},
                                                  "kind": "story"}, ensure_ascii=False), "utf-8")


def load_skeleton(folder: Path) -> dict:
    return json.loads((folder / "story.json").read_text("utf-8"))


def validate_skeleton(skeleton: dict) -> None:
    """Prüft ein (in der Oberfläche bearbeitetes) Skelett, bevor gerendert wird."""
    if skeleton.get("mood") not in MOODS or skeleton.get("lang") not in config.SUPPORTED_LANGS:
        raise ValueError("Ungültige Stimmung oder Sprache im Skelett")
    if not skeleton.get("parts") or not all(p.get("scenes") for p in skeleton["parts"]):
        raise ValueError("Das Skelett hat keine Szenen")
    for part in skeleton["parts"]:
        for scene in part["scenes"]:
            if not str(scene.get("text", "")).strip():
                raise ValueError("Leere Szene – Text eintragen oder Szene löschen")


# --------------------------------------------------------------------------- 3. Video

def render(folder_path: Path, skeleton: dict | None = None, progress=lambda stage, f: None) -> dict:
    """Alle Teile rendern. Ein übergebenes (bearbeitetes) Skelett ersetzt story.json."""
    folder = folder_path
    if skeleton is not None:
        validate_skeleton(skeleton)
        if not skeleton.get("voice"):              # Stimmung wurde geändert -> passende Stimme
            gender = narrator_gender(skeleton["post"].get("text", ""))
            name, rate, pitch = voice_for(skeleton["mood"], skeleton["lang"], gender)
            skeleton["voice"] = {"name": name, "rate": rate, "pitch": pitch, "pause": MOODS[skeleton["mood"]]["pause"]}
        save_skeleton(folder, skeleton)
    skeleton = load_skeleton(folder)
    lang, mood = skeleton["lang"], skeleton["mood"]
    n_parts = len(skeleton["parts"])
    all_scenes = [s for p in skeleton["parts"] for s in p["scenes"]]
    progress("Bilder und Clips", 0.02)
    visuals, notes = pick_visuals(all_scenes, mood, skeleton.get("visuals", "videos"),
                                  seed=zlib.crc32((skeleton["post"].get("id") or skeleton["title"]).encode()) % 10_000,
                                  progress=lambda d, t: progress("Bilder und Clips", 0.02 + 0.2 * d / t))
    result = {"output_dir": str(folder), "warnings": [*skeleton.get("rights", []), *notes], "videos": {}, "kind": "story"}
    base = f"story_{_slug(skeleton['title'])[:30]}_{lang}"
    offset = 0
    for i, part in enumerate(skeleton["parts"]):
        part_visuals = visuals[offset:offset + len(part["scenes"])]
        offset += len(part["scenes"])
        name = f"{base}_teil{i + 1}.mp4" if n_parts > 1 else f"{base}.mp4"
        share = 0.75 / n_parts
        files = render_part(skeleton, i, part_visuals, folder / f"work_{i + 1}", folder / name,
                            progress=lambda f, b=0.22 + i * share: progress(f"Video Teil {i + 1}/{n_parts}", b + share * f))
        meta = metadata(skeleton, i, part_visuals)
        desc = folder / name.replace(".mp4", "_beschreibung.txt")
        desc.write_text(f"{meta['title']}\n\n{meta['description']}\n", "utf-8")
        cap = folder / name.replace(".mp4", "_tiktok.txt")
        cap.write_text(meta["caption"] + "\n", "utf-8")
        key = f"{lang} · Teil {i + 1}" if n_parts > 1 else lang
        result["videos"][key] = {**files, "description_file": desc.name, "caption_file": cap.name, "metadata": meta}
    (folder / "review.md").write_text(review(skeleton, visuals, result), "utf-8")
    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    progress("Fertig", 1.0)
    return result


def autopilot(description: str = "", mood: str | None = None, url: str = "", lang: str = "de",
              length: str = "3min", visuals: str = "videos", soften: bool = True, seed: int | None = None,
              progress=lambda stage, f: None) -> dict:
    """Alles in einem Rutsch: Story suchen, beste nehmen, Skelett, Video."""
    progress("Story suchen", 0.0)
    story = None
    if not url:
        found = search(description, mood, lang, length, seed=seed, limit=3)
        if not found["stories"]:
            raise RuntimeError(" ".join(found["notes"]) or "Keine passende Story gefunden.")
        story = found["stories"][0]
        mood = mood or found["plan"]["mood"]
    progress("Skelett und Lektorat", 0.05)
    skeleton, folder = prepare(story=story, url=url, lang=lang, mood=mood, length=length, visuals=visuals, soften=soften)
    return render(folder, progress=lambda stage, f: progress(stage, 0.08 + 0.92 * f))


# --------------------------------------------------------------------------- Texte zum Hochladen

def metadata(skeleton: dict, part_index: int, visuals: list[Visual]) -> dict:
    lang, mood, post = skeleton["lang"], skeleton["mood"], skeleton["post"]
    de = lang == "de"
    n_parts = len(skeleton["parts"])
    part = f" ({'Teil' if de else 'Part'} {part_index + 1}/{n_parts})" if n_parts > 1 else ""
    icon = MOODS[mood]["icon"]
    title = f"{skeleton['title']}{part} {icon}"[:95]
    credit = (f"Story: u/{post['author']} auf r/{post['subreddit']}" if de else
              f"Story: u/{post['author']} on r/{post['subreddit']}") if post.get("author") else ""
    kinds = {v.kind for v in visuals}
    stock = sorted({v.credit for v in visuals if v.credit.startswith(("Pexels", "Pixabay"))})
    visual_line = []
    if "image" in kinds:
        visual_line.append("Bilder: KI-generierte Symbolbilder" if de else "Images: AI-generated illustrations")
    if stock:
        visual_line.append(("Videos: " if de else "Footage: ") + ", ".join(stock))
    photos = sorted({v.credit.removeprefix("Foto: ") for v in visuals if v.credit.startswith("Foto:")})
    if photos:
        visual_line.append(("Fotos: " if de else "Photos: ") + "; ".join(photos))
    tags = [*TAGS[mood][lang], "shorts"]
    lines = [skeleton["title"] + part, ""]
    if credit:
        lines += [credit, post.get("url", ""), ""]
    lines += [("ℹ️ Erzählt mit KI-Stimme. " if de else "ℹ️ Narrated with an AI voice. ") + " · ".join(visual_line),
              ("Musik: selbst erzeugt." if de else "Music: generated in-house."), "",
              " ".join(f"#{t}" for t in tags)]
    ai_voice = "KI-Stimme" if de else "AI voice"
    caption = "\n".join([f"{skeleton['title']}{part} {icon}", f"{credit} · {ai_voice}" if credit else ai_voice,
                          "", " ".join(f"#{t}" for t in TAGS[mood][lang])])
    return {"title": title, "description": "\n".join(lines).replace("\n\n\n", "\n\n"), "caption": caption, "tags": tags}


def review(skeleton: dict, visuals: list[Visual], result: dict) -> str:
    """Prüfbericht: Quelle, Rechte, Lektorat, Szenen mit Bild/Clip."""
    post, lang = skeleton["post"], skeleton["lang"]
    lines = [f"# Prüfbericht Story: {skeleton['title']}", ""]
    if post.get("url"):
        lines.append(f"**Quelle:** [{post['url']}]({post['url']}) – u/{post.get('author')} auf r/{post.get('subreddit')}, "
                     f"{post.get('score', 0)} Upvotes, {post.get('words')} Wörter ({post.get('source')})")
    else:
        lines.append("**Quelle:** eigener Text")
    voice = skeleton["voice"]
    lines += [f"**Stimmung:** {MOODS[skeleton['mood']]['label']['de']} · **Stimme:** {voice['name']} "
              f"(Tempo {voice['rate']}, Tonhöhe {voice['pitch']}) · **Lektorat:** {skeleton.get('editor')}", ""]
    if skeleton.get("rights"):
        lines += ["## ⚠️ Rechte", *[f"- {r}" for r in skeleton["rights"]], ""]
    if skeleton.get("notes") or result.get("warnings"):
        lines += ["## Lektorat und Hinweise", *[f"- {n}" for n in skeleton.get("notes", [])],
                  *[f"- {w}" for w in result.get("warnings", []) if w not in skeleton.get("rights", [])], ""]
    k = 0
    for i, part in enumerate(skeleton["parts"], start=1):
        lines += [f"## Teil {i}" if len(skeleton["parts"]) > 1 else "## Erzählung", "", f"**Einstieg:** {part['intro']}", ""]
        for scene in part["scenes"]:
            v = visuals[k] if k < len(visuals) else Visual("none")
            k += 1
            lines.append(f"{k}. {scene['text']}  \n   _Bild/Clip: {v.kind} · {v.credit or '–'} · Suche: {scene.get('query')}_")
        lines += ["", f"**Abschluss:** {part['outro']}", ""]
    for key, files in result.get("videos", {}).items():
        lines.append(f"- {key}: {files['video']} ({files['duration']} s)")
    return "\n".join(lines) + "\n"


def lengths() -> dict:
    return {k: v["label"] for k, v in LENGTHS.items()}
