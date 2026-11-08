"""YouTube Data API v3: Video hochladen (videos.insert, resumable) und einmaliger Browser-Login.

Quota: Ein Upload kostet etwa 1600 Einheiten, kostenlos stehen 10 000 pro Tag zur Verfügung (≈ 6 Uploads/Tag).
Ein nicht geprüftes API-Projekt lädt zunächst nur PRIVAT hoch (YouTube-Vorgabe) – siehe docs/upload-einrichten.md.
"""

from __future__ import annotations

import json
import os
import secrets as _secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from .. import config
from .. import upload as _up
from . import RETRIES, VISIBILITY, Material, UploadError, fail, pause, redact, require, retryable



def http(*args, **kw):
    return _up.http(*args, **kw)        # über das Paket, damit Tests den Netzzugang an einer Stelle ersetzen


TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
INIT_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
SCOPE_READ = "https://www.googleapis.com/auth/youtube.readonly"     # nur für den Lern-Analysten (Zahlen lesen)
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
READ_HINT = ("Scope youtube.readonly nötig: `python -m cudi_video youtube-login --lesen` ausführen und den neuen "
             "Refresh-Token als CUDI_YT_REFRESH_TOKEN hinterlegen (docs/lernen-einrichten.md) – oder öffentliche "
             "Videos mit CUDI_YT_API_KEY lesen.")
CHUNK = 8 * 1024 * 1024                  # Vielfaches von 256 KiB (Vorgabe der API)
QUOTA_HINT = "Quota: ein Upload kostet ca. 1600 von 10 000 freien Einheiten pro Tag."
TOKEN_FILE = "youtube_refresh_token.txt"


def token_file() -> Path:
    return config.OUTPUT_DIR / "_secrets" / TOKEN_FILE        # video_output/ ist gitignoriert


def refresh_token() -> str:
    """Refresh-Token aus CUDI_YT_REFRESH_TOKEN, sonst aus der lokalen Datei des Logins (nur am eigenen PC)."""
    value = os.environ.get("CUDI_YT_REFRESH_TOKEN", "")
    if not value and token_file().exists():
        value = token_file().read_text("utf-8").strip()
    if not value:
        raise UploadError("Zugangsdaten fehlen (Umgebungsvariablen): CUDI_YT_REFRESH_TOKEN – "
                          "zuerst `python -m cudi_video youtube-login`, siehe docs/upload-einrichten.md")
    return value


def access_token() -> str:
    creds = require("CUDI_YT_CLIENT_ID", "CUDI_YT_CLIENT_SECRET")
    refresh = refresh_token()
    resp = http("POST", TOKEN_URL, data={"client_id": creds["CUDI_YT_CLIENT_ID"],
                                         "client_secret": creds["CUDI_YT_CLIENT_SECRET"],
                                         "refresh_token": refresh, "grant_type": "refresh_token"})
    if resp.status_code != 200:
        raise fail("YouTube-Anmeldung fehlgeschlagen (Token abgelaufen? neu einloggen)", resp, (refresh,))
    return resp.json()["access_token"]


def snippet(material: Material, visibility: str = "privat") -> dict:
    """Body für videos.insert – Titel ≤ 100 Zeichen, #shorts im Text, Tags ≤ 500 Zeichen zusammen."""
    if visibility not in VISIBILITY:
        raise UploadError(f"Sichtbarkeit „{visibility}“ unbekannt – privat, ungelistet oder oeffentlich.")
    title = material.title.strip()[:100] or "Video"
    description = material.description.strip()
    if "#shorts" not in description.lower() and "#shorts" not in title.lower():
        description = (description + "\n\n#shorts").strip()
    tags, total = [], 0
    for tag in material.tags:
        total += len(tag) + 3
        if total > 480:
            break
        tags.append(tag)
    return {"snippet": {"title": title, "description": description[:4900], "tags": tags, "categoryId": "27",
                        "defaultLanguage": material.lang or "de"},
            "status": {"privacyStatus": VISIBILITY[visibility], "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": True}}


def plan(material: Material, visibility: str = "privat") -> dict:
    """Was gesendet würde (Trockenlauf) – ohne Netz, ohne Geheimnisse."""
    body = snippet(material, visibility)
    size = material.video.stat().st_size if material.video.exists() else 0
    return {"ziel": "youtube", "datei": str(material.video), "groesse_mb": round(size / 1048576, 1),
            "stuecke": max(1, -(-size // CHUNK)), "anfrage": body, "quota": QUOTA_HINT,
            "zugang": {n: ("gesetzt" if os.environ.get(n) else "fehlt") for n in
                       ("CUDI_YT_CLIENT_ID", "CUDI_YT_CLIENT_SECRET", "CUDI_YT_REFRESH_TOKEN")}}


def _start(token: str, material: Material, visibility: str, size: int) -> str:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
               "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"}
    body = json.dumps(snippet(material, visibility), ensure_ascii=False).encode("utf-8")
    for attempt in range(RETRIES):
        resp = http("POST", INIT_URL, params={"uploadType": "resumable", "part": "snippet,status"}, headers=headers,
                    data=body)
        if resp.status_code == 200 and resp.headers.get("Location"):
            return resp.headers["Location"]
        if not retryable(resp.status_code) or attempt == RETRIES - 1:
            raise fail("YouTube-Upload konnte nicht gestartet werden", resp, (token,))
        pause(attempt)
    raise UploadError("YouTube-Upload konnte nicht gestartet werden")


def _resume_offset(url: str, size: int) -> int:
    """Wie viele Bytes hat YouTube schon? (Statusabfrage nach einer Störung)"""
    resp = http("PUT", url, headers={"Content-Range": f"bytes */{size}", "Content-Length": "0"})
    if resp.status_code in (200, 201):
        return size
    if resp.status_code == 308:
        sent = resp.headers.get("Range", "")
        return int(sent.rsplit("-", 1)[-1]) + 1 if "-" in sent else 0
    return 0


def upload(material: Material, visibility: str = "privat") -> dict:
    """Video hochladen. Rückgabe {id, url, sichtbarkeit}. Störungen werden mit Wiederaufnahme wiederholt."""
    size = material.video.stat().st_size
    token = access_token()
    url = _start(token, material, visibility, size)
    offset, failures = 0, 0
    with material.video.open("rb") as fh:
        while True:
            fh.seek(offset)
            chunk = fh.read(CHUNK)
            end = offset + len(chunk) - 1
            resp = http("PUT", url, data=chunk, headers={"Content-Length": str(len(chunk)),
                                                         "Content-Type": "video/mp4",
                                                         "Content-Range": f"bytes {offset}-{end}/{size}"})
            if resp.status_code in (200, 201):
                vid = resp.json().get("id", "")
                return {"id": vid, "url": f"https://youtube.com/watch?v={vid}", "sichtbarkeit": visibility}
            if resp.status_code == 308:
                failures = 0
                sent = resp.headers.get("Range", "")
                offset = int(sent.rsplit("-", 1)[-1]) + 1 if "-" in sent else end + 1
                continue
            failures += 1
            if not retryable(resp.status_code) or failures >= RETRIES:
                raise fail("YouTube-Upload abgebrochen", resp, (token,))
            pause(failures - 1)
            offset = _resume_offset(url, size)


# --------------------------------------------------------------------------- einmaliger Browser-Login (am eigenen PC)

def login(open_browser: bool = True, read: bool = False) -> Path:
    """Browser-Login (OAuth „installierte App“ mit Loopback-Adresse). Schreibt den Refresh-Token in eine lokale,
    gitignorierte Datei (video_output/_secrets/…) und gibt ihn NICHT aus."""
    creds = require("CUDI_YT_CLIENT_ID", "CUDI_YT_CLIENT_SECRET")
    state = _secrets.token_urlsafe(16)
    result: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):                                   # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            result["code"] = (query.get("code") or [""])[0] if (query.get("state") or [""])[0] == state else ""
            result["error"] = (query.get("error") or [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h3>CUDI: Anmeldung abgeschlossen – du kannst dieses Fenster schließen.</h3>".encode())

        def log_message(self, *args):                       # keine Adressen (mit Code) in die Konsole
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{server.server_port}"
    link = AUTH_URL + "?" + urlencode({"client_id": creds["CUDI_YT_CLIENT_ID"], "redirect_uri": redirect,
                                       "response_type": "code", "scope": SCOPE + (" " + SCOPE_READ if read else ""),
                                       "access_type": "offline",
                                       "prompt": "consent", "state": state})
    print("Browser öffnet sich für die Google-Anmeldung. Falls nicht, diesen Link öffnen:\n" + link)
    if open_browser:
        threading.Thread(target=webbrowser.open, args=(link,), daemon=True).start()
    server.timeout = 300
    server.handle_request()
    server.server_close()
    if not result.get("code"):
        raise UploadError("Anmeldung abgebrochen oder abgelaufen" + (f" ({result.get('error')})" if result.get("error") else "") + ".")
    resp = http("POST", TOKEN_URL, data={"code": result["code"], "client_id": creds["CUDI_YT_CLIENT_ID"],
                                         "client_secret": creds["CUDI_YT_CLIENT_SECRET"], "redirect_uri": redirect,
                                         "grant_type": "authorization_code"})
    token = resp.json().get("refresh_token") if resp.status_code == 200 else None
    if not token:
        raise fail("Kein Refresh-Token erhalten (in den Google-Kontoeinstellungen den Zugriff von CUDI entfernen und "
                   "neu anmelden)", resp)
    path = token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, "utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


# --------------------------------------------------------------------------- Zahlen lesen (Lern-Analyst)

def video_stats(ids: list[str]) -> tuple[dict[str, dict], list[str]]:
    """Statistik der Videos (videos.list, part=statistics, 1 Quota-Einheit je 50 Videos).
    Rückgabe ({id: {views, likes, comments}}, Hinweise). Der Upload-Scope reicht NICHT zum Lesen: mit OAuth braucht es
    youtube.readonly; öffentliche Videos liefert auch ein API-Schlüssel (CUDI_YT_API_KEY). Fehler = Hinweis, kein Abbruch."""
    out: dict[str, dict] = {}
    notes: list[str] = []
    key = os.environ.get("CUDI_YT_API_KEY", "")
    token, denied = "", False
    if all(os.environ.get(n) for n in ("CUDI_YT_CLIENT_ID", "CUDI_YT_CLIENT_SECRET")):
        try:
            token = access_token()
        except UploadError:
            token = ""
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        for auth in ([("token", token)] if token else []) + ([("key", key)] if key else []):
            how, secret = auth
            resp = http("GET", VIDEOS_URL, params={"part": "statistics", "id": ",".join(chunk),
                                                   **({"key": secret} if how == "key" else {})},
                        headers={"Authorization": f"Bearer {secret}"} if how == "token" else None)
            if resp.status_code in (401, 403):
                denied = denied or how == "token"
                continue
            if resp.status_code != 200:
                notes.append(f"YouTube-Zahlen: HTTP {resp.status_code}")
                continue
            for item in resp.json().get("items", []):
                st = item.get("statistics") or {}
                out.setdefault(item["id"], {"views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                                            "comments": int(st.get("commentCount", 0))})
        if not (token or key):
            break
    if not (token or key):
        notes.append("YouTube-Zahlen: kein Zugang (CUDI_YT_REFRESH_TOKEN mit Lese-Scope oder CUDI_YT_API_KEY). " + READ_HINT)
    elif denied and len(out) < len(ids):
        notes.append("YouTube-Zahlen: Zugriff verweigert. " + READ_HINT)
    return out, [redact(n) for n in notes]
