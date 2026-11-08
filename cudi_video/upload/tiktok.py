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


# ---------- Einmaliger Login (Code gegen Refresh-Token tauschen) ----------
AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
DEFAULT_REDIRECT = "http://localhost:8723/callback/"   # Desktop-Login (TikTok verlangt localhost:Port); Web: CUDI_TIKTOK_REDIRECT_URI
WEB_REDIRECT = "https://poso47.github.io/CUDI/tiktok/"   # kostenlose GitHub-Pages-Seite (docs/tiktok/) für Web-Apps
LOGIN_SCOPES = "video.upload"
READ_SCOPES = "video.upload,video.list"      # --lesen: zusätzlich eigene Videos mit Zahlen lesen (Lern-Analyst)
TOKEN_FILE = "tiktok_refresh_token.txt"


def redirect_uri() -> str:
    return os.environ.get("CUDI_TIKTOK_REDIRECT_URI") or DEFAULT_REDIRECT


def is_local(uri: str) -> bool:
    from urllib.parse import urlparse

    return urlparse(uri).hostname in ("localhost", "127.0.0.1")


def pkce_pair() -> tuple[str, str]:
    """PKCE für den Desktop-Login: TikTok verlangt SHA256 des Verifiers als Hex (nicht Base64)."""
    import hashlib
    import secrets as _s

    verifier = _s.token_urlsafe(48)[:64]
    return verifier, hashlib.sha256(verifier.encode()).hexdigest()


def authorize_url(state: str, challenge: str = "", read: bool = False) -> str:
    from urllib.parse import urlencode

    key = require("CUDI_TIKTOK_CLIENT_KEY")["CUDI_TIKTOK_CLIENT_KEY"]
    params = {"client_key": key, "scope": READ_SCOPES if read else LOGIN_SCOPES, "response_type": "code",
              "redirect_uri": redirect_uri(), "state": state}
    if challenge:
        params.update(code_challenge=challenge, code_challenge_method="S256")
    return AUTHORIZE_URL + "?" + urlencode(params)


def code_from(pasted: str, state: str = "") -> str:
    """Code aus der eingefügten Rücksprung-Adresse (oder dem nackten Code) lesen; prüft state, falls vorhanden."""
    from urllib.parse import parse_qs, unquote, urlparse

    text = pasted.strip()
    if "code=" not in text and "error=" not in text:
        if not text or any(c.isspace() for c in text) or "/" in text:
            raise UploadError("Kein Code gefunden – bitte die ganze Adresse aus dem Browser einfügen.")
        return unquote(text)
    query = parse_qs(urlparse(text).query or text.split("?", 1)[-1])
    if query.get("error"):
        raise UploadError(f"TikTok meldet: {query['error'][0]} – Login abgelehnt oder abgebrochen.")
    if state and query.get("state") and query["state"][0] != state:
        raise UploadError("Die Adresse gehört nicht zu diesem Login (state passt nicht) – bitte neu starten.")
    code = (query.get("code") or [""])[0]
    if not code:
        raise UploadError("Kein Code gefunden – bitte die ganze Adresse aus dem Browser einfügen.")
    return code


def exchange_code(code: str, verifier: str = "") -> str:
    creds = require("CUDI_TIKTOK_CLIENT_KEY", "CUDI_TIKTOK_CLIENT_SECRET")
    form = {"client_key": creds["CUDI_TIKTOK_CLIENT_KEY"], "client_secret": creds["CUDI_TIKTOK_CLIENT_SECRET"],
            "code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri()}
    if verifier:
        form["code_verifier"] = verifier
    resp = http("POST", TOKEN_URL, data=form, headers={"Content-Type": "application/x-www-form-urlencoded"})
    token = resp.json().get("refresh_token") if resp.status_code == 200 else None
    if not token:
        raise fail("TikTok-Code konnte nicht eingetauscht werden (Code abgelaufen oder Redirect-URI anders?)", resp)
    return token


def save_refresh_token(token: str):
    from .. import config

    path = config.OUTPUT_DIR / "_secrets" / TOKEN_FILE                # video_output/ ist gitignoriert
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def wait_for_code(state: str, timeout: int = 300) -> str:
    """Kleiner Server auf localhost fängt TikToks Rücksprung ab (Desktop-Login) – nichts zu kopieren."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse

    uri = urlparse(redirect_uri())
    got: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):                                   # noqa: N802
            got["url"] = self.path
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h3>CUDI: TikTok-Anmeldung erhalten – du kannst dieses Fenster schließen.</h3>".encode())

        def log_message(self, *args):                       # keine Adressen (mit Code) in die Konsole
            pass

    server = HTTPServer(("127.0.0.1", uri.port or 80), Handler)
    server.timeout = timeout
    try:
        while "url" not in got:
            before = dict(got)
            server.handle_request()
            if got == before:                               # Zeit abgelaufen
                raise UploadError("Keine Antwort von TikTok innerhalb von 5 Minuten – bitte neu starten.")
            if urlparse(got["url"]).path.rstrip("/") != uri.path.rstrip("/"):
                got.pop("url")                              # z. B. favicon.ico
    finally:
        server.server_close()
    return code_from("http://localhost" + got["url"], state)


# --------------------------------------------------------------------------- Zahlen lesen (Lern-Analyst)

LIST_URL = API + "/v2/video/list/"
READ_HINT = ("Scope video.list nötig: in der TikTok-App unter „Scopes“ video.list hinzufügen, dann "
             "`python -m cudi_video tiktok-login --lesen` und den neuen Refresh-Token als CUDI_TIKTOK_REFRESH_TOKEN "
             "hinterlegen (docs/lernen-einrichten.md).")


def video_list(max_count: int = 20) -> list[dict]:
    """Die letzten eigenen Videos mit Zahlen: [{title, create_time, views, likes, comments, shares}].
    Wirft UploadError mit READ_HINT, wenn der Token den Scope video.list nicht hat."""
    resp = http("POST", LIST_URL + "?fields=id,create_time,title,view_count,like_count,comment_count,share_count",
                json={"max_count": max(1, min(max_count, 20))},
                headers={"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json; charset=UTF-8"})
    if resp.status_code in (401, 403):
        raise UploadError("TikTok-Zahlen: Zugriff verweigert. " + READ_HINT)
    if resp.status_code != 200:
        raise fail("TikTok-Zahlen konnten nicht gelesen werden", resp)
    videos = ((resp.json().get("data") or {}).get("videos")) or []
    return [{"title": v.get("title", ""), "create_time": v.get("create_time", 0), "views": v.get("view_count", 0),
             "likes": v.get("like_count", 0), "comments": v.get("comment_count", 0), "shares": v.get("share_count", 0)}
            for v in videos]
