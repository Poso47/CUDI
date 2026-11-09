"""Firma-Mitarbeiter „Vorrecherche“: erledigt nachts die langsamen Netzstufen eines Rankings (Wikidata-Abfrage + Quellen-Abgleich)
für alle Vorlagen und die Ranking-Ideen vorab -> firma_daten/vorrecherche/<schluessel>.json.gz (+ vorrecherche.json als Übersicht).
Kein Claude-Verbrauch. Die Pipeline nutzt junge Einträge (`cudi_video/vorrecherche.py`), ältere werden live neu abgefragt.

Höflich: nacheinander, Pausen, Zeitbudget; Drosselung (429) im Abgleich = Eintrag wird nicht gespeichert, nach einer Pause
ein zweiter Versuch, sonst bleibt der alte (noch gültige) Eintrag und der Rest folgt in der nächsten Nacht."""

from __future__ import annotations

import copy
import logging
import os
import time
from pathlib import Path

from .. import net, vorrecherche
from ..spec import VideoSpec
from . import common

log = logging.getLogger(__name__)

PLAETZE = (10, 5)                      # App-Standard 10; 5 ist die zweithäufigste Wahl (CUDI_VORRECHERCHE_PLAETZE="10,5,3")
SPRACHEN = (["de"], ["de", "en"])      # App-Standard nur Deutsch; mit Englisch für zweisprachige Aufträge
MAX_IDEEN = 3
PAUSE = 20.0                           # Sekunden zwischen zwei Vorlagen (Wikidata/Wikipedia schonen)
PAUSE_NACH_DROSSELUNG = 90.0
BUDGET_S = 100 * 60                    # Zeitbudget je Lauf (Workflow-Limit 150 Minuten)
MIN_BESTAETIGT = 0.5                   # weniger Plätze mit Bestätigung = Abgleich war lückenhaft -> nicht speichern


def _plaetze() -> list[int]:
    raw = os.environ.get("CUDI_VORRECHERCHE_PLAETZE", "")
    try:
        got = [int(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        got = []
    return got or list(PLAETZE)


def ziele(ideen: list[dict] | None = None) -> list[tuple[str, VideoSpec]]:
    """Alle Vorgaben, die vorab geholt werden: (Beschreibung, Spec). Reihenfolge: Vorlagen, dann Ideen."""
    from ..spec import find_preset, list_presets

    out: list[tuple[str, VideoSpec]] = []
    for preset in list_presets():
        for count in _plaetze():
            for langs in SPRACHEN:
                try:
                    spec = find_preset(preset.id, count)
                except (KeyError, ValueError) as exc:
                    log.warning("Vorlage %s (%d): %s", preset.id, count, exc)
                    continue
                spec.langs = list(langs)
                out.append((preset.id, spec))
    for idea in (ideen if ideen is not None else top_ideen()):
        order = idea.get("auftrag") or {}
        thema = str(order.get("thema") or "")
        if not thema or order.get("vorlage"):
            continue                                     # Vorlagen sind oben schon dabei
        try:
            from ..topics import plan_from_text

            spec = VideoSpec.from_dict(plan_from_text(thema, int(order.get("plaetze") or 10)))
        except Exception as exc:                          # noqa: BLE001 – PlanError, Fakten-Ideen u. a. gehören nicht hierher
            log.info("Idee „%s“ nicht vorab planbar: %s", thema[:50], exc)
            continue
        spec.langs = list(order.get("sprachen") or ["de"])
        out.append((f"idee: {thema[:50]}", spec))
    return out


def top_ideen() -> list[dict]:
    """Ranking-Ideen mit Auftrag, beste zuerst (nach Trend-Wert)."""
    data = common.read_json("ideen.json", {}) or {}
    ideas = [i for i in data.get("ideen", []) if i.get("bereich") == "ranking" and (i.get("auftrag") or {}).get("thema")
             and i.get("geprueft") in ("vorlage", "wikidata", "geplant")]
    ideas.sort(key=lambda i: -float((i.get("quelle") or {}).get("score") or 0))
    return ideas[:MAX_IDEEN]


def faellig(spec: VideoSpec, base: Path, jetzt=None) -> bool:
    """Eintrag fehlt oder ist älter als 40 % seiner erlaubten Nutzungsdauer (so ist er bei der Nutzung nie knapp vor dem Ablauf)."""
    entry = vorrecherche.lesen(vorrecherche.pfad(vorrecherche.schluessel(spec), base))
    if not entry:
        return True
    age = vorrecherche.alter_tage(entry.get("stand", ""), jetzt)
    return age is None or age < -0.01 or age > max(1.0, 0.4 * vorrecherche.max_alter_tage(spec.source.property))


def erzeuge(spec: VideoSpec):
    """Genau die Stufen planen + pruefen der Pipeline (gleiche Funktionen, gleiche Strenge). Gibt (Research, Spec nach Abgleich)."""
    from ..compare import load_references
    from ..sources.wikidata import fetch_identifiers, fetch_ranking
    from ..verify import verify
    from .. import config

    work = copy.deepcopy(spec)
    research = fetch_ranking(work, fresh=False)
    if not research.items:
        raise RuntimeError("Keine Daten gefunden")
    fetch_identifiers(research.items, config.CHECK_LANGS)
    verify(work, research, strict=False)
    research.references = load_references(work)
    return research, work


def gut_genug(research, n: int) -> str | None:
    """None = speichern; sonst der Grund, warum nicht (ehrlich im Bericht)."""
    if not research.items:
        return "keine Plätze"
    ok = sum(1 for it in research.items if (it.verification or {}).get("status") in ("bestätigt", "korrigiert"))
    if ok < MIN_BESTAETIGT * len(research.items):
        return f"nur {ok} von {len(research.items)} Plätzen bestätigt (Abgleich lückenhaft)"
    return None


def verarbeite(name: str, spec: VideoSpec, base: Path, notes: list[str]) -> str:
    """Einen Eintrag holen und speichern. Rückgabe: 'neu' | 'behalten' | 'aufgeschoben'."""
    key = vorrecherche.schluessel(spec)
    for attempt in (1, 2):
        net.reset_blocks()
        before = net.throttled_count
        try:
            research, nach = erzeuge(spec)
        except Exception as exc:                           # noqa: BLE001 – eine Vorlage darf ausfallen
            notes.append(f"{name} ({spec.count}): {common.short_error(exc)}")
            return "aufgeschoben"
        gedrosselt = net.throttled_count - before
        grund = gut_genug(research, spec.count) or (f"{gedrosselt}× von Wikimedia gedrosselt (Abgleich unvollständig)"
                                                   if gedrosselt else None)
        if grund is None:
            break
        if attempt == 1:
            log.info("%s: %s – Pause, zweiter Versuch", name, grund)
            time.sleep(PAUSE_NACH_DROSSELUNG)
    else:
        notes.append(f"{name} ({spec.count}, {'+'.join(spec.langs)}): {grund} – später erneut")
        return "aufgeschoben"
    new = vorrecherche.eintrag(key, nach, research, common.iso(), thema=name, gedrosselt=gedrosselt)
    old = vorrecherche.lesen(vorrecherche.pfad(key, base))
    age = vorrecherche.alter_tage((old or {}).get("stand", ""))
    if old and age is not None and age <= vorrecherche.max_alter_tage(spec.source.property) \
            and vorrecherche.bewertung(new) < vorrecherche.bewertung(old):
        notes.append(f"{name} ({spec.count}): neuer Abgleich schwächer als der gespeicherte – alter bleibt")
        return "behalten"
    size = vorrecherche.schreiben(vorrecherche.pfad(key, base), new)
    if size > vorrecherche.MAX_EINTRAG_BYTES:
        vorrecherche.pfad(key, base).unlink(missing_ok=True)
        notes.append(f"{name} ({spec.count}): Eintrag zu groß ({size} Bytes) – nicht gespeichert")
        return "aufgeschoben"
    return "neu"


def aufraeumen(base: Path, behalten: set[str]) -> int:
    """Einträge, die zu keiner heutigen Vorgabe mehr gehören (geänderte Vorlage, alte Idee), entfernen – und bei
    Überschreitung der Größengrenze die ältesten."""
    removed = 0
    files = sorted(base.glob("*.json.gz"), key=lambda p: p.stat().st_mtime)
    for p in files:
        if p.name[:-len(".json.gz")] not in behalten:
            p.unlink(missing_ok=True)
            removed += 1
    files = sorted(base.glob("*.json.gz"), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    while files and total > vorrecherche.MAX_BYTES:
        p = files.pop(0)
        total -= p.stat().st_size
        p.unlink(missing_ok=True)
        removed += 1
    return removed


def uebersicht(base: Path) -> list[dict]:
    rows = []
    for p in sorted(base.glob("*.json.gz")):
        e = vorrecherche.lesen(p)
        if e:
            rows.append({"schluessel": e["key"], "thema": e.get("thema", ""), "plaetze": e.get("count_nach"),
                         "sprachen": e.get("langs"), "stand": e.get("stand"), "status": e.get("status"),
                         "bytes": p.stat().st_size})
    return rows


def run() -> dict:
    started = time.monotonic()
    base = vorrecherche.ordner()
    base.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    wanted = ziele()
    keys = {vorrecherche.schluessel(s) for _, s in wanted}
    stats = {"neu": 0, "behalten": 0, "aufgeschoben": 0, "aktuell": 0}
    # Zuerst, was fehlt oder am ältesten ist: so kommt bei knappem Budget jede Vorlage wenigstens einmal dran
    todo = [(n, s) for n, s in wanted if faellig(s, base)]
    stats["aktuell"] = len(wanted) - len(todo)
    todo.sort(key=lambda ns: ((vorrecherche.lesen(vorrecherche.pfad(vorrecherche.schluessel(ns[1]), base)) or {}).get("stand", ""), ns[0]))
    for i, (name, spec) in enumerate(todo):
        if time.monotonic() - started > BUDGET_S:
            notes.append(f"Zeitbudget erreicht – {len(todo) - i} Einträge folgen in der nächsten Nacht")
            break
        if i and name != todo[i - 1][0]:                 # Pause nur zwischen verschiedenen Vorlagen (Varianten teilen den Netz-Cache)
            time.sleep(PAUSE)
        stats[verarbeite(name, spec, base, notes)] += 1
    removed = aufraeumen(base, keys)
    rows = uebersicht(base)
    data = {"erzeugt": common.iso(), "hinweise": notes[:20], "vorgaben": len(wanted), **stats, "entfernt": removed,
            "eintraege": rows, "bytes": sum(r["bytes"] for r in rows)}
    changed = common.write_json("vorrecherche.json", data)
    common.record_status("vorrecherche", started, bool(rows),
                         f"{len(rows)} Einträge ({stats['neu']} neu, {stats['aktuell']} aktuell, {stats['aufgeschoben']} aufgeschoben)"
                         + ("" if changed else " (unverändert)"), notes)
    return data
