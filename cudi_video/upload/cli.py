"""Befehle `hochladen` und `youtube-login` sowie der Auftragsweg (Feld „hochladen“ in job.py)."""

from __future__ import annotations

import json
import logging

from . import Material, UploadError, materials, redact, tiktok, youtube

log = logging.getLogger(__name__)


def _targets(target: str) -> list[str]:
    return ["youtube", "tiktok"] if target == "beide" else [target]


def run_one(material: Material, target: str, visibility: str, mode: str = "inbox") -> dict:
    if target == "youtube":
        return youtube.upload(material, visibility)
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


def upload_order(wish: dict, data: dict) -> list[dict]:
    """Auftragsweg: lädt die fertigen Videos des Ergebnisses hoch. Fehler werden als Eintrag gemeldet, nie geworfen."""
    from pathlib import Path

    out = []
    for video in data.get("videos", []):
        app = Path(video["video"])
        original = app.with_name(app.stem.removesuffix("_app") + app.suffix)
        from . import material_for_file

        material = material_for_file(original if original.exists() else app, video.get("key", ""))
        for target in _targets(wish["ziel"]):
            entry = {"ziel": target, "sprache": video.get("key", "")}
            try:
                entry.update(run_one(material, target, wish["sichtbarkeit"]))
                entry["ok"] = True
            except Exception as exc:                  # noqa: BLE001
                entry.update(ok=False, fehler=redact(f"{type(exc).__name__}: {exc}")[:300])
            out.append(entry)
    return out


def youtube_login() -> int:
    try:
        path = youtube.login()
    except UploadError as exc:
        print(f"Fehler: {redact(exc)}")
        return 1
    print(f"Fertig. Der Refresh-Token liegt in {path} (nur auf diesem Rechner, nicht im Repo).")
    print("Für Server/Cloud: Inhalt der Datei als Umgebungsvariable CUDI_YT_REFRESH_TOKEN hinterlegen – "
          "nie in einen Chat oder ins Repo schreiben.")
    print(youtube.QUOTA_HINT)
    return 0
