"""Vorrecherche: Wikidata-Abfrage + Quellen-Abgleich (Stufen „planen“ und „pruefen“) vorab geholt und gespeichert.

Der Firma-Mitarbeiter `firma/vorrecherche.py` erledigt die langsamen Netzstufen nachts für alle Vorlagen und die
Ranking-Ideen und legt je Ranking-Vorgabe eine komprimierte Datei in `firma_daten/vorrecherche/` ab. `pipeline.research_stage`
nutzt sie, wenn sie jung genug ist – sonst läuft alles wie bisher live.

Ehrlichkeit: Jeder Eintrag trägt seinen Stand. Älter als erlaubt (Standard 7 Tage; selten ändernde Werte wie Höhen,
Flächen, Längen 30 Tage, je Eigenschaft einstellbar) wird er NIE genutzt. Der Prüfbericht nennt „Vorrecherche vom <Datum>“.
Die Prüfungen selbst bleiben gleich streng: gespeichert wird nur, was der normale Abgleich ergeben hat – und nur, wenn er
nicht durch Drosselung (429) lückenhaft war.

Aus: `CUDI_VORRECHERCHE=0`. Ordner: `CUDI_VORRECHERCHE_DIR` (sonst `<CUDI_FIRMA_DATEN|firma_daten>/vorrecherche`).
Alter: `CUDI_VORRECHERCHE_ALTER="standard=7,P1082=3,P2044=60"` (Tage)."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import os
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .models import Research
from .spec import VideoSpec

log = logging.getLogger(__name__)

SCHEMA = 1
ALTER_STANDARD = 7.0                    # Tage
# Höhen, Flächen, Tiefen, Längen ändern sich selten (Wikidata-Werte werden eher präzisiert als neu gemessen)
ALTER_JE_EIGENSCHAFT = {"P2044": 30.0, "P2046": 30.0, "P2048": 30.0, "P4511": 30.0, "P2043": 30.0}
MAX_BYTES = 4_000_000                   # Obergrenze aller Dateien im Repo
MAX_EINTRAG_BYTES = 200_000


def aktiv() -> bool:
    return os.environ.get("CUDI_VORRECHERCHE", "1").strip().lower() not in ("0", "aus", "off", "false", "nein")


def ordner() -> Path:
    if os.environ.get("CUDI_VORRECHERCHE_DIR"):
        return Path(os.environ["CUDI_VORRECHERCHE_DIR"])
    return Path(os.environ.get("CUDI_FIRMA_DATEN", config.PROJECT_DIR / "firma_daten")) / "vorrecherche"


def alter_grenzen() -> dict[str, float]:
    """Höchstalter in Tagen: {'standard': 7, 'P2044': 30, …}; Umgebung überschreibt je Eintrag."""
    out = {"standard": ALTER_STANDARD, **ALTER_JE_EIGENSCHAFT}
    for part in os.environ.get("CUDI_VORRECHERCHE_ALTER", "").split(","):
        name, _, days = part.partition("=")
        try:
            if name.strip() and days.strip():
                out[name.strip() if name.strip().lower() != "standard" else "standard"] = float(days)
        except ValueError:
            pass
    return out


def max_alter_tage(prop: str) -> float:
    limits = alter_grenzen()
    return limits.get(prop, limits["standard"])


def schluessel(spec: VideoSpec) -> str:
    """Gleiche Vorgabe (Quelle, Anzahl, Sprachen, Prüfmodus) = gleicher Schlüssel; Titel und Kennung zählen nicht."""
    basis = {"v": SCHEMA, "source": asdict(spec.source), "count": spec.count, "langs": sorted(spec.langs),
             "confirmed_only": spec.confirmed_only, "compare": spec.compare, "image_prop": spec.image_prop}
    return hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:20]


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


def _parse(text: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def alter_tage(stand: str, jetzt: datetime | None = None) -> float | None:
    dt = _parse(stand)
    return None if dt is None else ((jetzt or _jetzt()) - dt).total_seconds() / 86400


def pfad(key: str, base: Path | None = None) -> Path:
    return (base or ordner()) / f"{key}.json.gz"


def lesen(path: Path) -> dict | None:
    try:
        data = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    except (OSError, ValueError, EOFError):
        return None
    return data if isinstance(data, dict) and data.get("v") == SCHEMA else None


def schreiben(path: Path, data: dict) -> int:
    """Komprimiert und byte-gleich bei gleichem Inhalt (mtime=0): keine Scheinänderungen im Repo."""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as gz:
        gz.write(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.getvalue())
    return len(buf.getvalue())


def lade(spec: VideoSpec, jetzt: datetime | None = None) -> Research | None:
    """Passenden, jungen Eintrag lesen -> Research (nach planen+pruefen, vor check_consistency). Sonst None (= live abfragen).

    Setzt Titel/Anzahl der Vorgabe so, wie der Abgleich sie damals verändert hat (z. B. „Top 9“ statt „Top 10“)."""
    if not aktiv():
        return None
    key = schluessel(spec)
    entry = lesen(pfad(key))
    if not entry or entry.get("key") != key:
        return None
    age = alter_tage(entry.get("stand", ""), jetzt)
    limit = max_alter_tage(spec.source.property)
    if age is None or age < -0.01 or age > limit:         # zu alt (oder Uhr kaputt): nie als aktuell ausgeben
        log.info("Vorrecherche %s ist zu alt (%s Tage, erlaubt %s) – frage live ab", key, age and round(age, 1), limit)
        return None
    try:
        research = Research.from_dict(entry["research"])
    except (KeyError, TypeError, ValueError):
        return None
    research.spec_id = spec.id
    research.vorrecherche = entry["stand"]
    if entry.get("count_nach") and entry["count_nach"] != spec.count:
        spec.shrink_to(entry["count_nach"])
    if research.partial and entry.get("titel_nach"):       # „5 der längsten …“ statt „Die 5 längsten …“
        spec.title = dict(entry["titel_nach"])
    log.info("Vorrecherche vom %s genutzt (%.1f Tage alt, erlaubt %.0f)", entry["stand"], age, limit)
    return research


def eintrag(spec_vorher_key: str, spec: VideoSpec, research: Research, stand: str, thema: str = "",
            gedrosselt: int = 0) -> dict:
    """Datensatz für die Datei; `spec` ist die Vorgabe NACH dem Abgleich (Titel/Anzahl können sich geändert haben)."""
    counts: dict[str, int] = {}
    for it in research.items:
        status = (it.verification or {}).get("status", "nicht geprüft")
        counts[status] = counts.get(status, 0) + 1
    data = research.to_dict()
    data["vorrecherche"] = ""
    return {"v": SCHEMA, "key": spec_vorher_key, "stand": stand, "id": spec.id, "thema": thema or spec.title.get("de", ""),
            "property": spec.source.property, "count_nach": spec.count, "titel_nach": spec.title, "langs": sorted(spec.langs),
            "status": counts, "gedrosselt": gedrosselt, "research": data}


def bewertung(entry: dict) -> tuple[int, int]:
    """Wie gut belegt? (bestätigt/korrigiert, Quellen außerhalb Wikipedias) – ein neuer Eintrag ersetzt keinen besseren."""
    ok = sum((entry.get("status") or {}).get(k, 0) for k in ("bestätigt", "korrigiert"))
    ext = sum(len((it.get("verification") or {}).get("sources", [])) for it in (entry.get("research") or {}).get("items", []))
    return ok, ext


def review_zeile(research: Research, jetzt: datetime | None = None) -> str:
    """Zeile für den Prüfbericht; leer ohne Vorrecherche."""
    if not research.vorrecherche:
        return ""
    age = alter_tage(research.vorrecherche, jetzt)
    return (f"Vorrecherche vom {research.vorrecherche[:10]}"
            + (f" ({age:.0f} Tage alt)" if age is not None else "")
            + ": Wikidata-Abfrage und Quellen-Abgleich stammen aus der nächtlichen Vorrecherche, nicht aus diesem Lauf. "
              "Bilder, Texte und Prüfungen der Texte laufen frisch.")
