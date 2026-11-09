"""Höflicher Seitenabruf für die Recherche: nur http/https, robots.txt beachten, Zeit- und Größenlimit, keine Cookies/Logins."""

from __future__ import annotations

import ipaddress
import threading
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from .. import config

UA_TOKEN = "CUDI-Recherche"
USER_AGENT = f"{UA_TOKEN}/1.0 (+https://github.com/Poso47/CUDI; freundlicher Lese-Bot, beachtet robots.txt)"
MAX_BYTES = 1_500_000
TIMEOUT = 15
PAUSE_JE_HOST = 1.0
TYPEN = ("text/html", "application/xhtml", "text/plain", "application/json", "application/xml", "text/xml")


class WebFehler(RuntimeError):
    pass


_robots: dict[str, RobotFileParser | None] = {}
_zuletzt: dict[str, float] = {}
_lock = threading.Lock()


def erlaubt_url(url: str) -> bool:
    """Nur öffentliche http(s)-Adressen ohne Zugangsdaten in der Adresse; keine Rechner im eigenen Netz."""
    try:
        p = urlparse(url)
    except ValueError:
        return False
    host = (p.hostname or "").lower()
    if p.scheme not in ("http", "https") or not host or p.username or p.password:
        return False
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return "." in host
    return ip.is_global


def robots_erlaubt(url: str) -> bool:
    """robots.txt des Hosts: nicht erreichbar/fehlend = erlaubt, 401/403 = gesperrt (übliche Auslegung)."""
    p = urlparse(url)
    key = f"{p.scheme}://{p.netloc}"
    with _lock:
        known = key in _robots
        rp = _robots.get(key)
    if not known:
        rp = RobotFileParser()
        try:
            r = requests.get(key + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=8)
            if r.status_code in (401, 403):
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp = None
            else:
                rp.parse(r.text.splitlines())
        except requests.RequestException:
            rp = None
        with _lock:
            _robots[key] = rp
    return True if rp is None else rp.can_fetch(UA_TOKEN, url)


def _pause(host: str) -> None:
    with _lock:
        wait = PAUSE_JE_HOST - (time.monotonic() - _zuletzt.get(host, 0.0))
        _zuletzt[host] = time.monotonic() + max(0.0, wait)
    if wait > 0:
        time.sleep(wait)


def hole(url: str, timeout: float = TIMEOUT, max_bytes: int = MAX_BYTES, headers: dict | None = None,
         pruefe_robots: bool = True) -> dict:
    """{"url", "status", "text", "last_modified", "typ"}; wirft WebFehler. Keine Cookies (zustandsloser Abruf)."""
    if not erlaubt_url(url):
        raise WebFehler("Adresse nicht erlaubt")
    if pruefe_robots and not robots_erlaubt(url):
        raise WebFehler("robots.txt verbietet den Abruf")
    _pause(urlparse(url).hostname or "")
    hdr = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
           "Accept-Language": "de,en;q=0.7", **(headers or {})}
    try:
        with requests.get(url, headers=hdr, timeout=timeout, stream=True, allow_redirects=True) as r:
            if not erlaubt_url(r.url):
                raise WebFehler("Weiterleitung auf nicht erlaubte Adresse")
            if r.status_code in (401, 402, 403, 407):
                raise WebFehler(f"Zugang verlangt oder verweigert (HTTP {r.status_code})")
            if r.status_code >= 400:
                raise WebFehler(f"HTTP {r.status_code}")
            typ = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if typ and not typ.startswith(TYPEN):
                raise WebFehler(f"Inhaltstyp {typ} nicht lesbar")
            raw = b""
            for chunk in r.iter_content(65536):
                raw += chunk
                if len(raw) >= max_bytes:
                    break
            enc = r.encoding if r.encoding and "iso-8859-1" not in r.encoding.lower() else (r.apparent_encoding or "utf-8")
            return {"url": r.url, "status": r.status_code, "typ": typ, "last_modified": r.headers.get("Last-Modified", ""),
                    "text": raw.decode(enc, errors="replace")}
    except requests.RequestException as exc:
        raise WebFehler(f"{type(exc).__name__}") from exc


def user_agent_fuer_api() -> str:
    return config.USER_AGENT
