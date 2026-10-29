"""Die komplette Pipeline. Jede Stufe speichert ihr Ergebnis als JSON im Ausgabeordner."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import config
from .compare import load_references
from .enrich import enrich
from .metadata import build_metadata, build_review
from .models import Research, Script
from .script import build_script
from .sources.wikidata import check_consistency, fetch_identifiers, fetch_ranking
from .spec import VideoSpec
from .verify import verify

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, float], None]
MAX_SECONDS = 179.0   # YouTube Shorts: höchstens 3 Minuten


def _noop(stage: str, fraction: float) -> None:
    pass


def _save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def new_output_dir(spec: VideoSpec) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = config.OUTPUT_DIR / f"{stamp}_{spec.id}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def research_stage(spec: VideoSpec, out: Path, fresh: bool = True, images: bool = True,
                   strict: bool = False) -> Research:
    research = fetch_ranking(spec, fresh=fresh)
    if not research.items:
        raise RuntimeError("Keine Daten gefunden – Vorgabe prüfen (Klasse/Eigenschaft).")
    fetch_identifiers(research.items, config.CHECK_LANGS)
    verify(spec, research, strict=strict)          # Abgleich mit unabhängigen Quellen
    research.warnings.extend(check_consistency(spec, research))
    research.references = load_references(spec)    # belegte Vergleiche ("5-mal so hoch wie …")
    enrich(research, spec.langs, images=images)
    _save(out / "research.json", research.to_dict())
    return research


def video_seconds(script: Script) -> float:
    from .render.video import LEAD, TAIL

    return sum(LEAD[s.kind] + s.duration + TAIL[s.kind] for s in script.segments)


def _faster(rate: str, extra: int) -> str:
    """'+8%' -> '+15%'"""
    return f"{int(rate.strip('%')) + extra:+d}%"


def voice_within_limit(spec: VideoSpec, research: Research, script: Script, out: Path, use_llm) -> Script:
    """Vertonen und sicherstellen, dass das Video unter dem Shorts-Limit bleibt.

    Nach der ersten Vertonung wird das echte Sprechtempo gemessen und die reichhaltigste
    Textstufe gewählt, die passt (erst Wikipedia-Sätze, dann Zusatzinfos weglassen). Reicht das
    nicht, spricht die Stimme etwas schneller."""
    from .render.video import LEAD, TAIL
    from .tts import voice_script

    limit = min(spec.target_seconds + 8, MAX_SECONDS)
    audio_dir = out / f"audio_{script.lang}"
    voice_script(script, audio_dir)
    total = video_seconds(script)
    if total <= limit:
        return script

    speech = sum(s.duration for s in script.segments)
    words = sum(len(s.text.split()) for s in script.segments)
    pauses = sum(LEAD[s.kind] + TAIL[s.kind] for s in script.segments)
    seconds_per_word = speech / max(1, words)
    candidates = [(scale, detail) for detail in (2, 1, 0) for scale in ((0.8, 0.6, 0.4) if detail == 2 else (1.0,))]
    rates = [config.VOICE_RATE, _faster(config.VOICE_RATE, 7), _faster(config.VOICE_RATE, 14)]
    for rate_index, rate in enumerate(rates):
        speed = 1 + 0.07 * rate_index                     # grobe Schätzung des Tempogewinns
        for scale, detail in candidates:
            candidate = build_script(spec, research, script.lang, use_llm=use_llm, budget_scale=scale, detail=detail)
            estimate = pauses + sum(len(s.text.split()) for s in candidate.segments) * seconds_per_word / speed
            if estimate > limit * 0.97:
                continue
            log.info("Kürze Text (Stufe %d, Faktor %.1f, Tempo %s): geschätzt %.0fs", detail, scale, rate, estimate)
            voice_script(candidate, audio_dir, rate=rate)
            total = video_seconds(candidate)
            if total <= limit:
                return candidate
            seconds_per_word = sum(s.duration for s in candidate.segments) / max(
                1, sum(len(s.text.split()) for s in candidate.segments)) * speed
    raise RuntimeError(f"Video bleibt zu lang ({total:.0f}s). Bitte weniger Plätze wählen.")


def run(
    spec: VideoSpec,
    out: Path | None = None,
    langs: list[str] | None = None,
    render: bool = True,
    use_llm: bool | None = None,
    fresh: bool = True,
    images: bool = True,
    strict: bool = False,
    progress: ProgressFn = _noop,
) -> dict:
    """Erzeugt Videos für alle Sprachen. Mit render=False nur Recherche + Skript + Prüfbericht."""
    from .render.video import render_video   # erst hier laden: braucht ffmpeg/numpy

    langs = langs or spec.langs
    spec.langs = langs
    out = out or new_output_dir(spec)
    _save(out / "spec.json", spec.to_dict())

    progress("Recherche", 0.0)
    research_file = out / "research.json"
    if research_file.exists():
        research = Research.from_dict(json.loads(research_file.read_text("utf-8")))
    else:
        progress("Quellen-Abgleich", 0.05)
        research = research_stage(spec, out, fresh=fresh, images=images, strict=strict)

    progress("Skript", 0.15)
    scripts: list[Script] = []
    for lang in langs:
        script = build_script(spec, research, lang, use_llm=use_llm)
        _save(out / f"script_{lang}.json", script.to_dict())
        scripts.append(script)
    (out / "review.md").write_text(build_review(spec, research, scripts), "utf-8")

    result = {"output_dir": str(out), "warnings": research.warnings, "videos": {}}
    if not render:
        _save(out / "result.json", result)
        progress("Fertig (nur Skript)", 1.0)
        return result

    share = 0.8 / len(langs)
    for i, script in enumerate(scripts):
        base = 0.2 + i * share
        progress(f"Stimme ({script.lang})", base)
        script = voice_within_limit(spec, research, script, out, use_llm)
        scripts[i] = script
        _save(out / f"script_{script.lang}.json", script.to_dict())

        progress(f"Animation ({script.lang})", base + share * 0.1)
        files = render_video(spec, research, script, out,
                             progress_cb=lambda f, b=base: progress(f"Animation ({script.lang})", b + share * (0.1 + 0.85 * f)))
        meta = build_metadata(spec, research, script)
        meta_file = out / f"{spec.id}_{script.lang}_beschreibung.txt"
        meta_file.write_text(f"{meta['title']}\n\n{meta['description']}\n", "utf-8")
        files.update({"metadata": meta, "description_file": meta_file.name})
        result["videos"][script.lang] = files

    (out / "review.md").write_text(build_review(spec, research, scripts), "utf-8")   # endgültige Texte
    _save(out / "result.json", result)
    progress("Fertig", 1.0)
    return result
