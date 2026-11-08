"""Gemeinsames: HTTP mit Zeitlimit/Wiederholung, Quellen einzeln absichern, JSON nur bei Änderung schreiben, Status."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import requests

from .. import config

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("CUDI_FIRMA_DATEN", config.PROJECT_DIR / "firma_daten"))
# Generischer Name ohne E-Mail (Wikimedia-Regeln: erkennbarer Bot, Kontakt über die Repo-Seite)
USER_AGENT = "CUDI-Firma/1.0 (open-source video research bot; https://github.com/Poso47/CUDI)"
# Schlüssel, die bei jedem Lauf wechseln und allein keinen Commit auslösen sollen
VOLATILE = ("erzeugt", "letzter_lauf", "dauer_s", "naechste_planung")
WORKERS = {"trends": 3, "news": 3, "ideen": 24, "putzen": 24, "lernen": 24, "wissen": 168}      # Planungsabstand in Stunden


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(text: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fetch(url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 15,
          retries: int = 2, method: str = "GET", **kw) -> requests.Response:
    """HTTP mit Zeitlimit und Wiederholung (429/5xx, Retry-After bis 20 s). Wirft requests.RequestException."""
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.request(method, url, params=params, headers=hdrs, timeout=timeout, **kw)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = resp.headers.get("Retry-After", "")
                time.sleep(min(float(wait) if wait.isdigit() else 2.0 * (attempt + 1), 20.0))
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last = exc
            if attempt < retries:
                time.sleep(2.0 * (attempt + 1))
    assert last is not None
    raise last


def short_error(exc: BaseException) -> str:
    """Fehlertext ohne Abfrage-Teil der Adressen (dort könnten Schlüssel stehen)."""
    text = re.sub(r"\s+", " ", f"{type(exc).__name__}: {exc}")
    return re.sub(r"\?[^\s'\")]*", "?…", text)[:200]


def run_source(name: str, func: Callable[[], list], notes: list[str]) -> list:
    """Eine Quelle einzeln absichern: Ausfall = Hinweis, kein Abbruch."""
    try:
        items = func()
        if not items:
            notes.append(f"{name}: keine Daten erhalten")
        return items or []
    except Exception as exc:                       # noqa: BLE001 – jede Störung einer Quelle bleibt lokal
        log.warning("%s: %s", name, short_error(exc))
        notes.append(f"{name}: nicht erreichbar ({short_error(exc)})")
        return []


def _strip(obj, drop=VOLATILE):
    if isinstance(obj, dict):
        return {k: _strip(v, drop) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [_strip(v, drop) for v in obj]
    return obj


def read_json(name: str, default=None):
    try:
        return json.loads((DATA_DIR / name).read_text("utf-8"))
    except (OSError, ValueError):
        return default


def write_json(name: str, data) -> bool:
    """Schreibt nur, wenn sich außer den flüchtigen Feldern etwas geändert hat. True = geschrieben."""
    path = DATA_DIR / name
    old = read_json(name)
    if old is not None and _strip(old) == _strip(data):
        return False
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf-8")
    tmp.replace(path)
    return True


def record_status(worker: str, started: float, ok: bool, summary: str, hinweise: list[str] | None = None) -> None:
    """Letzten Lauf des Mitarbeiters in status.json eintragen (Grundlage für das 3D-Büro)."""
    status = read_json("status.json", {}) or {}
    t = now()
    status.setdefault("mitarbeiter", {})[worker] = {
        "letzter_lauf": iso(t), "dauer_s": round(time.monotonic() - started, 1),
        "ergebnis": "ok" if ok else "fehler", "zusammenfassung": summary[:300],
        "hinweise": (hinweise or [])[:10],
        "naechste_planung": iso(t + timedelta(hours=WORKERS.get(worker, 24))),
    }
    status["erzeugt"] = iso(t)
    write_json("status.json", status)


def thin_by_age(items: list[dict], key: str, days: float) -> list[dict]:
    """Einträge entfernen, deren Zeitfeld `key` älter als `days` ist (ohne lesbare Zeit bleiben sie)."""
    limit = now() - timedelta(days=days)
    return [i for i in items if (parse_time(i.get(key, "")) or now()) >= limit]
