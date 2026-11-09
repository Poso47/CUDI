"""Instagram Reels über die offizielle Graph API (Resumable Upload, lokale Datei).

Zugang NUR über Umgebungsvariablen: CUDI_IG_USER_ID (Instagram-Konto-ID), CUDI_IG_ACCESS_TOKEN (langlebiger Token),
optional CUDI_IG_API_VERSION (Standard v25.0). Ablauf laut Meta-Dokumentation (content-publishing/resumable-uploads):
1. Container: POST graph.facebook.com/<v>/<IG_USER_ID>/media (upload_type=resumable, media_type=REELS, caption)
2. Datei:     POST rupload.facebook.com/ig-api-upload/<v>/<Container> (Header offset, file_size)
3. Status:    GET  <Container>?fields=status_code bis FINISHED
4. Freigabe:  POST <IG_USER_ID>/media_publish?creation_id=<Container>

Instagram kennt kein „privat“/„ungelistet“: ein Reel ist sofort öffentlich. Deshalb wird nur bei Sichtbarkeit
„oeffentlich“ hochgeladen – sonst Fehler, damit nichts versehentlich öffentlich wird. Beim Bau lag noch kein echter
Zugang vor: der Weg ist per Test mit Attrappen geprüft, gegen die echte API noch nicht.
"""

from __future__ import annotations

import os
import re
import time

from . import Material, UploadError, fail, http, pause, redact, require, retryable, RETRIES

GRAPH = "https://graph.facebook.com"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload"
STANDARD_VERSION = "v25.0"
POLL_EVERY = 20.0          # Sekunden (Tests setzen 0)
POLL_MAX = 15 * 60
CAPTION_MAX = 2200
HASHTAGS_MAX = 30


def _version() -> str:
    v = os.environ.get("CUDI_IG_API_VERSION", "").strip()
    return v if re.fullmatch(r"v\d+\.\d+", v) else STANDARD_VERSION


def caption(material: Material) -> str:
    text = (material.caption or material.title or "").strip()
    tags = re.findall(r"#\w+", text)
    if len(tags) > HASHTAGS_MAX:                          # Instagram lehnt mehr als 30 Hashtags ab
        for extra in tags[HASHTAGS_MAX:]:
            text = text.replace(extra, "", 1)
    return text[:CAPTION_MAX]


def plan(material: Material, visibility: str = "oeffentlich") -> dict:
    """Trockenlauf: was gesendet würde – ohne Netz, ohne Geheimnisse."""
    size = material.video.stat().st_size if material.video.exists() else 0
    return {"ziel": "instagram", "datei": str(material.video), "groesse_mb": round(size / 1048576, 1),
            "typ": "REELS", "caption": caption(material), "api": _version(),
            "hinweis": "Reels sind sofort öffentlich – hochgeladen wird nur mit Sichtbarkeit „oeffentlich“.",
            "zugang": {n: ("gesetzt" if os.environ.get(n) else "fehlt") for n in
                       ("CUDI_IG_USER_ID", "CUDI_IG_ACCESS_TOKEN")}}


def _json(resp) -> dict:
    try:
        d = resp.json()
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def upload(material: Material, visibility: str = "oeffentlich") -> dict:
    """Reel hochladen und veröffentlichen. Rückgabe {id, url, sichtbarkeit}."""
    if visibility != "oeffentlich":
        raise UploadError("Instagram kennt kein privat/ungelistet – Reels sind sofort öffentlich. "
                          "Bitte Sichtbarkeit „oeffentlich“ wählen, wenn das gewollt ist.")
    cred = require("CUDI_IG_USER_ID", "CUDI_IG_ACCESS_TOKEN")
    user, token, ver = cred["CUDI_IG_USER_ID"], cred["CUDI_IG_ACCESS_TOKEN"], _version()
    auth = {"Authorization": f"OAuth {token}"}
    size = material.video.stat().st_size

    container = {}
    for attempt in range(RETRIES):
        resp = http("POST", f"{GRAPH}/{ver}/{user}/media",
                    data={"upload_type": "resumable", "media_type": "REELS", "caption": caption(material)}, headers=auth)
        container = _json(resp)
        if resp.status_code == 200 and container.get("id") and container.get("uri"):
            break
        if not retryable(resp.status_code) or attempt == RETRIES - 1:
            raise fail("Instagram-Container konnte nicht angelegt werden", resp, (token,))
        pause(attempt)
    cid, uri = str(container["id"]), str(container["uri"])

    data = material.video.read_bytes()
    for attempt in range(RETRIES):
        resp = http("POST", uri, headers={**auth, "offset": "0", "file_size": str(size)}, data=data, timeout=600)
        if resp.status_code == 200 and _json(resp).get("success", True):
            break
        if not retryable(resp.status_code) or attempt == RETRIES - 1:
            raise fail("Instagram-Upload abgelehnt", resp, (token,))
        pause(attempt)

    waited = 0.0
    while True:
        resp = http("GET", f"{GRAPH}/{ver}/{cid}", params={"fields": "status_code,status"}, headers=auth)
        code = _json(resp).get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise UploadError(redact(f"Instagram-Verarbeitung fehlgeschlagen ({code}): {_json(resp).get('status', '')}", (token,)))
        if waited >= POLL_MAX:
            raise UploadError(f"Instagram verarbeitet zu lange (Status {code}) – Container {cid} später prüfen.")
        time.sleep(POLL_EVERY)
        waited += max(POLL_EVERY, 1.0)

    for attempt in range(RETRIES):
        resp = http("POST", f"{GRAPH}/{ver}/{user}/media_publish", data={"creation_id": cid}, headers=auth)
        out = _json(resp)
        if resp.status_code == 200 and out.get("id"):
            return {"id": str(out["id"]), "url": "https://www.instagram.com/reels/", "sichtbarkeit": "oeffentlich"}
        if not retryable(resp.status_code) or attempt == RETRIES - 1:
            raise fail("Instagram-Veröffentlichung fehlgeschlagen", resp, (token,))
        pause(attempt)
    raise UploadError("Instagram-Veröffentlichung fehlgeschlagen")
