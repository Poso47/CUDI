"""Ergebnis eines Cloud-Laufs für die CUDI-App-Seite ablegen.

Schreibt runs/<run_id>.json in den Zweig „cudi-ergebnisse“: Titel, Videos mit Dauer, YouTube- und
TikTok-Texte, Prüfbericht und – bei einem Fehler – die letzten Zeilen der Meldung. Die Seite in Claude
liest die Datei über die GitHub-Verbindung; die Videos selbst liegen als ZIP am Lauf.

Aufruf: python publish_result.py <ausgabeordner> <log-datei> <art: ranking|story> [--nur-datei]
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BRANCH = "cudi-ergebnisse"
MAX_REVIEW = 60_000


def newest_output(base: Path) -> Path | None:
    folders = [p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")] if base.exists() else []
    return max(folders, key=lambda p: p.stat().st_mtime, default=None)


def read(path: Path, limit: int = 20_000) -> str:
    try:
        return path.read_text("utf-8")[:limit]
    except OSError:
        return ""


def summary(output: Path | None, log: Path, kind: str) -> dict:
    run_id = os.environ.get("GITHUB_RUN_ID", "lokal")
    data = {
        "run_id": run_id, "run_number": os.environ.get("GITHUB_RUN_NUMBER", ""), "kind": kind,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ok": False,
        "title": "", "videos": [], "warnings": [], "review": "", "error": "",
    }
    result_file = output / "result.json" if output else None
    if result_file and result_file.exists():
        result = json.loads(result_file.read_text("utf-8"))
        data["ok"] = True
        data["warnings"] = result.get("warnings", [])[:20]
        for key, files in result.get("videos", {}).items():
            meta = files.get("metadata", {})
            data["videos"].append({
                "key": key, "file": files.get("video", ""), "cover": files.get("cover", ""), "duration": files.get("duration"),
                "title": meta.get("title", ""),
                "youtube": read(output / files["description_file"]) if files.get("description_file") else "",
                "tiktok": read(output / files["caption_file"]) if files.get("caption_file") else "",
            })
        spec = output / "spec.json"
        if spec.exists():
            titles = json.loads(spec.read_text("utf-8")).get("title", {})
            data["title"] = titles.get("de") or next(iter(titles.values()), "")
        data["review"] = read(output / "review.md", MAX_REVIEW)
    if not data["ok"]:
        lines = [l for l in read(log, 200_000).splitlines() if l.strip()]
        useful = [l for l in lines if "Error" in l or "Fehler" in l or "⚠" in l or "nicht" in l.lower()]
        data["error"] = "\n".join((useful or lines)[-12:])[-3000:] or "Der Lauf ist ohne Ergebnis beendet."
    return data


def push(data: dict) -> None:
    """Datei im Ergebnis-Zweig ablegen (eigener Arbeitsordner, der Haupt-Checkout bleibt unberührt)."""
    work = Path("/tmp/cudi-ergebnisse")
    git = ["git", "-C", str(work)]
    remote = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True).stdout.strip()
    # Zugangsdaten wie im Haupt-Checkout (actions/checkout legt sie als extraheader ab) – auch fürs Klonen
    header = subprocess.run(["git", "config", "--get", "http.https://github.com/.extraheader"],
                            capture_output=True, text=True).stdout.strip()
    auth = ["-c", f"http.https://github.com/.extraheader={header}"] if header else []
    subprocess.run(["rm", "-rf", str(work)], check=True)
    if subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", BRANCH], capture_output=True).returncode == 0:
        subprocess.run(["git", *auth, "clone", "--depth", "1", "--branch", BRANCH, remote, str(work)], check=True)
    else:
        work.mkdir(parents=True)
        subprocess.run(git + ["init", "-b", BRANCH], check=True)
        subprocess.run(git + ["remote", "add", "origin", remote], check=True)
        (work / "README.md").write_text("Ergebnisse der CUDI-Cloud-Läufe (für die CUDI-App-Seite). Wird automatisch geschrieben.\n")
    if header:
        subprocess.run(git + ["config", "http.https://github.com/.extraheader", header], check=True)
    runs = work / "runs"
    runs.mkdir(exist_ok=True)
    (runs / f"{data['run_id']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    # Nur die letzten 60 Ergebnisse behalten
    for old in sorted(runs.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-60]:
        old.unlink()
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["-c", "user.name=CUDI", "-c", "user.email=cudi@users.noreply.github.com", "commit", "-q", "-m",
                          f"Ergebnis Lauf {data['run_number']} ({data['kind']})"], check=True)
    for attempt in range(4):                       # parallele Läufe: bei Konflikt neu holen und erneut versuchen
        if subprocess.run(git + ["push", "-q", "origin", BRANCH]).returncode == 0:
            return
        subprocess.run(git + ["pull", "-q", "--rebase", "origin", BRANCH])
    raise SystemExit("Ergebnis konnte nicht abgelegt werden")


def main() -> int:
    output_base, log, kind = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    data = summary(newest_output(output_base), log, kind)
    if "--nur-datei" in sys.argv:
        print(json.dumps(data, ensure_ascii=False, indent=1)[:4000])
        return 0
    push(data)
    print(f"Ergebnis abgelegt: {BRANCH}/runs/{data['run_id']}.json ({'ok' if data['ok'] else 'Fehler'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
