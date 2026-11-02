"""Ergebnis eines Cloud-Laufs im Auftrag (GitHub-Issue) melden – für die CUDI-App-Seite.

- Videos und Cover landen als Dateien im Release „CUDI-Videos“ (Tag cudi-videos): direkte
  Download-Links fürs Handy, ohne ZIP. Die ältesten Dateien werden nach KEEP_ASSETS gelöscht.
- Kommentar im Issue: Titel, Dauer, Download-Links, TikTok- und YouTube-Text zum Kopieren,
  Hinweise vor dem Hochladen, Prüfbericht (aufklappbar) – oder verständlich die Fehlermeldung.
- Erfolgreiche Aufträge werden geschlossen, fehlgeschlagene bleiben offen (fallen so auf).

Aufruf: python report_issue.py <ausgabeordner> <log-datei> <art: ranking|story> <issue> [--nur-text]
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish_result import newest_output, summary  # noqa: E402

RELEASE_TAG = "cudi-videos"
KEEP_ASSETS = 80
MAX_COMMENT = 60_000          # GitHub erlaubt 65.536 Zeichen je Kommentar
MAX_REVIEW = 30_000


def asset_name(run_number: str, filename: str) -> str:
    """Eindeutiger, URL-sicherer Dateiname im Release: <Lauf>_<Datei>."""
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-.") or "video.mp4"
    return f"{run_number}_{clean}" if run_number else clean


def defuse(text: str) -> str:
    """@-Erwähnungen aus Story-/Wikipedia-Texten entschärfen – sonst benachrichtigt GitHub fremde Nutzer."""
    return re.sub(r"@(?=\w)", "@\u200b", text or "")


def fenced(text: str, lang: str = "text") -> str:
    """Codeblock (mit Kopier-Knopf auf GitHub), Zaun länger als jede Backtick-Folge im Text."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{lang}\n{text.strip()}\n{fence}"


def comment_text(data: dict, links: dict[str, dict[str, str]], run_url: str, release_url: str) -> str:
    """Kommentar fürs Issue (reine Funktion – getestet)."""
    if not data.get("ok"):
        error = data.get("error") or "Der Lauf ist ohne Ergebnis beendet."
        return "\n\n".join([
            "## ❌ Hat leider nicht geklappt",
            fenced(error[-3000:]),
            "Oft hilft es, den Auftrag in der CUDI-App mit einer anderen Stimmung oder Vorlage neu zu starten.",
            f"Alle Details: {run_url}",
        ])
    videos = data.get("videos") or []
    title = defuse(data.get("title") or "Ergebnis")
    parts = [f"## ✅ Fertig: {title}" if videos else f"## ✅ Skript und Prüfbericht fertig: {title}"]
    if not videos:
        parts.append("Es wurde wie gewünscht nur das Skript erstellt (kein Video). Der Prüfbericht steht unten.")
    for v in videos:
        key = v.get("key") or ""
        key = key[:2].upper() + key[2:]                 # „en · Teil 1“ -> „EN · Teil 1“
        link = links.get(v.get("file", ""), {})
        line = f"### 🎬 {key}" + (f" · {round(v['duration'])} s" if v.get("duration") else "")
        downloads = []
        if link.get("video"):
            downloads.append(f"[⬇️ **Video herunterladen**]({link['video']})")
        if link.get("cover"):
            downloads.append(f"[Titelbild]({link['cover']})")
        if not downloads:
            downloads.append(f"Video im Lauf als ZIP: {run_url}")
        parts += [line, " · ".join(downloads)]
        if v.get("tiktok"):
            parts += [f"**TikTok-Text {key}**", fenced(v["tiktok"])]
        if v.get("youtube"):
            parts.append(f"<details><summary><b>YouTube-Titel und Beschreibung {key}</b></summary>\n\n"
                         f"{fenced(v['youtube'])}\n\n</details>")
    warnings = data.get("warnings") or []
    if warnings:
        parts.append("**⚠️ Vor dem Hochladen prüfen:**\n" + "\n".join(f"- {defuse(w)}" for w in warnings[:8])
                     + (f"\n- … und {len(warnings) - 8} weitere im Prüfbericht" if len(warnings) > 8 else ""))
    body = "\n\n".join(parts)
    tail = f"Alle Videos: {release_url} · Lauf: {run_url}"
    review = defuse(data.get("review") or "").strip()
    if review:
        if len(review) > MAX_REVIEW:
            review = review[:MAX_REVIEW] + "\n\n… (gekürzt – vollständig im ZIP des Laufs)"
        block = f"<details><summary><b>Prüfbericht mit Quellen</b></summary>\n\n{review}\n\n</details>"
        if len(body) + len(block) + len(tail) + 4 <= MAX_COMMENT:    # Prüfbericht zuerst opfern, Downloads nie
            body += "\n\n" + block
        else:
            body += "\n\nPrüfbericht: zu lang für einen Kommentar – er liegt im ZIP des Laufs."
    return (body + "\n\n" + tail)[:MAX_COMMENT]


# --------------------------------------------------------------------------- GitHub

def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def ensure_release(repo: str) -> None:
    """Release „CUDI-Videos“ anlegen, falls es fehlt (zwei gleichzeitige Läufe: einer legt an, beide nutzen es)."""
    if gh("release", "view", RELEASE_TAG, "--repo", repo, check=False).returncode == 0:
        return
    gh("release", "create", RELEASE_TAG, "--repo", repo, "--title", "CUDI-Videos", "--prerelease",
       "--notes", "Fertige Videos aus der CUDI-App – wird automatisch gefüllt. "
                  "Die Dateinamen beginnen mit der Nummer des Laufs.", check=False)
    gh("release", "view", RELEASE_TAG, "--repo", repo)          # wirft, wenn es weiterhin fehlt


def upload(repo: str, output: Path, data: dict, run_number: str) -> dict[str, dict[str, str]]:
    """Videos und Cover ins Release laden; Rückgabe: Videodatei -> {video, cover} als Download-Links."""
    ensure_release(repo)
    links: dict[str, dict[str, str]] = {}
    base = f"https://github.com/{repo}/releases/download/{RELEASE_TAG}/"
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for v in data.get("videos", []):
            entry = {}
            for kind in ("file", "cover"):
                name = v.get(kind)
                if name and (output / name).exists():
                    target = Path(tmp) / asset_name(run_number, name)
                    shutil.copy2(output / name, target)
                    files.append(str(target))
                    entry["video" if kind == "file" else "cover"] = base + quote(target.name)
            links[v.get("file", "")] = entry
        if files:
            gh("release", "upload", RELEASE_TAG, *files, "--repo", repo, "--clobber")
    return links


def prune(repo: str) -> None:
    """Älteste Dateien aus dem Release löschen, damit die Liste übersichtlich bleibt."""
    res = gh("api", f"repos/{repo}/releases/tags/{RELEASE_TAG}", check=False)
    if res.returncode != 0:
        return
    assets = sorted(json.loads(res.stdout).get("assets", []), key=lambda a: a.get("created_at", ""))
    for old in assets[:-KEEP_ASSETS]:
        gh("api", "-X", "DELETE", f"repos/{repo}/releases/assets/{old['id']}", check=False)


def main() -> int:
    output_base, log, kind, issue = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    if not re.fullmatch(r"\d+", issue or ""):
        print("Keine Issue-Nummer – nichts zu melden.")
        return 0
    repo = os.environ.get("GITHUB_REPOSITORY", "Poso47/CUDI")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    release_url = f"{server}/{repo}/releases/tag/{RELEASE_TAG}"
    output = newest_output(output_base)
    data = summary(output, log, kind)
    links: dict[str, dict[str, str]] = {}
    if "--nur-text" not in sys.argv and data["ok"] and data["videos"] and output:
        try:
            links = upload(repo, output, data, os.environ.get("GITHUB_RUN_NUMBER", ""))
            prune(repo)
        except subprocess.CalledProcessError as exc:      # Download bleibt über das ZIP des Laufs möglich
            print("Hochladen ins Release fehlgeschlagen:", (exc.stderr or "")[-500:])
    text = comment_text(data, links, run_url, release_url)
    if "--nur-text" in sys.argv:
        print(text)
        return 0
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as f:
        f.write(text)                                  # als Datei: ein Argument darf höchstens 128 KB haben
    gh("issue", "comment", issue, "--repo", repo, "--body-file", f.name)
    if data["ok"]:
        gh("issue", "close", issue, "--repo", repo, "--reason", "completed", check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
