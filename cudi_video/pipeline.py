"""Die komplette Pipeline. Jede Stufe speichert ihr Ergebnis als JSON im Ausgabeordner."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from . import config, handoff, net, vorrecherche, zeiten
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
    cached = None
    if not strict:                                 # streng: immer frisch abgleichen
        with zeiten.stufe("vorrecherche"):
            cached = vorrecherche.lade(spec)       # junger Eintrag der nächtlichen Vorrecherche (sonst None = live)
    if cached is not None:
        research = cached
        research.warnings.extend(check_consistency(spec, research))
    else:
        with zeiten.stufe("planen"):
            research = fetch_ranking(spec, fresh=fresh)
            if not research.items:
                raise RuntimeError("Keine Daten gefunden – Vorgabe prüfen (Klasse/Eigenschaft).")
            fetch_identifiers(research.items, config.CHECK_LANGS)
        with zeiten.stufe("pruefen"):
            verify(spec, research, strict=strict)      # Abgleich mit unabhängigen Quellen
            research.warnings.extend(check_consistency(spec, research))
            research.references = load_references(spec)    # belegte Vergleiche ("5-mal so hoch wie …")
    with zeiten.stufe("bilder"):
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
                       narration: dict | None = None, pruefer=None) -> Script:
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
    if pruefer:                                        # Wahrheits-Prüfer: auch gekürzte Fassungen laufen durch die Regeln
        pruefer.korrigiere_skript(script)
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
            if pruefer:
                from . import regie

                regie.wieder_anwenden(candidate, pruefer)          # Hook/Schluss der Regie bleiben auch in der gekürzten Fassung
            if pruefer:
                pruefer.korrigiere_skript(candidate)
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


def render_checked(spec: VideoSpec, research: Research, script: Script, out: Path, pruefer, titles_llm: dict | None = None,
                   progress_cb=None, revoice=None) -> tuple[dict, dict, Script]:
    """Rendern mit Endabnahme: Das Video gilt nur als fertig, wenn Wahrheits-Prüfung UND Endkontrolle (qa) bestehen.

    Besteht eines nicht, gibt es genau eine Reparaturrunde: Texte korrigieren, neu vertonen (`revoice`), ganz neu rendern
    (Teilrendern gibt es nicht – die Teile hängen an Bild- und Tonlänge). Bleibt der Befund, trägt `files["abnahme"]`
    `ok: False` mit ehrlichen Gründen; der Auftrag liefert dieses Video dann nicht aus."""
    from . import wahrheit
    from .metadata import build_metadata
    from .render.video import render_video

    for attempt in (1, 2):
        files = render_video(spec, research, script, out, progress_cb=progress_cb)
        meta = pruefer.korrigiere_meta(script, build_metadata(spec, research, script, titles_llm, files.get("duration")))
        bericht = pruefer.pruefe(script, meta)
        qa_block = files.get("qa")
        qa_ok = qa_block is None or bool(qa_block.get("ok", True))          # qa selbst ausgefallen: kein Grund zu blockieren
        if (bericht.ok and qa_ok) or attempt == 2:
            break
        before = [seg.text for seg in script.segments]
        pruefer.korrigiere_skript(script)
        changed = before != [seg.text for seg in script.segments]
        if not changed and bericht.offen:
            break                                    # nicht korrigierbar: neu rendern ändert nichts
        if changed and revoice:
            script = revoice(script)
        log.info("Endabnahme (%s): Reparaturrunde – Wahrheit %s, qa %s", script.lang, bericht.ok, qa_ok)
    reasons = [f"{wahrheit.REGELN.get(b.regel, (b.regel,))[0]}: „{b.satz[:90]}“ – {b.grund}" for b in bericht.offen[:5]]
    if not qa_ok:
        reasons += [f"Endkontrolle: {b}" for b in (qa_block or {}).get("befunde", [])[:5]]
    files["abnahme"] = {"ok": not reasons, "gruende": reasons, "wahrheit": bericht.to_dict(), "qa_ok": qa_ok,
                        "runden": attempt}
    return files, meta, script


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
    with zeiten.stufe("schreiben"):
        from .narrate import request as narrate_request
        if use_llm is not False and spec.kind != "facts":          # Erzählen + Titel sind unabhängig: EINE Schreibrunde statt zwei
            from . import narrate
            from .metadata import title_task

            handoff.request_many([narrate.task(spec, research, langs), title_task(spec, research, langs)])
        narration = narrate_request(spec, research, langs) if use_llm is not False and spec.kind != "facts" else {}
        from .metadata import request_titles
        titles_llm = request_titles(spec, research, langs) if use_llm is not False else {}      # 3 Titel je Sprache
        scripts: list[Script] = []
        for lang in langs:
            script = build_script(spec, research, lang, use_llm=use_llm, narration=narration.get(lang) or None)
            _save(out / f"script_{lang}.json", script.to_dict())
            scripts.append(script)
        from . import wahrheit

        pruefer = wahrheit.Pruefer(spec, research)
        from . import regie

        regie_block = regie.verbessere(spec, research, scripts, pruefer, use_llm)       # Psychologie + natürlicher Klang (max. 1 Runde)
        _save(out / "regie.json", regie_block)
        for s in scripts:
            _save(out / f"script_{s.lang}.json", s.to_dict())
        metas = {s.lang: build_metadata(spec, research, s, titles_llm) for s in scripts}
        pruefer.gegenlesen(scripts, metas)                  # optional: Claude/Notbetrieb liest gegen (kann WritingNeeded werfen)
        for s in scripts:
            pruefer.korrigiere_skript(s)                    # Wahrheits-Prüfung: Sprechtext/Hook vor dem Vertonen
            pruefer.korrigiere_meta(s, metas[s.lang])       # Titel/Beschreibung/Cover vollständig prüfen (Bericht auch ohne Render)
            _save(out / f"script_{s.lang}.json", s.to_dict())
        _save(out / "spec.json", spec.to_dict())            # Titel kann bei falscher Anzahl berichtigt sein
        if spec.kind == "facts" and use_llm is not False:   # Fakten-Videos: eigene Animation je Fakt, 1:1 zum Sprechtext
            from . import animation

            items = {s.lang: [{"key": str(seg.rank), "text": seg.text} for seg in s.segments if seg.kind == "item"] for s in scripts}
            animation.buendeln([(items[s.lang], s.title, s.lang, f"animation_fakten_{s.lang}") for s in scripts])
            for s in scripts:
                notes_anim: list[str] = []
                szenen, abgleich = animation.szenen_schreiben(
                    items[s.lang], s.title, s.lang, notes_anim, f"animation_fakten_{s.lang}")
                if szenen:
                    _save(out / f"animation_{s.lang}.json", szenen)
                animation.speichern(out, "fakten", abgleich)
                research.warnings = list(research.warnings) + notes_anim
    truth_review = lambda: wahrheit.review_section(pruefer, gruende)      # noqa: E731
    gruende: dict[str, list[str]] = {}
    (out / "review.md").write_text(wahrheit.in_review(build_review(spec, research, scripts),
                                                      truth_review() + "\n" + regie.review_section(regie_block)), "utf-8")

    result = {"output_dir": str(out), "warnings": research.warnings, "videos": {}, "regie": regie_block}
    for lang_, done in pruefer.protokoll.items():
        if done:
            result["warnings"] = list(result["warnings"]) + [
                f"Wahrheits-Prüfung ({lang_}): {len(done)} Aussage(n) korrigiert – Details im Prüfbericht."]
    if not render:
        _save(out / "result.json", result)
        progress("Fertig (nur Skript)", 1.0)
        return result

    share = 0.8 / len(langs)
    for i, script in enumerate(scripts):
        base = 0.2 + i * share
        progress(f"Stimme ({script.lang})", base)
        voice = lambda sc: voice_within_limit(spec, research, sc, out, use_llm,       # noqa: E731
                                              narration=narration.get(sc.lang) or None, pruefer=pruefer)
        script = voice(script)
        scripts[i] = script
        _save(out / f"script_{script.lang}.json", script.to_dict())

        progress(f"Animation ({script.lang})", base + share * 0.1)
        files, meta, script = render_checked(
            spec, research, script, out, pruefer, titles_llm, revoice=voice,
            progress_cb=lambda f, b=base, lg=script.lang: progress(f"Animation ({lg})", b + share * (0.1 + 0.85 * f)))
        scripts[i] = script
        _save(out / f"script_{script.lang}.json", script.to_dict())
        if not files["abnahme"]["ok"]:
            gruende[script.lang] = files["abnahme"]["gruende"]
            result["warnings"] = list(result["warnings"]) + [
                f"Nicht ausgeliefert ({script.lang}), weil: " + "; ".join(files["abnahme"]["gruende"])]
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
    review = wahrheit.in_review(build_review(spec, research, scripts), truth_review() + "\n" + regie.review_section(regie_block))
    _save(out / "wahrheit.json", {lang: b.to_dict() for lang, b in pruefer.berichte.items()})
    qa_lines = [f"- {lang}: " + ("bestanden" if f["qa"]["ok"] else "; ".join(f["qa"]["befunde"]))
                + f" (Lautheit {f['qa']['lufs_vor']} -> {f['qa']['lufs_nach']} LUFS)"
                for lang, f in result["videos"].items() if f.get("qa")]
    (out / "review.md").write_text(review + ("\n## Endkontrolle\n\n" + "\n".join(qa_lines) + "\n" if qa_lines else "")
                                     + ("\n## Längenziel\n\n" + "\n".join(hints) + "\n" if hints else ""), "utf-8")
    _save(out / "result.json", result)
    progress("Fertig", 1.0)
    return result
