"""Höflicher HTTP-Client für Wikimedia: korrekter User-Agent, Backoff bei 429, Datei-Cache."""

import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import config

log = logging.getLogger(__name__)

_session = requests.Session()
_session.headers["User-Agent"] = config.USER_AGENT


class FetchError(RuntimeError):
    pass


def _cache_path(kind: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:32]
    return config.CACHE_DIR / kind / digest


# Hosts, die wiederholt gedrosselt haben (429 trotz Wartens), werden eine Weile übersprungen,
# damit optionale Anreicherung die Pipeline nicht minutenlang aufhält. Die Sperre läuft nach
# BLOCK_SECONDS ab: danach wird wieder angefragt – eine lange laufende Web-App erholt sich so von
# selbst. Scheitert der nächste Versuch erneut, gilt die Sperre sofort wieder.
_blocked_hosts: dict[str, int] = {}       # Host -> Anzahl erschöpfter 429-Serien
_blocked_at: dict[str, float] = {}        # Host -> Beginn der aktuellen Sperre
_block_lock = threading.Lock()
BLOCK_AFTER = 3
BLOCK_SECONDS = 300.0


RETRY_STATUSES = (429, 500, 502, 503, 504)


def reset_blocks() -> None:
    """Sperren aufheben – zu Beginn jedes Auftrags und vor einem bewusst späteren zweiten Versuch."""
    with _block_lock:
        _blocked_hosts.clear()
        _blocked_at.clear()


def is_blocked(host: str) -> bool:
    with _block_lock:
        return (_blocked_hosts.get(host, 0) >= BLOCK_AFTER
                and time.monotonic() - _blocked_at.get(host, 0.0) < BLOCK_SECONDS)


def _note_throttled(host: str) -> None:
    with _block_lock:
        _blocked_hosts[host] = _blocked_hosts.get(host, 0) + 1
        if _blocked_hosts[host] >= BLOCK_AFTER:
            _blocked_at[host] = time.monotonic()


def _note_ok(host: str) -> None:
    if host in _blocked_hosts:
        with _block_lock:
            _blocked_hosts.pop(host, None)
            _blocked_at.pop(host, None)


def _block_key(host: str) -> str:
    """Wikimedia drosselt pro Domain: alle Sprachversionen von Wikipedia teilen sich eine Sperre."""
    for domain in ("wikipedia.org", "wikimedia.org"):
        if host.endswith(domain):
            return domain
    return host


HOST_PARALLEL = 2                       # höchstens so viele gleichzeitige Abrufe je Server (Faktencheck parallel)
HOST_PARALLEL_SPECIAL = {"wikimedia.org": 1}   # Commons/Bilder drosseln anonyme Abrufe besonders schnell
_slots: dict = {}
_slots_lock = threading.Lock()


def _slot(host: str) -> threading.Semaphore:
    with _slots_lock:
        return _slots.setdefault(host, threading.Semaphore(HOST_PARALLEL_SPECIAL.get(host, HOST_PARALLEL)))


def get(url, params=None, headers=None, retries=4, max_wait=30.0, timeout=60, retry_on=RETRY_STATUSES):
    """GET mit Wiederholung. Respektiert Retry-After, wartet aber höchstens `max_wait` Sekunden.

    `retry_on` legt fest, bei welchen HTTP-Codes erneut versucht wird (z. B. nur 429, wenn ein
    Timeout 504 sofort an eine Ausweichroute übergeben werden soll)."""
    host = _block_key(urlparse(url).netloc)
    if is_blocked(host):
        raise FetchError(f"{host} drosselt gerade (zu viele Anfragen) – Pause bis zu {BLOCK_SECONDS / 60:.0f} Minuten")
    delay = 3.0
    last = None
    for attempt in range(retries + 1):
        try:
            with _slot(host):
                resp = _session.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last = str(exc)
            if 504 not in retry_on:      # Zeitüberschreitung soll sofort weitergereicht werden
                break
        else:
            if resp.ok:
                _note_ok(host)
                return resp
            last = f"HTTP {resp.status_code}"
            if resp.status_code not in retry_on:
                break
            retry_after = resp.headers.get("Retry-After", "")
            if retry_after.isdigit():
                delay = float(retry_after)
        if attempt < retries:
            wait = min(delay, max_wait)
            log.info("Warte %.0fs vor erneutem Versuch (%s): %s", wait, last, url)
            time.sleep(wait)
            delay *= 2
    if last == "HTTP 429":
        _note_throttled(host)
    raise FetchError(f"{url}: {last}")


def get_json(url, params=None, headers=None, cache_hours=12.0, **kw):
    """JSON holen, mit Cache. `cache_hours=0` erzwingt frische Daten."""
    key = url + "?" + json.dumps(params or {}, sort_keys=True)
    path = _cache_path("json", key)
    if cache_hours and path.exists() and time.time() - path.stat().st_mtime < cache_hours * 3600:
        return json.loads(path.read_text("utf-8"))
    data = get(url, params=params, headers=headers, **kw).json()
    _atomic_write(path, json.dumps(data).encode("utf-8"))
    return data


def _atomic_write(path: Path, data: bytes) -> None:
    """Erst in eine eigene Zwischendatei, dann umbenennen – parallele Abrufe zerschießen den Cache nicht."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def cached_file(url, suffix="", cache_hours=24.0 * 30) -> Path | None:
    """Pfad der zwischengespeicherten Datei – oder None, wenn sie (noch) nicht da ist."""
    path = _cache_path("files", url).with_suffix(suffix)
    if path.exists() and path.stat().st_size and time.time() - path.stat().st_mtime < cache_hours * 3600:
        return path
    return None


def download(url, suffix="", cache_hours=24.0 * 30, **kw) -> Path:
    """Datei herunterladen und im Cache ablegen; gibt den lokalen Pfad zurück."""
    path = _cache_path("files", url).with_suffix(suffix)
    if cached_file(url, suffix, cache_hours):
        return path
    resp = get(url, **kw)
    _atomic_write(path, resp.content)
    return path


def post(url, data=None, auth=None, timeout=30) -> requests.Response:
    """Einfacher POST (z. B. Reddit-Anmeldung); Fehler als FetchError."""
    try:
        resp = _session.post(url, data=data, auth=auth, timeout=timeout)
    except requests.RequestException as exc:
        raise FetchError(f"{url}: {exc}") from exc
    if not resp.ok:
        raise FetchError(f"{url}: HTTP {resp.status_code}")
    return resp
