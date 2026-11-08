"""Notbetrieb über GitHub Actions: App-Auftrag (JSON aus dem Issue) mit freiem Sprachmodell ausführen und melden.

Workflow „CUDI Notbetrieb“ (notbetrieb.yml) ruft zwei Schritte auf:

  python notbetrieb.py run     Auftrag aus $AUFTRAG prüfen (job.parse_order) und mit job.run_order(via_claude=False)
                               ausführen; Schreibaufgaben beantwortet das Sprachmodell (CUDI_LLM_*).
  python notbetrieb.py melden  Ergebnis als Kommentar ins Issue ($ISSUE), bei Erfolg Issue schließen.

Zugangsdaten kommen nur aus Umgebungsvariablen und erscheinen nie in Ausgaben (upload.redact).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MAX_COMMENT = 60_000
MAX_REVIEW = 6_000            # Kurzform; der volle Prüfbericht liegt als review.md im Artefakt
SECRET_ENV = ("CUDI_LLM_API_KEY", "CUDI_YT_CLIENT_SECRET", "CUDI_YT_REFRESH_TOKEN", "CUDI_TIKTOK_CLIENT_SECRET",
              "CUDI_TIKTOK_REFRESH_TOKEN", "CUDI_PEXELS_API_KEY", "CUDI_PIXABAY_API_KEY", "CUDI_DEEPL_API_KEY",
              "CUDI_REDDIT_CLIENT_SECRET", "CUDI_POLLINATIONS_TOKEN")


def scrub(text: object) -> str:
    """Gesetzte Geheimnisse aus Text entfernen (zusätzlich zu upload.redact)."""
    out = str(text or "")
    for name in SECRET_ENV:
        value = os.environ.get(name, "")
        if len(value) >= 6:
            out = out.replace(value, "***")
    return out


def defuse(text: str) -> str:
    return re.sub(r"@(?=\w)", "@​", text or "")


def fenced(text: str, lang: str = "text") -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{lang}\n{text.strip()}\n{fence}"


def prepare_order(raw: dict, presets: set[str]) -> dict:
    """Auftrag prüfen und für den Notbetrieb zurichten: nur Ranking/Story im ganzen Lauf; Hochladen direkt
    (es gibt keinen Freigabe-Knopf), außer der Auftrag setzt „freigabe“ ausdrücklich."""
    from cudi_video import job

    order = job.parse_order(raw, presets)
    if order["art"] not in ("ranking", "story"):
        raise job.OrderError("Im Notbetrieb gehen nur Rankings und Storys (Clips laufen in der App mit Claude).")
    if order.get("schritt"):
        raise job.OrderError("Im Notbetrieb läuft der Auftrag in einem Zug (ohne Zwischenschritte).")
    wish = order.get("hochladen")
    if wish and "freigabe" not in wish:
        wish["freigabe"] = False
    return order


# --------------------------------------------------------------------------- Kommentar

def comment_text(data: dict, run_url: str, artifact_url: str = "") -> str:
    """Kommentar fürs Issue aus ergebnis.json-Daten (reine Funktion – getestet)."""
    where = f"[Artefakt mit den Videos]({artifact_url})" if artifact_url else "Artefakt am Lauf"
    footer = f"Videos: {where} (Download nur mit GitHub-Anmeldung, 14 Tage) · Lauf: {run_url}"
    if not data or not data.get("ok"):
        error = scrub((data or {}).get("fehler") or "Der Lauf ist ohne Ergebnis beendet.")
        return "\n\n".join([
            "## ❌ Hat leider nicht geklappt", fenced(error[-2500:]),
            "Bitte später noch einmal versuchen (Sprachmodell-Limit?) oder den Auftrag in der CUDI-App starten.",
            f"Alle Details: {run_url}"])
    videos = data.get("videos") or []
    title = defuse(data.get("titel") or "Ergebnis")
    parts = [f"## ✅ Fertig: {title}" if videos else f"## ✅ Skript und Prüfbericht fertig: {title}"]
    for v in videos:
        key = v.get("key") or ""
        key = key[:2].upper() + key[2:]
        parts.append(f"### 🎬 {key}" + (f" · {round(v['dauer'])} s" if v.get("dauer") else ""))
        if v.get("youtube"):
            parts.append(f"**YouTube-Titel, Beschreibung, Hashtags {key}**\n\n{fenced(defuse(v['youtube']))}")
        if v.get("tiktok"):
            parts.append(f"**TikTok-Text {key}**\n\n{fenced(defuse(v['tiktok']))}")
    uploaded = data.get("hochgeladen") or []
    if uploaded:
        from cudi_video.job import upload_note
        parts.append("**Hochladen:**\n" + "\n".join(f"- {scrub(upload_note(e))}" for e in uploaded))
    notes = [h for h in data.get("hinweise") or [] if not re.match(r"(YouTube|TikTok): ", h)]
    if notes:
        parts.append("**⚠️ Hinweise:**\n" + "\n".join(f"- {scrub(defuse(n))}" for n in notes[:8])
                     + (f"\n- … und {len(notes) - 8} weitere" if len(notes) > 8 else ""))
    review = defuse(data.get("pruefbericht") or "").strip()
    if review:
        short = review[:MAX_REVIEW] + ("\n\n… (gekürzt – vollständig als review.md im Artefakt)" if len(review) > MAX_REVIEW else "")
        parts.append(f"<details><summary><b>Prüfbericht (Kurzform)</b></summary>\n\n{short}\n\n</details>")
    return ("\n\n".join(parts) + "\n\n" + footer)[:MAX_COMMENT]


# --------------------------------------------------------------------------- Schritte

def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def cmd_run() -> int:
    from cudi_video import job
    from cudi_video.spec import list_presets

    try:
        order = prepare_order(json.loads(os.environ["AUFTRAG"]), {s.id for s in list_presets()})
    except (job.OrderError, json.JSONDecodeError, KeyError) as exc:
        folder = job.job_folder("fehler")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "ergebnis.json").write_text(json.dumps({"ok": False, "fehler": f"Auftrag ungültig: {exc}"}), "utf-8")
        print(f"FEHLER: Auftrag ungültig: {exc}")
        return 2
    print(f"Notbetrieb-Auftrag {order['id']} ({order['art']})", flush=True)
    code, data = job.run_order(order, job.job_folder(order["id"]), via_claude=False)
    print("ERGEBNIS:", "ok" if data and data.get("ok") else scrub((data or {}).get("fehler", "kein Ergebnis"))[:300])
    return code


def cmd_melden() -> int:
    issue = os.environ.get("ISSUE", "")
    if not re.fullmatch(r"\d+", issue):
        print("Keine Issue-Nummer – nichts zu melden.")
        return 0
    from cudi_video import config

    repo = os.environ.get("GITHUB_REPOSITORY", "Poso47/CUDI")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    files = sorted(config.OUTPUT_DIR.glob("auftrag-*/ergebnis.json"), key=lambda p: p.stat().st_mtime)
    data = None
    if files:
        try:
            data = json.loads(files[-1].read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
    if data is None:
        log = Path("cudi.log")
        tail = "\n".join(log.read_text("utf-8", "replace").splitlines()[-12:]) if log.exists() else ""
        data = {"ok": False, "fehler": "Der Lauf ist ohne Ergebnis beendet." + (("\n" + tail) if tail else "")}
    text = comment_text(data, run_url, os.environ.get("ARTIFACT_URL", ""))
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as f:
        f.write(text + "\n\n<sub>CUDI · Notbetrieb · automatisch</sub>")
    gh("issue", "comment", issue, "--repo", repo, "--body-file", f.name)
    if data.get("ok"):
        gh("issue", "close", issue, "--repo", repo, "--reason", "completed", check=False)
    return 0


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"run": cmd_run, "melden": cmd_melden}.get(step, lambda: print("run | melden") or 2)())
