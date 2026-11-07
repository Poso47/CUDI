"""TikTok Content Posting API: Video hochladen.

* Standard: **Upload in die Inbox** (`/v2/post/publish/inbox/video/init/`, Scope `video.upload`) – das Video landet als
  Entwurf in der TikTok-App, dort wird Text ergänzt und veröffentlicht. Funktioniert ohne App-Review.
* **Direct Post** (`/v2/post/publish/video/init/`, Scope `video.publish`) erfordert die App-Prüfung durch TikTok;
  bis dahin sind nur Beiträge mit Sichtbarkeit „nur ich“ möglich.
Die Datei wird per FILE_UPLOAD in Stücken übertragen (PUT mit Content-Range).
"""

from __future__ import annotations

import os

from .. import upload as _up
from . import RETRIES, Material, UploadError, fail, pause, require, retryable

API = "https://open.tiktokapis.com"
INBOX_INIT = API + "/v2/post/publish/inbox/video/init/"
DIRECT_INIT = API + "/v2/post/publish/video/init/"
STATUS = API + "/v2/post/publish/status/fetch/"
TOKEN_URL = API + "/v2/oauth/token/"
MIN_CHUNK = 5 * 1024 * 1024
MAX_SINGLE = 64 * 1024 * 1024           # bis hierhin ein einziges Stück
CHUNK = 32 * 1024 * 1024
CAPTION_MAX = 2200
PRIVACY = {"privat": "SELF_ONLY", "ungelistet": "MUTUAL_FOLLOW_FRIENDS", "oeffentlich": "PUBLIC_TO_EVERYONE",
           "öffentlich": "PUBLIC_TO_EVERYONE"}
MODES = ("inbox", "direkt")


def http(*args, **kw):
    return _up.http(*args, **kw)


def chunking(size: int) -> tuple[int, int]:
    """(chunk_size, total_chunk_count) nach den TikTok-Regeln: unter 5 MB und bis 64 MB ein Stück; darüber Stücke
    von 32 MB, das letzte nimmt den Rest auf (bis 128 MB)."""
    if size <= MAX_SINGLE:
        return size, 1
    return CHUNK, size // CHUNK


def source_info(size: int) -> dict:
    chunk, count = chunking(size)
    return {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}


def init_body(material: Material, size: int, mode: str, visibility: str) -> dict:
    body = {"source_info": source_info(size)}
    if mode == "direkt":
        if visibility not in PRIVACY:
            raise UploadError(f"Sichtbarkeit „{visibility}“ unbekannt – privat, ungelistet oder oeffentlich.")
        body["post_info"] = {"title": (material.caption or material.title)[:CAPTION_MAX],
                             "privacy_level": PRIVACY[visibility], "disable_duet": False, "disable_comment": False,
                             "disable_stitch": False, "is_aigc": True}
    return body


def plan(material: Material, mode: str = "inbox", visibility: str = "privat") -> dict:
    size = material.video.stat().st_size if material.video.exists() else 0
    chunk, count = chunking(size) if size else (0, 0)
    return {"ziel": "tiktok", "modus": mode, "datei": str(material.video), "groesse_mb": round(size / 1048576, 1),
            "stuecke": count, "stueckgroesse_mb": round(chunk / 1048576, 1),
            "endpunkt": DIRECT_INIT if mode == "direkt" else INBOX_INIT,
            "anfrage": init_body(material, size, mode, visibility),
            "hinweis": ("Direct Post braucht die App-Prüfung durch TikTok; vorher nur „privat“ (nur ich)."
                        if mode == "direkt" else "Das Video erscheint als Entwurf in der TikTok-App (Inbox); dort veröffentlichen."),
            "zugang": {"CUDI_TIKTOK_ACCESS_TOKEN": "gesetzt" if os.environ.get("CUDI_TIKTOK_ACCESS_TOKEN") else
                       ("Refresh über Client-Key möglich" if all(os.environ.get(n) for n in (
                           "CUDI_TIKTOK_CLIENT_KEY", "CUDI_TIKTOK_CLIENT_SECRET", "CUDI_TIKTOK_REFRESH_TOKEN")) else "fehlt")}}


def refresh_access_token() -> str:
    creds = require("CUDI_TIKTOK_CLIENT_KEY", "CUDI_TIKTOK_CLIENT_SECRET", "CUDI_TIKTOK_REFRESH_TOKEN")
    resp = http("POST", TOKEN_URL, data={"client_key": creds["CUDI_TIKTOK_CLIENT_KEY"],
                                         "client_secret": creds["CUDI_TIKTOK_CLIENT_SECRET"],
                                         "grant_type": "refresh_token",
                                         "refresh_token": creds["CUDI_TIKTOK_REFRESH_TOKEN"]},
                headers={"Content-Type": "application/x-www-form-urlencoded"})
    token = resp.json().get("access_token") if resp.status_code == 200 else None
    if not token:
        raise fail("TikTok-Token konnte nicht erneuert werden", resp)
    os.environ["CUDI_TIKTOK_ACCESS_TOKEN"] = token                    # nur für diesen Lauf
    return token


def access_token() -> str:
    return os.environ.get("CUDI_TIKTOK_ACCESS_TOKEN") or refresh_access_token()


def _init(material: Material, size: int, mode: str, visibility: str) -> dict:
    url = DIRECT_INIT if mode == "direkt" else INBOX_INIT
    body = init_body(material, size, mode, visibility)
    refreshed = False
    for attempt in range(RETRIES):
        token = access_token()
        resp = http("POST", url, json=body, headers={"Authorization": f"Bearer {token}",
                                                     "Content-Type": "application/json; charset=UTF-8"})
        if resp.status_code == 401 and not refreshed and os.environ.get("CUDI_TIKTOK_REFRESH_TOKEN"):
            refreshed = True
            os.environ.pop("CUDI_TIKTOK_ACCESS_TOKEN", None)           # abgelaufen: einmal erneuern
            continue
        data = resp.json().get("data") if resp.status_code == 200 else None
        if data and data.get("upload_url"):
            return data
        if not retryable(resp.status_code) or attempt == RETRIES - 1:
            raise fail("TikTok-Upload konnte nicht gestartet werden", resp, (token,))
        pause(attempt)
    raise UploadError("TikTok-Upload konnte nicht gestartet werden")


def upload(material: Material, mode: str = "inbox", visibility: str = "privat") -> dict:
    """Video hochladen. Rückgabe {publish_id, modus, hinweis}."""
    if mode not in MODES:
        raise UploadError(f"TikTok-Modus „{mode}“ unbekannt – inbox oder direkt.")
    size = material.video.stat().st_size
    data = _init(material, size, mode, visibility)
    url, chunk_size, count = data["upload_url"], *chunking(size)
    with material.video.open("rb") as fh:
        for index in range(count):
            start = index * chunk_size
            end = size - 1 if index == count - 1 else start + chunk_size - 1        # letztes Stück nimmt den Rest
            fh.seek(start)
            payload = fh.read(end - start + 1)
            for attempt in range(RETRIES):
                resp = http("PUT", url, data=payload, headers={"Content-Type": "video/mp4",
                                                               "Content-Length": str(len(payload)),
                                                               "Content-Range": f"bytes {start}-{end}/{size}"})
                if resp.status_code in (200, 201, 206):
                    break
                if not retryable(resp.status_code) or attempt == RETRIES - 1:
                    raise fail(f"TikTok-Upload abgebrochen (Stück {index + 1}/{count})", resp)
                pause(attempt)
    return {"publish_id": data.get("publish_id", ""), "modus": mode,
            "hinweis": ("In der TikTok-App unter Posteingang/Entwürfe ergänzen und veröffentlichen."
                        if mode == "inbox" else "Beitrag wird von TikTok verarbeitet.")}


def status(publish_id: str) -> str:
    """Status des Beitrags (z. B. PROCESSING_UPLOAD, SEND_TO_USER_INBOX, PUBLISH_COMPLETE, FAILED) oder Leerstring."""
    resp = http("POST", STATUS, json={"publish_id": publish_id},
                headers={"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json; charset=UTF-8"})
    return (resp.json().get("data") or {}).get("status", "") if resp.status_code == 200 else ""
