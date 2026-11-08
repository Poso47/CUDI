"""Die komplette Pipeline. Jede Stufe speichert ihr Ergebnis als JSON im Ausgabeordner."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from . import config, net
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
    return config.new_output_folder(spec.id)


def research_stage(spec: VideoSpec, out: Path, fresh: bool = True, images: bool = True,
                   strict: bool = False) -> Research:
    if spec.kind == "facts":                       # Fakten-Ranking: Fachartikel -> Claude -> Prüfung je Fakt
        from .facts import research_facts

        research = research_facts(spec, spec.langs)
        _save(out / "research.json", research.to_dict())
        return research
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


def voice_within_limit(spec: VideoSpec, research: Research, script: Script, out: Path, use_llm,
                       narration: dict | None = None) -> Script:
    """Vertonen und sicherstellen, dass das Video unter dem Shorts-Limit bleibt.

    Nach der ersten Vertonung wird das echte Sprechtempo gemessen und die reichhaltigste
    Textstufe gewählt, die passt (erst Wikipedia-Sätze, dann Zusatzinfos weglassen). Reicht das
    nicht, spricht die Stimme etwas schneller."""
    from .render.video import LEAD, TAIL
    from .tts import speech_profile, voice_script

    cap = config.LONG_MAX_SECONDS if spec.target_seconds > MAX_SECONDS else MAX_SECONDS   # „Lang“: bis 10 Min.
    limit = min(spec.target_seconds + 8, cap)
    audio_dir = out / f"audio_{script.lang}"
    profile = speech_profile(spec.kind)                # Sprechprofil nach Videoart (Ranking spannend, Fakten erklärend)
    voice_script(script, audio_dir, profile=profile)
    total = video_seconds(script)
    if total <= limit:
        return script

    rates = [config.VOICE_RATE, _faster(config.VOICE_RATE, 7), _faster(config.VOICE_RATE, 14)]
    if narration:                      # erzählte Texte zuerst nur etwas schneller sprechen, bevor gekürzt wird
        for rate in rates[1:]:
            voice_script(script, audio_dir, rate=rate, profile=profile)
            total = video_seconds(script)
            if total <= limit:
                return script

    pauses = sum(LEAD[s.kind] + TAIL[s.kind] for s in script.segments)
    # Sprechtempo je Abschnitt messen (Zahlen und lange Wörter dauern länger als der Durchschnitt)
    rates_per_segment = [s.duration / max(1, len(s.text.split())) for s in script.segments]

    def estimate(candidate: Script, speed: float) -> float:
        speech = sum(len(seg.text.split()) * rate for seg, rate in zip(candidate.segments, rates_per_segment))
        return pauses + speech / speed

    candidates = [(scale, detail) for detail in (2, 1, 0) for scale in ((0.8, 0.6, 0.4) if detail == 2 else (1.0,))]
    for rate_index, rate in enumerate(rates):
        speed = 1 + 0.07 * rate_index                     # grobe Schätzung des Tempogewinns
        for scale, detail in candidates:
            candidate = build_script(spec, research, script.lang, use_llm=use_llm, budget_scale=scale, detail=detail)
            guess = estimate(candidate, speed)
            if guess > limit - 2:
                continue
            log.info("Kürze Text (Stufe %d, Faktor %.1f, Tempo %s): geschätzt %.0fs", detail, scale, rate, guess)
            voice_script(candidate, audio_dir, rate=rate, profile=profile)
            total = video_seconds(candidate)
            if total <= limit:
                return candidate
            rates_per_segment = [s.duration * speed / max(1, len(s.text.split())) for s in candidate.segments]
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
    net.reset_blocks()                       # Drosselungen früherer Aufträge gelten hier nicht
    out = out or new_output_dir(spec)
    _save(out / "spec.json", spec.to_dict())

    progress("Recherche", 0.0)
    research_file = out / "research.json"
    if research_file.exists():
        research = Research.from_dict(json.loads(research_file.read_text("utf-8")))
        spec.shrink_to(len(research.items))       # wie nach dem Abgleich (Fortsetzen nach einer Schreibaufgabe)
        if research.partial:                      # Cloud-Probe Flüsse 4: „5 der längsten“ ging beim Fortsetzen verloren
            from .verify import _partial_title

            spec.title = {lang: _partial_title(t, lang) for lang, t in spec.title.items()}
    else:
        progress("Quellen-Abgleich", 0.05)
        research = research_stage(spec, out, fresh=fresh, images=images, strict=strict)

    progress("Skript", 0.15)
    from .narrate import request as narrate_request
    narration = narrate_request(spec, research, langs) if use_llm is not False and spec.kind != "facts" else {}
    from .metadata import request_titles
    titles_llm = request_titles(spec, research, langs) if use_llm is not False else {}      # 3 Titel je Sprache
    scripts: list[Script] = []
    for lang in langs:
        script = build_script(spec, research, lang, use_llm=use_llm, narration=narration.get(lang) or None)
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
        script = voice_within_limit(spec, research, script, out, use_llm, narration=narration.get(script.lang) or None)
        scripts[i] = script
        _save(out / f"script_{script.lang}.json", script.to_dict())

        progress(f"Animation ({script.lang})", base + share * 0.1)
        files = render_video(spec, research, script, out,
                             progress_cb=lambda f, b=base: progress(f"Animation ({script.lang})", b + share * (0.1 + 0.85 * f)))
        meta = build_metadata(spec, research, script, titles_llm, files.get("duration"))
        meta_file = out / f"{spec.id}_{script.lang}_beschreibung.txt"
        meta_file.write_text(f"{meta['title']}\n\n{meta['description']}\n", "utf-8")
        caption_file = out / f"{spec.id}_{script.lang}_tiktok.txt"
        caption_file.write_text(meta["caption"] + "\n", "utf-8")
        files.update({"metadata": meta, "description_file": meta_file.name, "caption_file": caption_file.name})
        result["videos"][script.lang] = files
        if files.get("qa"):
            result["warnings"] = list(result["warnings"]) + [f"Endkontrolle ({script.lang}): {b}" for b in files["qa"]["befunde"]]

    hints = [f"- {lang}: {f['metadata']['length_hint']}" for lang, f in result["videos"].items()
             if (f.get("metadata") or {}).get("length_hint")]
    review = build_review(spec, research, scripts)                                    # endgültige Texte
    qa_lines = [f"- {lang}: " + ("bestanden" if f["qa"]["ok"] else "; ".join(f["qa"]["befunde"]))
                + f" (Lautheit {f['qa']['lufs_vor']} -> {f['qa']['lufs_nach']} LUFS)"
                for lang, f in result["videos"].items() if f.get("qa")]
    (out / "review.md").write_text(review + ("\n## Endkontrolle\n\n" + "\n".join(qa_lines) + "\n" if qa_lines else "")
                                     + ("\n## Längenziel\n\n" + "\n".join(hints) + "\n" if hints else ""), "utf-8")
    _save(out / "result.json", result)
    progress("Fertig", 1.0)
    return result
