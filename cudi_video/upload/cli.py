"""Befehle `hochladen` und `youtube-login` sowie der Auftragsweg (Feld „hochladen“ in job.py)."""

from __future__ import annotations

import json
import logging

from . import Material, UploadError, instagram, materials, redact, tiktok, youtube

log = logging.getLogger(__name__)


def _targets(target: str) -> list[str]:
    """„beide“ = YouTube + TikTok, „alle“ = zusätzlich Instagram; sonst ein einzelnes Ziel."""
    return {"beide": ["youtube", "tiktok"], "alle": ["youtube", "tiktok", "instagram"]}.get(target, [target])


def run_one(material: Material, target: str, visibility: str, mode: str = "inbox") -> dict:
    if target == "youtube":
        return youtube.upload(material, visibility)
    if target == "instagram":
        return instagram.upload(material, visibility)
    result = tiktok.upload(material, mode, visibility)
    try:                                              # Status ist nur Zugabe
        result["status"] = tiktok.status(result["publish_id"]) if result.get("publish_id") else ""
    except Exception:                                 # noqa: BLE001
        result["status"] = ""
    return result


def hochladen(args) -> int:
    """CLI. Gibt nie Zugangsdaten aus; Fehlermeldungen sind geschwärzt."""
    try:
        items = materials(args.quelle, args.sprache)
    except UploadError as exc:
        print(f"Fehler: {redact(exc)}")
        return 1
    visibility = args.sichtbarkeit.replace("ö", "oe")
    code = 0
    for material in items:
        for target in _targets(args.ziel):
            if args.probe:
                plan = (youtube.plan(material, visibility) if target == "youtube"
                        else instagram.plan(material, visibility) if target == "instagram"
                        else tiktok.plan(material, args.tiktok_modus, visibility))
                print(f"[Probe – nichts wird gesendet] {target}: {material.video.name}")
                print(json.dumps(plan, ensure_ascii=False, indent=1))
                continue
            try:
                result = run_one(material, target, visibility, args.tiktok_modus)
                print(f"{target}: hochgeladen – " + ", ".join(f"{k}={v}" for k, v in result.items() if v))
            except UploadError as exc:
                print(f"{target}: Fehler – {redact(exc)}")
                code = 1
    return code


def upload_materials(wish: dict, items: list) -> list[dict]:
    """Lädt [(Sprache, Material)] hoch. Fehler werden als Eintrag gemeldet, nie geworfen."""
    out = []
    for key, material in items:
        for target in _targets(wish["ziel"]):
            entry = {"ziel": target, "sprache": key}
            try:
                entry.update(run_one(material, target, wish["sichtbarkeit"]))
                entry["ok"] = True
            except Exception as exc:                  # noqa: BLE001
                entry.update(ok=False, fehler=redact(f"{type(exc).__name__}: {exc}")[:300])
            out.append(entry)
    return out


def upload_order(wish: dict, data: dict) -> list[dict]:
    """Auftragsweg: lädt die fertigen Videos des Ergebnisses hoch. Fehler werden als Eintrag gemeldet, nie geworfen."""
    from pathlib import Path

    from . import material_for_file

    items = []
    for video in data.get("videos", []):
        app = Path(video["video"])
        original = app.with_name(app.stem.removesuffix("_app") + app.suffix)
        items.append((video.get("key", ""), material_for_file(original if original.exists() else app, video.get("key", ""))))
    return upload_materials(wish, items)


def youtube_login(read: bool = False) -> int:
    try:
        path = youtube.login(read=read)
    except UploadError as exc:
        print(f"Fehler: {redact(exc)}")
        return 1
    print(f"Fertig. Der Refresh-Token liegt in {path} (nur auf diesem Rechner, nicht im Repo).")
    print("Für Server/Cloud: Inhalt der Datei als Umgebungsvariable CUDI_YT_REFRESH_TOKEN hinterlegen – "
          "nie in einen Chat oder ins Repo schreiben.")
    print(youtube.QUOTA_HINT)
    return 0


def tiktok_login(pasted: str = "", read: bool = False) -> int:
    """Einmaliger TikTok-Login. Desktop (Standard, localhost): Browser öffnet sich, CUDI fängt den Code selbst ab.
    Web (CUDI_TIKTOK_REDIRECT_URI = https-Seite): Rücksprung-Adresse wird hier eingefügt."""
    import secrets as _s
    import threading
    import webbrowser

    try:
        state, verifier = "", ""
        if pasted:
            code = tiktok.code_from(pasted)
        else:
            state = _s.token_urlsafe(12)
            local = tiktok.is_local(tiktok.redirect_uri())
            verifier, challenge = tiktok.pkce_pair() if local else ("", "")
            link = tiktok.authorize_url(state, challenge, read)
            print("Der Browser öffnet sich für die TikTok-Anmeldung. Falls nicht, diesen Link öffnen:\n\n   " + link + "\n")
            if local:
                threading.Thread(target=webbrowser.open, args=(link,), daemon=True).start()
                print("Warte auf die Anmeldung (bis 5 Minuten) …")
                code = tiktok.wait_for_code(state)
            else:
                print(f"Danach landest du auf {tiktok.redirect_uri()} – die GANZE Adresse kopieren und hier einfügen.")
                code = tiktok.code_from(input("Adresse oder Code: "), state)
        path = tiktok.save_refresh_token(tiktok.exchange_code(code, verifier))
    except (UploadError, OSError) as exc:
        print(f"Fehler: {redact(exc)}")
        return 1
    print(f"Fertig. Der Refresh-Token liegt in {path} (nur auf diesem Rechner, nicht im Repo, ca. 1 Jahr gültig).")
    print("Für die Cloud: Inhalt der Datei als Umgebungsvariable CUDI_TIKTOK_REFRESH_TOKEN hinterlegen – "
          "nie in einen Chat oder ins Repo schreiben.")
    return 0
