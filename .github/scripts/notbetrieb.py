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
import shutil
import subprocess
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

NOTBETRIEB_ARTEN = ("ranking", "fakten", "erklaer", "story", "reportage", "satire", "clip", "schaubild")
SCHRITTE = ("bearbeiten", "hochladen")      # brauchen den Verweis „bezug“ auf das frühere Ergebnis
WARTEN = 600                                # Sekunden bis zum zweiten Versuch, wenn das Sprachmodell ausgefallen war
MAX_COMMENT = 60_000
MAX_REVIEW = 6_000            # Kurzform; der volle Prüfbericht liegt als review.md im Artefakt
SECRET_ENV = ("CUDI_LLM_API_KEY", "CUDI_LLM2_API_KEY", "CUDI_LLM3_API_KEY", "CUDI_YT_CLIENT_SECRET", "CUDI_YT_REFRESH_TOKEN", "CUDI_TIKTOK_CLIENT_SECRET",
              "CUDI_TIKTOK_REFRESH_TOKEN", "CUDI_TIKTOK_ACCESS_TOKEN", "CUDI_IG_ACCESS_TOKEN", "CUDI_PEXELS_API_KEY", "CUDI_PIXABAY_API_KEY", "CUDI_DEEPL_API_KEY",
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
    """Auftrag prüfen und für den Notbetrieb zurichten. Alle Arten laufen in einem Zug: ranking, fakten, erklaer, story,
    reportage, satire, clip (Erlaubnisprüfung läuft im Lauf). Story-Zwischenschritte „skelett“/„video“ werden zu
    „direkt Video“ (es gibt keine Bearbeiten-Ansicht). „bearbeiten“ (Ranking/Story, mit „aenderungen“) und „hochladen“
    gehen mit „bezug“ = Verweis auf das frühere Notbetrieb-Ergebnis (Issue-Nummer, optional „lauf“). Hochladen direkt
    (kein Freigabe-Knopf), außer der Auftrag setzt „freigabe“ ausdrücklich."""
    from cudi_video import job

    if isinstance(raw, dict) and raw.get("art") == "story" and str(raw.get("schritt") or "") in ("skelett", "video"):
        raw = {**raw, "schritt": ""}
    order = job.parse_order(raw, presets)
    if order["art"] not in NOTBETRIEB_ARTEN:
        raise job.OrderError("Diese Art gibt es im Notbetrieb nicht: " + ", ".join(NOTBETRIEB_ARTEN) + " gehen.")
    step = order.get("schritt")
    if step:
        if step not in SCHRITTE:
            raise job.OrderError("Im Notbetrieb gibt es die Schritte „bearbeiten“ und „hochladen“ (mit Verweis auf das frühere Ergebnis).")
        if not order.get("bezug"):
            raise job.OrderError(f"„{step}“ braucht im Notbetrieb den Verweis auf das frühere Ergebnis: \"bezug\": {{\"issue\": <Nummer des früheren Auftrags>}}.")
        if step == "bearbeiten" and order["art"] not in ("ranking", "story"):
            raise job.OrderError("Bearbeiten gibt es nur für Ranking und Story.")
    wish = order.get("hochladen")
    if wish and "freigabe" not in wish:
        wish["freigabe"] = False
    return order


# --------------------------------------------------------------------------- früheres Ergebnis holen

def pick_artifact(listing: list[dict], issue: int, lauf: int | None = None) -> dict | None:
    """Neuestes nicht abgelaufenes Artefakt „cudi-notbetrieb-<issue>-<lauf>“ aus der GitHub-Liste (reine Funktion)."""
    prefix = f"cudi-notbetrieb-{issue}-"
    found = [a for a in listing if str(a.get("name", "")).startswith(prefix) and not a.get("expired")
             and (lauf is None or a["name"] == f"{prefix}{lauf}")]
    return max(found, key=lambda a: a.get("created_at") or "", default=None)


def restore_earlier(order: dict, repo: str, runner=None) -> Path:
    """Artefakt des früheren Laufs holen und als Auftragsordner des Verweises ablegen (job.earlier_folder findet ihn dann).
    Ehrliche Fehler (RuntimeError), wenn es abgelaufen ist oder fehlt."""
    from cudi_video import config, job

    run = runner or gh
    bezug = order["bezug"]
    issue = int(bezug["id"][2:])
    listing: list[dict] = []
    for page in range(1, 6):
        resp = run("api", f"repos/{repo}/actions/artifacts?per_page=100&page={page}", check=False)
        try:
            batch = json.loads(resp.stdout or "{}").get("artifacts", [])
        except ValueError:
            batch = []
        listing += batch
        if len(batch) < 100:
            break
    art = pick_artifact(listing, issue, bezug.get("lauf"))
    if not art:
        raise RuntimeError(f"Das frühere Ergebnis (Auftrag #{issue}) ist nicht mehr da – Artefakte bleiben nur 14 Tage "
                           "erhalten, oder der frühere Lauf hat kein Video gebracht. Bitte das Video neu erstellen.")
    target = Path(tempfile.mkdtemp(prefix="frueher-"))
    got = run("run", "download", str((art.get("workflow_run") or {}).get("id", "")), "-n", art["name"], "-D", str(target),
              "--repo", repo, check=False)
    candidates = sorted(target.rglob("ergebnis.json"))
    if got.returncode != 0 or not candidates:
        raise RuntimeError(f"Das frühere Ergebnis (Auftrag #{issue}) ließ sich nicht herunterladen: "
                           f"{scrub((got.stderr or '')[-200:]) or 'Artefakt ohne ergebnis.json'}")
    source = next((c.parent for c in candidates if _result_id(c) == bezug["id"]), candidates[0].parent)
    dest = job.job_folder(bezug["id"])
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, dirs_exist_ok=True)
    return dest


def _result_id(path: Path) -> str:
    try:
        return str(json.loads(path.read_text("utf-8")).get("id", ""))
    except (OSError, ValueError):
        return ""


# --------------------------------------------------------------------------- Kommentar

def comment_text(data: dict, run_url: str, artifact_url: str = "") -> str:
    """Kommentar fürs Issue aus ergebnis.json-Daten (reine Funktion – getestet)."""
    where = f"[Artefakt mit den Videos]({artifact_url})" if artifact_url else "Artefakt am Lauf"
    footer = f"Videos: {where} (Download nur mit GitHub-Anmeldung, 14 Tage) · Lauf: {run_url}"
    if not data or not data.get("ok"):
        error = scrub((data or {}).get("fehler") or "Der Lauf ist ohne Ergebnis beendet.")
        return "\n\n".join([
            "## ❌ Hat leider nicht geklappt", fenced(error[-2500:]),
            ("Das Sprachmodell war auch beim zweiten Versuch (10 Minuten später) nicht erreichbar. Bitte später noch einmal "
             "starten – ein Fakten- oder Erklärvideo wird nie ohne Sprachmodell erfunden. " if data and data.get("modell_ausfall") else "")
            + "Bitte später noch einmal versuchen (Sprachmodell-Limit?) oder den Auftrag in der CUDI-App starten. "
            "Erfunden wird nichts: fehlen Quellen oder Belege, endet der Auftrag ehrlich.",
            f"Alle Details: {run_url}"])
    videos = data.get("videos") or []
    title = defuse(data.get("titel") or "Ergebnis")
    step = data.get("art_schritt")
    if step == "hochladen":
        parts = [f"## ✅ Hochgeladen: {title}" if title != "Ergebnis" else "## ✅ Hochgeladen"]
    elif step == "bearbeiten":
        parts = [f"## ✅ Neu gerendert mit deinen Änderungen: {title}"]
    else:
        parts = [f"## ✅ Fertig: {title}" if videos else f"## ✅ Skript und Prüfbericht fertig: {title}"]
    for v in videos:
        key = v.get("key") or ""
        key = key[:2].upper() + key[2:]
        parts.append(f"### 🎬 {key}" + (f" · {round(v['dauer'])} s" if v.get("dauer") else ""))
        variants = [t for t in (v.get("titel_varianten") or []) if isinstance(t, str) and t.strip()]
        if variants:
            chosen = v.get("titel_gewaehlt") or ""
            parts.append(f"**Titel-Varianten {key}**\n" + "\n".join(
                f"- {defuse(t)}" + (" ← gewählt" if t == chosen else "") for t in variants[:3]))
        if v.get("youtube"):
            parts.append(f"**YouTube-Titel, Beschreibung, Hashtags {key}**\n\n{fenced(defuse(v['youtube']))}")
        if v.get("tiktok"):
            parts.append(f"**TikTok-Text {key}**\n\n{fenced(defuse(v['tiktok']))}")
        if not v.get("youtube") and not v.get("tiktok"):
            parts.append(f"_Für dieses Video gibt es keinen fertigen Beschreibungstext – Titel oben, Prüfbericht unten._")
        befunde = [b for b in ((v.get("qa") or {}).get("befunde") or []) if isinstance(b, str)]
        if befunde:
            parts.append(f"**Endkontrolle {key}:** " + "; ".join(defuse(b) for b in befunde[:4]))
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


def run_with_retry(order: dict, run=None, sleep=time.sleep, wait: int | None = None) -> tuple[int, dict | None]:
    """Auftrag ausführen. War das Sprachmodell nicht erreichbar (`modell_ausfall`), einmal nach 10 Minuten erneut – nie
    endlos. Scheitert auch der zweite Versuch, steht der Grund klar im Ergebnis."""
    from cudi_video import job

    run = run or job.run_order
    folder = job.job_folder(order["id"])
    code, data = run(order, folder, via_claude=False)
    if not (data and not data.get("ok") and data.get("modell_ausfall")):
        return code, data
    pause = WARTEN if wait is None else wait
    print(f"Sprachmodell nicht erreichbar – zweiter Versuch in {pause // 60} Minuten (der letzte).", flush=True)
    sleep(pause)
    code, data = run(order, folder, via_claude=False)
    if data and not data.get("ok") and data.get("modell_ausfall"):
        data["fehler"] = (data.get("fehler") or "") + "\n(Zweiter Versuch nach 10 Minuten ebenfalls ohne Sprachmodell.)"
        try:
            (folder / "ergebnis.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
        except OSError:
            pass
    return code, data


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
    print(f"Notbetrieb-Auftrag {order['id']} ({order['art']}{', ' + order['schritt'] if order.get('schritt') else ''})", flush=True)
    if order.get("bezug"):
        try:
            restore_earlier(order, os.environ.get("GITHUB_REPOSITORY", "Poso47/CUDI"))
        except RuntimeError as exc:
            folder = job.job_folder(order["id"])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "ergebnis.json").write_text(json.dumps({"ok": False, "fehler": str(exc)}, ensure_ascii=False), "utf-8")
            print(f"FEHLER: {exc}")
            return 1
    code, data = run_with_retry(order)
    if order.get("bezug"):                                  # das geholte frühere Ergebnis nicht noch einmal ins neue Artefakt
        shutil.rmtree(job.job_folder(order["bezug"]["id"]), ignore_errors=True)
    print("ERGEBNIS:", "ok" if data and data.get("ok") else scrub((data or {}).get("fehler", "kein Ergebnis"))[:300])
    records = job.upload_records(order, data) if data else []          # für den Lern-Analysten (firma_daten/uploads.json)
    if records:
        from cudi_video import config
        (config.OUTPUT_DIR / "uploads_neu.json").write_text(json.dumps(records, ensure_ascii=False), "utf-8")
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
