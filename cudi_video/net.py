"""Höflicher HTTP-Client für Wikimedia: korrekter User-Agent, Backoff bei 429, Datei-Cache."""

import hashlib
import json
import logging
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


# Hosts, die in diesem Lauf wiederholt blockiert haben, werden übersprungen,
# damit optionale Anreicherung die Pipeline nicht minutenlang aufhält.
_blocked_hosts: dict[str, int] = {}
BLOCK_AFTER = 3


def get(url, params=None, headers=None, retries=4, max_wait=30.0, timeout=60):
    """GET mit Wiederholung. Respektiert Retry-After, wartet aber höchstens `max_wait` Sekunden."""
    host = urlparse(url).netloc
    if _blocked_hosts.get(host, 0) >= BLOCK_AFTER:
        raise FetchError(f"{host} ist in diesem Lauf blockiert (zu viele Anfragen)")
    delay = 3.0
    last = None
    for attempt in range(retries + 1):
        try:
            resp = _session.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as exc:
            last = str(exc)
        else:
            if resp.ok:
                _blocked_hosts.pop(host, None)
                return resp
            last = f"HTTP {resp.status_code}"
            if resp.status_code not in (429, 500, 502, 503, 504):
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
        _blocked_hosts[host] = _blocked_hosts.get(host, 0) + 1
    raise FetchError(f"{url}: {last}")


def get_json(url, params=None, headers=None, cache_hours=12.0, **kw):
    """JSON holen, mit Cache. `cache_hours=0` erzwingt frische Daten."""
    key = url + "?" + json.dumps(params or {}, sort_keys=True)
    path = _cache_path("json", key)
    if cache_hours and path.exists() and time.time() - path.stat().st_mtime < cache_hours * 3600:
        return json.loads(path.read_text("utf-8"))
    data = get(url, params=params, headers=headers, **kw).json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), "utf-8")
    return data


def download(url, suffix="", cache_hours=24.0 * 30, **kw) -> Path:
    """Datei herunterladen und im Cache ablegen; gibt den lokalen Pfad zurück."""
    path = _cache_path("files", url).with_suffix(suffix)
    if path.exists() and path.stat().st_size and time.time() - path.stat().st_mtime < cache_hours * 3600:
        return path
    resp = get(url, **kw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    return path
