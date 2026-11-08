"""Fertiges Video in der App bearbeiten – ohne neue Recherche.

Beim Rendern sichert `capture` die Bearbeitungsgrundlage (Skript je Sprache, Format, Design, Maskottchen, Tempo,
Reihenfolge, Recherche mit Medienverweisen) als `bearbeitung.json` im Auftragsordner und kompakt im Ergebnisdokument
(`results/<id>.bearbeitung`). Die App legt Grundlage + Änderungen als `bearbeitungen/<id>` ab {"basis", "neu"}; der
Schritt `bearbeiten` (job.py) rendert daraus neu. Geänderte Texte laufen durch dieselben Prüfungen wie Claude-Texte
(textcheck): keine neuen Zahlen oder Namen ohne Beleg – abgelehnte Zeilen bleiben auf dem alten Stand (Hinweis).
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from . import config, handoff, textcheck

log = logging.getLogger(__name__)

VERSION = 1
MAX_COMPACT = 160_000                  # Bytes JSON der Grundlage im Ergebnisdokument (Doc. der App bleibt klein)
MAX_TEXT = 700                         # Zeichen je Zeile
TEMPO_RANGE = (-15, 20)                # Prozentpunkte zum bisherigen Sprechtempo
FILE = "bearbeitung.json"

WRITE_INSTRUCTIONS = (
    "Ein fertiges Kurzvideo wird nach dem Wunsch des Nutzers („wunsch“) überarbeitet. „sprachen“ enthält je Sprache "
    "den Titel und alle Textfelder („intro“, „platz_<n>“, „outro“). Ändere NUR Felder, die der Wunsch betrifft, und "
    "formuliere sie natürlich und gut vorlesbar. Strenge Regeln: Erfinde nichts – keine neuen Zahlen, Namen, Orte oder "
    "Behauptungen; Zahlen und Fakten dürfen nur aus dem alten Text desselben Feldes oder aus „fakten“ stammen; die "
    "Platznummern und Reihenfolge bleiben wahr; Länge höchstens etwas über dem alten Text. Antworte mit JSON: "
    "{\"<sprache>\": {\"titel\": \"…\", \"intro\": \"…\", \"platz_3\": \"…\", \"outro\": \"…\"}} und nur den geänderten "
    "Feldern. Ist der Wunsch ohne Erfindungen nicht erfüllbar, antworte mit {}."
)


# --------------------------------------------------------------------------- Prüfung von Texten

def clean(text) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", str(text or ""))).strip()[:MAX_TEXT]


def check_text(new: str, old: str, pool: str, lang: str, extra_numbers=()) -> str:
    """'' = Text darf übernommen werden, sonst der Grund der Ablehnung. `pool` = alles, was den Text belegt
    (alter Text, Namen, Beschreibungen, Werte desselben Platzes); Zahlen und Namen müssen darin vorkommen."""
    new = clean(new)
    if not new:
        return "leer"
    if new == clean(old):
        return ""
    old_words = len(clean(old).split())
    if len(new.split()) > max(old_words * 1.6, old_words + 12):
        return "deutlich länger als vorher (das Video würde zu lang)"
    allowed = textcheck.numbers(pool, lang) | {f"{float(n):g}" for n in extra_numbers}
    bad = sorted(textcheck.numbers(new, lang) - allowed)
    if bad:
        return "neue Zahl ohne Beleg: " + ", ".join(bad[:3])
    people = textcheck.invented_people(new, pool)
    if people:
        return "neuer Name ohne Beleg: " + ", ".join(people[:3])
    tokens = textcheck.tokens(pool)
    extra = {t for t in tokens if t.isalpha()}
    unknown = []
    for match in re.finditer(r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'’-]+", new):
        word = match.group(0)
        before = new[:match.start()].rstrip()
        if not before or before[-1] in ".!?…:":          # Satzanfang: Großschreibung sagt nichts
            continue
        if textcheck.known(word, tokens) or textcheck.everyday_word(word, lang, extra):
            continue
        unknown.append(word)
    if unknown:
        return "neues Wort/Name ohne Beleg: " + ", ".join(unknown[:3])
    return ""


# --------------------------------------------------------------------------- Grundlage sichern

def _json(path: Path):
    return json.loads(path.read_text("utf-8"))


def _options() -> dict:
    from .render.theme import FORMAT_NAMES, STYLES

    return {"formate": list(FORMAT_NAMES),
            "designs": [{"id": k, "name": v["label"]["de"]} for k, v in STYLES.items() if k != "manuskript"]}


def _tempo(result: dict) -> int:
    try:
        return int(result.get("tempo", int(str(config.VOICE_RATE).strip("%"))))
    except (TypeError, ValueError):
        return 0


def _shrink(basis: dict) -> dict:
    """Kompakte Fassung für das Ergebnisdokument: Recherche ohne lokale Pfade und lange Texte, Größe begrenzt."""
    out = copy.deepcopy(basis)
    out["kompakt"] = True
    research = out.get("research")
    if research:
        for item in research["items"]:
            item["image_path"] = None
            item["clips"] = [{k: c.get(k) for k in ("credit", "duration", "kind")} for c in item.get("clips") or []]
            ver = item.get("verification") or {}
            item["verification"] = {k: ver[k] for k in ("status", "sources") if k in ver}
            item["fact"] = item.get("fact") or {}
        research.pop("query", None)
    skeleton = out.get("skelett")
    if skeleton:
        post = skeleton.get("post") or {}
        skeleton["post"] = {k: (v[:800] if isinstance(v, str) else v) for k, v in post.items()
                            if isinstance(v, (str, int, float, bool)) or v is None}

    def size() -> int:
        return len(json.dumps(out, ensure_ascii=False))

    for cut in (300, 160, 80, 0):
        if size() <= MAX_COMPACT:
            break
        for item in (research or {}).get("items", []):
            item["summary"] = {k: v[:cut] for k, v in (item.get("summary") or {}).items()}
            item["descriptions"] = {k: v[:max(cut, 60)] for k, v in (item.get("descriptions") or {}).items()}
            item["fact"] = {k: (v[:cut] if isinstance(v, str) else v) for k, v in (item.get("fact") or {}).items()}
    if size() > MAX_COMPACT:
        out.pop("research", None)                     # zu groß: ohne Recherche (Neu-Recherche nötig) – Texte bleiben
        out["ohne_recherche"] = True
    return out


def capture(order: dict, result: dict | None) -> dict | None:
    """Bearbeitungsgrundlage eines fertigen Videos; None für Clips, Skelett-Schritt, Fehler. Nie ein Abbruch."""
    if not result or not result.get("videos") or order.get("art") not in ("ranking", "story"):
        return None
    try:
        out = Path(result["output_dir"])
        basis = (_capture_story if order["art"] == "story" else _capture_ranking)(order, result, out)
        basis.update(version=VERSION, id=order["id"], art=order["art"], optionen=_options(),
                     stand=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        return basis
    except Exception:                                     # noqa: BLE001 – Bearbeiten ist eine Zugabe
        log.exception("Bearbeitungsgrundlage ließ sich nicht sichern")
        return None


def _capture_ranking(order: dict, result: dict, out: Path) -> dict:
    from . import mascot
    from .render.video import style_for
    from .spec import VideoSpec

    spec_data = _json(out / "spec.json")
    spec = VideoSpec.from_dict(copy.deepcopy(spec_data))
    style = style_for(spec)
    langs = {}
    for lang in result["videos"]:
        script = _json(out / f"script_{lang}.json")
        langs[lang] = {"titel": script["title"], "modus": script.get("mode", ""),
                       "segmente": [{"art": s["kind"], "rang": s.get("rank"), "text": s["text"]} for s in script["segments"]]}
    return {"spec": spec_data, "research": _json(out / "research.json"), "sprachen": langs,
            "stil": {"format": style["format"], "design": style["name"], "motion": style["motion"],
                     "maskottchen": mascot.enabled() and style["format"] != "manuskript", "tempo": _tempo(result)}}


def _capture_story(order: dict, result: dict, out: Path) -> dict:
    from . import mascot
    from .story import pipeline

    return {"skelett": pipeline.load_skeleton(out), "stil": {"maskottchen": mascot.enabled()}}


def write_files(folder: Path, basis: dict) -> dict:
    """bearbeitung.json im Auftragsordner (komplett, mit lokalen Pfaden) und die kompakte Fassung fürs Dokument."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / FILE).write_text(json.dumps(basis, ensure_ascii=False), "utf-8")
    return _shrink(basis)


# --------------------------------------------------------------------------- Ranking neu rendern

def _load_basis(job_folder: Path | None, basis: dict) -> dict:
    """Liegt auf diesem Rechner noch die volle Grundlage desselben Renderns (Web-App/PC), hat sie Vorrang
    (mit Bildern und Clips); sonst die kompakte aus der App."""
    try:
        local = _json(job_folder / FILE) if job_folder else None
    except (OSError, ValueError):
        local = None
    return local if local and local.get("stand") == basis.get("stand") and local.get("research") else basis


def _restore(basis: dict, langs: list[str], enrich_fn, notes: list[str]):
    from .models import Research
    from .spec import VideoSpec

    if not basis.get("research"):
        raise RuntimeError("Die Recherche dieses Videos ist nicht mehr gespeichert – bitte das Video neu erstellen.")
    spec = VideoSpec.from_dict(copy.deepcopy(basis["spec"]))
    research = Research.from_dict(copy.deepcopy(basis["research"]))
    for item in research.items:
        if item.image_path and not Path(item.image_path).exists():
            item.image_path = None
        item.clips = [c for c in item.clips if c.get("path") and Path(c["path"]).exists()]
    try:
        enrich_fn(research, langs)                        # holt nur Fehlendes: Bilder/Clips der gespeicherten Plätze
    except Exception as exc:                              # noqa: BLE001 – ohne Bild gibt es Platzhalter, kein Abbruch
        log.warning("Medien nachladen: %s", exc)
        notes.append("Einige Bilder ließen sich nicht erneut laden – dort steht ein Platzhalter.")
    return spec, research


def _enrich(research, langs):
    from .enrich import enrich

    enrich(research, langs, images=True)


def _facts_pool(spec, item, lang: str) -> str:
    from .units import quantity

    parts = [spec.title.get(lang, ""), " ".join(item.labels.values()), item.descriptions.get(lang, ""),
             item.summary.get(lang, ""), " ".join(" ".join(v.values()) for v in item.extras.values())]
    if spec.kind != "facts":
        parts.append(quantity(item.value, item.unit, spec.unit).display(lang))
    parts += [str(v) for v in (item.fact or {}).values() if isinstance(v, str)]
    return " ".join(parts)


def _ask_claude(wish: str, spec, research, orig: dict, cand: dict, langs: list[str]):
    """Freitext-Wunsch als Schreibaufgabe `bearbeiten` (Claude in der Sitzung oder Notbetrieb-Modell)."""
    data = {"wunsch": wish, "sprachen": {}, "fakten": {}}
    for lang in langs:
        fields = {"intro": cand[lang]["intro"], "outro": cand[lang]["outro"]}
        fields.update({f"platz_{r}": t for r, t in cand[lang]["items"].items()})
        data["sprachen"][lang] = {"titel": cand[lang]["titel"], **fields}
    for item in research.items:
        data["fakten"][f"platz_{item.rank}"] = {lang: _facts_pool(spec, item, lang) for lang in langs}
    answer = handoff.request("bearbeiten", WRITE_INSTRUCTIONS, data)
    return answer if isinstance(answer, dict) else None


def apply_ranking(basis: dict, neu: dict, spec, research, ask=_ask_claude) -> tuple[dict, list[int], list[str]]:
    """Änderungen der App prüfen und anwenden. Rückgabe: ({lang: {titel, intro, outro, items:{rang: text}}},
    Reihenfolge der Plätze, Hinweise). Abgelehnte Zeilen bleiben auf dem alten Stand."""
    notes: list[str] = []
    orig = basis["sprachen"]
    langs = list(orig)
    new_langs = (neu or {}).get("sprachen") or {}
    first = langs[0]
    ranks = {s["rang"]: s["text"] for s in orig[first]["segmente"] if s["art"] == "item"}
    order: list[int] = []
    for seg in (new_langs.get(first) or {}).get("segmente", []):
        try:
            rank = int(seg.get("rang"))
        except (TypeError, ValueError):
            continue
        if seg.get("art") == "item" and rank in ranks and rank not in order:
            order.append(rank)
    if not order:
        order = list(ranks)
    if 1 in ranks and 1 not in order:
        order.append(1)
        notes.append("Platz 1 bleibt im Video – das Ranking braucht seine Spitze.")
    if len(order) < 3:
        order = list(ranks)
        notes.append("Mindestens drei Plätze bleiben – die Auswahl wurde zurückgesetzt.")
    items = {it.rank: it for it in research.items}
    default_order = list(ranks)

    def old_of(lang: str) -> dict:
        segs = orig[lang]["segmente"]
        return {"titel": orig[lang]["titel"], "intro": next((s["text"] for s in segs if s["art"] == "intro"), ""),
                "outro": next((s["text"] for s in segs if s["art"] == "outro"), ""),
                "items": {s["rang"]: s["text"] for s in segs if s["art"] == "item"}}

    def new_of(lang: str) -> dict:
        cur = old_of(lang)
        given = new_langs.get(lang) or {}
        if given.get("titel") is not None:
            cur["titel"] = clean(given["titel"]) or cur["titel"]
        for seg in given.get("segmente", []):
            text = clean(seg.get("text"))
            if seg.get("art") == "intro":
                cur["intro"] = text or cur["intro"]
            elif seg.get("art") == "outro":
                cur["outro"] = text or cur["outro"]
            elif seg.get("art") == "item":
                try:
                    rank = int(seg.get("rang"))
                except (TypeError, ValueError):
                    continue
                if rank in cur["items"] and text:
                    cur["items"][rank] = text
        return cur

    before = {lang: old_of(lang) for lang in langs}
    wanted = {lang: new_of(lang) for lang in langs}
    wish = clean((neu or {}).get("wunsch"))
    if wish:                                                # Freitext: Claude ändert nur, was der Nutzer nicht schon selbst tat
        answer = ask(wish, spec, research, before, wanted, langs)
        if answer is None:
            notes.append("Dein Wunsch („" + wish[:60] + "“) ließ sich nicht umsetzen: Weder Claude noch das Ersatz-"
                         "Sprachmodell hat geantwortet. Die übrigen Änderungen gelten.")
        else:
            for lang in langs:
                got = answer.get(lang) if isinstance(answer, dict) else None
                if not isinstance(got, dict):
                    continue
                for key, value in got.items():
                    text = clean(value)
                    if not text:
                        continue
                    if key == "titel" and wanted[lang]["titel"] == before[lang]["titel"]:
                        wanted[lang]["titel"] = text
                    elif key in ("intro", "outro") and wanted[lang][key] == before[lang][key]:
                        wanted[lang][key] = text
                    elif (m := re.fullmatch(r"platz_(\d+)", str(key))) and int(m.group(1)) in before[lang]["items"]:
                        rank = int(m.group(1))
                        if wanted[lang]["items"][rank] == before[lang]["items"][rank]:
                            wanted[lang]["items"][rank] = text

    result = {}
    numbers = set(range(1, len(ranks) + 1))
    all_pool = {lang: " ".join(_facts_pool(spec, it, lang) for it in research.items) for lang in langs}
    for lang in langs:
        o, w = before[lang], wanted[lang]
        accepted = {"titel": o["titel"], "intro": o["intro"], "outro": o["outro"], "items": dict(o["items"])}
        for name, label, key in (("titel", "Titel", None), ("intro", "Einstieg", None), ("outro", "Schluss", None)):
            reason = check_text(w[name], o[name], f"{o[name]} {all_pool[lang]}", lang, numbers)
            if reason:
                notes.append(f"{label} ({lang.upper()}) abgelehnt, bleibt wie vorher: {reason}.")
            else:
                accepted[name] = clean(w[name])
        for rank, text in w["items"].items():
            if rank not in items:
                continue
            reason = check_text(text, o["items"][rank], f"{o['items'][rank]} {_facts_pool(spec, items[rank], lang)}",
                                lang, numbers)
            if reason:
                notes.append(f"Platz {rank} ({lang.upper()}) abgelehnt, bleibt wie vorher: {reason}.")
            else:
                accepted["items"][rank] = clean(text)
        result[lang] = accepted
    if order != default_order and sorted(order) != sorted(default_order):
        gone = [r for r in default_order if r not in order]
        notes.append("Weggelassen: Platz " + ", ".join(map(str, sorted(gone))) +
                     ". Die übrigen Plätze behalten ihre wahre Platznummer.")
    elif order != default_order:
        notes.append("Die Reihenfolge ist geändert; die Platznummern bleiben wahr.")
    return result, order, notes


def _voice_fits(spec, script, audio_dir: Path, profile: str) -> bool:
    from .pipeline import MAX_SECONDS, _faster, video_seconds
    from .tts import voice_script

    cap = config.LONG_MAX_SECONDS if spec.target_seconds > MAX_SECONDS else MAX_SECONDS
    base = config.VOICE_RATE
    for rate in (base, _faster(base, 7), _faster(base, 14)):
        voice_script(script, audio_dir, rate=rate, profile=profile)
        if video_seconds(script) <= cap:
            return True
    return False


def render_ranking(order: dict, folder: Path, basis: dict, neu: dict, progress, ask=_ask_claude,
                   enrich_fn=_enrich) -> dict:
    """Ranking mit geänderten Texten, Format, Design, Tempo, Maskottchen neu rendern – gespeicherte Recherche."""
    from .metadata import build_metadata, build_review
    from .models import Script, Segment
    from .render.video import render_video
    from .tts import speech_profile

    notes: list[str] = []
    basis = _load_basis(folder, basis)
    langs = list(basis["sprachen"])
    progress("Bearbeitung vorbereiten", 0.03)
    spec, research = _restore(basis, langs, enrich_fn, notes)
    texts, ranks, check_notes = apply_ranking(basis, neu, spec, research, ask)
    notes += check_notes

    stil = basis.get("stil") or {}
    spec.style = (neu.get("format") if neu.get("format") in basis["optionen"]["formate"] else "") or stil.get("format", "")
    valid = {d["id"] for d in basis["optionen"]["designs"]}
    spec.design = (neu.get("design") if neu.get("design") in valid else "") or stil.get("design", "")
    mascot_on = neu.get("maskottchen")
    mascot_on = stil.get("maskottchen", True) if mascot_on is None else bool(mascot_on)
    os.environ["CUDI_MASCOT"] = "1" if mascot_on else "0"
    try:
        delta = max(TEMPO_RANGE[0], min(TEMPO_RANGE[1], int(neu.get("tempo") or 0)))
    except (TypeError, ValueError):
        delta = 0
    tempo = int(stil.get("tempo", 0)) + delta
    research.items = [it for it in research.items if it.rank in ranks]
    research.items.sort(key=lambda it: it.rank)
    for lang in langs:
        spec.title[lang] = texts[lang]["titel"]

    out = folder / "video"
    out.mkdir(parents=True, exist_ok=True)
    scripts: list[Script] = []
    original = {s: basis["sprachen"][s] for s in langs}
    profile = speech_profile(spec.kind)
    rate_before = config.VOICE_RATE
    config.VOICE_RATE = f"{tempo:+d}%"
    result = {"output_dir": str(out), "warnings": list(research.warnings), "videos": {}, "tempo": tempo}
    try:
        for i, lang in enumerate(langs):
            def build(t: dict) -> Script:
                segs = [Segment("intro", t["intro"])] + [Segment("item", t["items"][r], rank=r) for r in ranks] \
                       + [Segment("outro", t["outro"])]
                return Script(lang=lang, title=t["titel"], segments=segs, mode="bearbeitet")

            progress(f"Stimme ({lang})", 0.1 + 0.8 * i / len(langs))
            script = build(texts[lang])
            if not _voice_fits(spec, script, out / f"audio_{lang}", profile):
                notes.append(f"Mit deinen Texten wäre das Video ({lang.upper()}) zu lang für ein Short – "
                             "die ursprünglichen Texte bleiben.")
                old = original[lang]
                script = build({"titel": texts[lang]["titel"],
                                "intro": next(s["text"] for s in old["segmente"] if s["art"] == "intro"),
                                "outro": next(s["text"] for s in old["segmente"] if s["art"] == "outro"),
                                "items": {s["rang"]: s["text"] for s in old["segmente"] if s["art"] == "item"}})
                _voice_fits(spec, script, out / f"audio_{lang}", profile)
            scripts.append(script)
            (out / f"script_{lang}.json").write_text(json.dumps(script.to_dict(), ensure_ascii=False, indent=2), "utf-8")
            base = 0.15 + 0.8 * i / len(langs)
            share = 0.8 / len(langs)
            files = render_video(spec, research, script, out,
                                 progress_cb=lambda f, b=base, s=share, lg=lang: progress(f"Animation ({lg})", b + s * f))
            meta = build_metadata(spec, research, script)
            meta_file = out / f"{spec.id}_{lang}_beschreibung.txt"
            meta_file.write_text(f"{meta['title']}\n\n{meta['description']}\n", "utf-8")
            caption_file = out / f"{spec.id}_{lang}_tiktok.txt"
            caption_file.write_text(meta["caption"] + "\n", "utf-8")
            files.update({"metadata": meta, "description_file": meta_file.name, "caption_file": caption_file.name})
            result["videos"][lang] = files
    finally:
        config.VOICE_RATE = rate_before
    (out / "spec.json").write_text(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2), "utf-8")
    (out / "research.json").write_text(json.dumps(research.to_dict(), ensure_ascii=False, indent=2), "utf-8")
    review = build_review(spec, research, scripts)
    if notes:
        review += "\n## Bearbeitung\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    (out / "review.md").write_text(review, "utf-8")
    result["warnings"] = notes + result["warnings"]
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    progress("Fertig", 1.0)
    return result


# --------------------------------------------------------------------------- Story

def apply_story(basis: dict, neu: dict, ask_fn=None) -> tuple[dict, list[str]]:
    """Bearbeitetes Skelett prüfen: geänderte Szenen/Titel/Einstieg gegen die ursprünglichen Texte. Abgelehnte
    Szenen kehren zum alten Text zurück; neue Szenen, die nicht bestehen, entfallen."""
    notes: list[str] = []
    orig = basis["skelett"]
    skeleton = copy.deepcopy((neu or {}).get("skelett") or orig)
    lang = orig.get("lang", "de")
    flat = [s for p in orig["parts"] for s in p["scenes"]]
    pool = " ".join([orig.get("title", ""), orig.get("hook", "")] + [str(s.get("text", "")) for s in flat]
                    + [str((orig.get("post") or {}).get("text", ""))])
    wish = clean((neu or {}).get("wunsch"))
    if wish and ask_fn:
        answer = ask_fn(wish, orig, skeleton)
        if answer is None:
            notes.append("Dein Wunsch („" + wish[:60] + "“) ließ sich nicht umsetzen: Weder Claude noch das Ersatz-"
                         "Sprachmodell hat geantwortet. Die übrigen Änderungen gelten.")
        else:
            _merge_story_answer(skeleton, orig, answer)
    for key, label in (("title", "Titel"), ("hook", "Einstieg")):
        old, new = str(orig.get(key) or ""), str(skeleton.get(key) or "")
        if new != old and new:
            reason = check_text(new, old, f"{old} {pool}", lang)
            if reason:
                notes.append(f"{label} abgelehnt, bleibt wie vorher: {reason}.")
                skeleton[key] = orig.get(key)
    if skeleton.get("title") != orig.get("title"):
        old_title = orig.get("title") or ""
        for part in skeleton["parts"]:
            if part.get("intro") and old_title:
                part["intro"] = part["intro"].replace(old_title, skeleton["title"])
    for part in skeleton["parts"]:
        kept = []
        for scene in part["scenes"]:
            text = clean(scene.get("text"))
            o = scene.get("_o")
            old = clean(flat[o]["text"]) if isinstance(o, int) and 0 <= o < len(flat) else ""
            scene.pop("_o", None)
            reason = check_text(text, old, f"{old} {pool}", lang) if text != old else ""
            if reason:
                if old:
                    notes.append(f"Eine geänderte Szene wurde abgelehnt und bleibt wie vorher: {reason}.")
                    scene["text"] = flat[o]["text"]
                    kept.append(scene)
                else:
                    notes.append(f"Eine neue Szene wurde abgelehnt und entfällt: {reason}.")
                continue
            scene["text"] = text
            kept.append(scene)
        part["scenes"] = kept
    skeleton["parts"] = [p for p in skeleton["parts"] if p["scenes"]]
    if not skeleton["parts"]:
        notes.append("Alle Szenen waren leer oder abgelehnt – das ursprüngliche Skelett bleibt.")
        skeleton = copy.deepcopy(orig)
    return skeleton, notes


STORY_INSTRUCTIONS = (
    "Eine fertige Story wird nach dem Wunsch des Nutzers („wunsch“) überarbeitet. „szenen“ ist die nummerierte Liste "
    "der Szenentexte. Ändere NUR Szenen (und ggf. „titel“/„einstieg“), die der Wunsch betrifft; erfinde nichts – keine "
    "neuen Zahlen, Namen oder Ereignisse. Antworte mit JSON {\"titel\": \"…\", \"einstieg\": \"…\", \"szenen\": "
    "{\"<nummer>\": \"neuer Text\"}} und nur den geänderten Feldern; ohne erfüllbaren Wunsch {}."
)


def ask_story(wish: str, orig: dict, skeleton: dict):
    scenes = {str(i): str(s.get("text", "")) for i, s in enumerate(s for p in skeleton["parts"] for s in p["scenes"])}
    answer = handoff.request("bearbeiten", STORY_INSTRUCTIONS, {"wunsch": wish, "titel": skeleton.get("title"),
                                                                "einstieg": skeleton.get("hook") or "", "szenen": scenes})
    return answer if isinstance(answer, dict) else None


def _merge_story_answer(skeleton: dict, orig: dict, answer: dict) -> None:
    if isinstance(answer.get("titel"), str) and skeleton.get("title") == orig.get("title"):
        skeleton["title"] = clean(answer["titel"]) or skeleton["title"]
    if isinstance(answer.get("einstieg"), str) and (skeleton.get("hook") or "") == (orig.get("hook") or ""):
        skeleton["hook"] = clean(answer["einstieg"])
    flat = [s for p in skeleton["parts"] for s in p["scenes"]]
    flat_orig = [s for p in orig["parts"] for s in p["scenes"]]
    for key, text in (answer.get("szenen") or {}).items():
        try:
            scene = flat[int(key)]
        except (TypeError, ValueError, IndexError):
            continue
        o = scene.get("_o")
        untouched = isinstance(o, int) and 0 <= o < len(flat_orig) and scene.get("text") == flat_orig[o].get("text")
        if untouched and clean(text):                       # Hat der Nutzer die Szene selbst geändert, gilt seine Fassung
            scene["text"] = clean(text)
