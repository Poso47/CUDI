"""Fertige Videos direkt zu YouTube Shorts und TikTok hochladen.

Zugangsdaten stehen NUR in Umgebungsvariablen (nie im Repo, nie in Ausgaben oder Logs):
  YouTube: CUDI_YT_CLIENT_ID, CUDI_YT_CLIENT_SECRET, CUDI_YT_REFRESH_TOKEN
  TikTok:  CUDI_TIKTOK_ACCESS_TOKEN (oder CUDI_TIKTOK_CLIENT_KEY/_CLIENT_SECRET/_REFRESH_TOKEN)
Einrichtung Schritt für Schritt: docs/upload-einrichten.md
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

log = logging.getLogger(__name__)

VISIBILITY = {"privat": "private", "ungelistet": "unlisted", "oeffentlich": "public", "öffentlich": "public"}
SECRET_VARS = ("CUDI_YT_CLIENT_ID", "CUDI_YT_CLIENT_SECRET", "CUDI_YT_REFRESH_TOKEN", "CUDI_TIKTOK_ACCESS_TOKEN",
               "CUDI_TIKTOK_CLIENT_KEY", "CUDI_TIKTOK_CLIENT_SECRET", "CUDI_TIKTOK_REFRESH_TOKEN")
RETRIES = 5
PAUSE = 2.0                 # Sekunden, verdoppelt sich je Versuch (Tests setzen 0)


class UploadError(RuntimeError):
    pass


def http(method: str, url: str, **kw) -> requests.Response:
    """Einziger Netzzugang des Uploads (Tests ersetzen ihn). Netzfehler werden zu Antworten mit Status 0."""
    kw.setdefault("timeout", 120)
    try:
        return requests.request(method, url, **kw)
    except requests.RequestException as exc:
        resp = requests.Response()
        resp.status_code = 0
        resp._content = type(exc).__name__.encode()
        return resp


def secrets() -> list[str]:
    """Aktuelle Geheimnisse (Werte der Umgebungsvariablen) – nur zum Schwärzen in Meldungen."""
    return [v for k in SECRET_VARS if len(v := os.environ.get(k, "")) >= 4]


def redact(text: object, extra: tuple = ()) -> str:
    out = str(text)
    for secret in [*secrets(), *[e for e in extra if e and len(str(e)) >= 4]]:
        out = out.replace(str(secret), "***")
    out = re.sub(r"(?i)(bearer\s+)[^\s\"',}]+", r"\1***", out)
    return re.sub(r"(?i)(access_token|refresh_token|client_secret|authorization)([\"'=: ]+)[^\s\"',&}]+", r"\1\2***", out)


def fail(what: str, resp: requests.Response, extra: tuple = ()) -> UploadError:
    return UploadError(redact(f"{what}: HTTP {resp.status_code} {resp.text[:300]}", extra))


def pause(attempt: int) -> None:
    time.sleep(PAUSE * 2 ** attempt)


def retryable(status: int) -> bool:
    return status == 0 or status == 429 or status >= 500


def require(*names: str) -> dict[str, str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise UploadError("Zugangsdaten fehlen (Umgebungsvariablen): " + ", ".join(missing)
                          + " – siehe docs/upload-einrichten.md")
    return {n: os.environ[n] for n in names}


@dataclass
class Material:
    video: Path
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    caption: str = ""            # TikTok-Text
    lang: str = ""


def _split_description(text: str) -> tuple[str, str]:
    """Beschreibungsdatei der Pipeline: erste Zeile = Titel, Rest = Beschreibung."""
    title, _, rest = text.strip().partition("\n")
    return title.strip(), rest.strip()


def _read(path: Path) -> str:
    try:
        return path.read_text("utf-8")
    except OSError:
        return ""


def material_for_file(video: Path, lang: str = "") -> Material:
    """Texte neben dem Video: <name>_beschreibung.txt (YouTube) und <name>_tiktok.txt (TikTok), sonst nur der Dateiname."""
    base = video.with_name(video.stem.removesuffix("_app"))
    title, description = _split_description(_read(base.with_name(base.name + "_beschreibung.txt")))
    caption = _read(base.with_name(base.name + "_tiktok.txt")).strip()
    tags = re.findall(r"#(\w+)", description.splitlines()[-1]) if description else []
    return Material(video=video, title=title or base.name.replace("_", " "), description=description, tags=tags,
                    caption=caption or title, lang=lang or (base.name.rsplit("_", 1)[-1] if "_" in base.name else ""))


def materials(source: str, lang: str = "") -> list[Material]:
    """Quelle = Pfad zu einer .mp4 oder eine Auftrags-ID (auftrag-<id>/ergebnis.json). Bei Aufträgen das Original
    in voller Qualität, nicht die verkleinerte App-Fassung."""
    path = Path(source)
    if path.suffix.lower() == ".mp4":
        if not path.exists():
            raise UploadError(f"Video nicht gefunden: {path}")
        return [material_for_file(path, lang)]
    from ..job import job_folder

    result = job_folder(source) / "ergebnis.json"
    if not result.exists():
        raise UploadError(f"Weder .mp4-Datei noch Auftrag gefunden: {source}")
    data = json.loads(result.read_text("utf-8"))
    out = []
    for v in data.get("videos", []):
        app = Path(v["video"])
        original = app.with_name(app.stem.removesuffix("_app") + app.suffix)
        video = original if original.exists() else app
        if lang and v.get("key") != lang:
            continue
        m = material_for_file(video, v.get("key", ""))
        out.append(m)
    if not out:
        raise UploadError(f"Auftrag {source} enthält kein passendes Video.")
    return out
