"""Auftrag aus der CUDI-App-Seite starten: vorausgefülltes GitHub-Issue -> passender Cloud-Ablauf.

Die App-Seite in Claude öffnet ein ausgefülltes Issue; nach „Absenden“ läuft dieses Skript
(Workflow „CUDI Auftrag“). Es prüft, dass der Auftrag vom Besitzer des Repositorys kommt, liest die
Angaben, prüft jede gegen eine Liste erlaubter Werte und startet „CUDI Video“ (Ranking) oder
„CUDI Story“ mit der Issue-Nummer. Der gestartete Lauf meldet das Ergebnis im selben Issue.

So braucht die App-Seite keine GitHub-Verbindung in Claude – nur den normalen GitHub-Login.

Aufruf (im Workflow): python auftrag.py        – liest das Ereignis aus $GITHUB_EVENT_PATH
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

MARKER = "cudi-auftrag"
LABEL = "cudi"
PRESETS_DIR = Path(__file__).resolve().parents[2] / "presets"
ALLOWED_AUTHORS = {"OWNER", "MEMBER", "COLLABORATOR"}

MOODS = {"auto": "auto", "creepy": "creepy", "gruselig": "creepy", "horror": "creepy",
         "suspense": "suspense", "spannend": "suspense", "funny": "funny", "lustig": "funny",
         "drama": "drama", "revenge": "revenge", "rache": "revenge", "wholesome": "wholesome",
         "herzlich": "wholesome", "herzerwaermend": "wholesome"}
LENGTHS = {"kurz": "kurz", "bis 1 minute": "kurz", "3min": "3min", "3 min": "3min", "bis 3 minuten": "3min",
           "teile": "teile", "lang": "teile", "lang in teilen": "teile", "in teilen": "teile"}
VISUALS = {"videos": "videos", "videos bevorzugt": "videos", "images": "images", "ki bilder": "images",
           "bilder": "images", "gameplay": "gameplay", "eigene clips": "gameplay"}
YES = {"ja", "yes", "true", "1", "an", "x", "wahr"}
NO = {"nein", "no", "false", "0", "aus", "falsch", ""}


def _norm(text: str) -> str:
    """Kleinschreibung, Umlaute ausgeschrieben, Satzzeichen zu Leerzeichen: „Plätze“ -> „plaetze“."""
    text = text.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def parse_body(body: str) -> dict[str, str]:
    """Zeilen „Feld: Wert“ einlesen (erstes Vorkommen zählt, unbekannte Felder werden ignoriert)."""
    fields: dict[str, str] = {}
    for line in (body or "").splitlines():
        m = re.match(r"^\s*([A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß _-]{0,30}?)\s*:\s*(.*?)\s*$", line)
        if m:
            fields.setdefault(_norm(m.group(1)), m.group(2))
    return fields


def _flag(value: str | None, default: bool, name: str) -> bool:
    if value is None:
        return default
    v = _norm(value)
    if v in YES:
        return True
    if v in NO:
        return False
    raise ValueError(f"„{name}“ bitte mit ja oder nein angeben (war: {value!r}).")


def _choice(value: str | None, table: dict[str, str], default: str, name: str) -> str:
    if value is None or not value.strip():
        return default
    key = _norm(value)
    for candidate in (key, key.split(" ")[0]):          # „Kurz (bis 1 Minute)“ -> „kurz“
        if candidate in table:
            return table[candidate]
    raise ValueError(f"„{name}“: {value!r} kenne ich nicht.")


def _clean_text(value: str | None, limit: int) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", value or "").strip()
    return re.sub(r"\s+", " ", text)[:limit]


def presets() -> set[str]:
    return {p.stem for p in PRESETS_DIR.glob("*.yaml")}


def build_order(fields: dict[str, str], known_presets: set[str]) -> tuple[str, dict[str, str]]:
    """Workflow-Datei und Eingaben für den Auftrag – oder ValueError mit verständlichem Grund."""
    kind = _norm(fields.get("art", ""))
    if kind in ("ranking", "rangliste", "top liste", "toplist"):
        topic = _clean_text(fields.get("thema"), 120)
        preset = _norm(fields.get("vorlage", "")).replace(" ", "-")
        if not topic:
            if not preset:
                raise ValueError("Bitte eine Vorlage oder ein eigenes Thema angeben.")
            if preset not in known_presets:
                raise ValueError(f"Die Vorlage „{fields.get('vorlage')}“ gibt es nicht. "
                                 f"Möglich: {', '.join(sorted(known_presets))}.")
        langs = [l for l in ("de", "en") if l in re.split(r"[^a-z]+", _norm(fields.get("sprachen", "de en")))]
        if not langs:
            raise ValueError("Bitte mindestens eine Sprache angeben (de, en).")
        try:
            count = int(_norm(fields.get("plaetze", "10")) or "10")
        except ValueError:
            raise ValueError("„Plätze“ bitte als Zahl von 3 bis 20 angeben.") from None
        if not 3 <= count <= 20:
            raise ValueError("„Plätze“ bitte als Zahl von 3 bis 20 angeben.")
        return "video.yml", {
            "preset": topic or preset, "langs": ",".join(langs), "count": str(count),
            "streng": str(_flag(fields.get("streng"), False, "Streng")).lower(),
            "nur_skript": str(_flag(fields.get("nur skript"), False, "Nur Skript")).lower(),
        }
    if kind in ("story", "reddit story", "geschichte"):
        wish = _clean_text(fields.get("wunsch"), 300)
        mood = _choice(fields.get("stimmung"), MOODS, "auto", "Stimmung")
        if not wish and mood == "auto":
            raise ValueError("Bitte eine Stimmung antippen oder kurz beschreiben, was für eine Story es sein soll.")
        lang = _norm(fields.get("sprache", "de")) or "de"
        lang = {"deutsch": "de", "englisch": "en", "english": "en", "german": "de"}.get(lang, lang)
        if lang not in ("de", "en"):
            raise ValueError("„Sprache“ bitte de oder en.")
        return "story.yml", {
            "wunsch": wish, "stimmung": mood, "sprache": lang,
            "laenge": _choice(fields.get("laenge"), LENGTHS, "3min", "Länge"),
            "bilder": _choice(fields.get("bilder"), VISUALS, "videos", "Bilder"),
            "entschaerfen": str(_flag(fields.get("entschaerfen"), True, "Entschärfen")).lower(),
        }
    raise ValueError("Unbekannte Art – „Art: Ranking“ oder „Art: Story“ angeben.")


def allowed(event: dict) -> bool:
    issue = event.get("issue", {})
    owner = event.get("repository", {}).get("owner", {}).get("login", "")
    author = issue.get("user", {}).get("login", "")
    return issue.get("author_association") in ALLOWED_AUTHORS or (author and author.lower() == owner.lower())


def summary_line(workflow: str, inputs: dict[str, str]) -> str:
    if workflow == "video.yml":
        extra = [x for x, on in (("streng", inputs["streng"] == "true"), ("nur Skript", inputs["nur_skript"] == "true")) if on]
        return (f"Ranking **{inputs['preset']}** · Sprachen {inputs['langs']} · Top {inputs['count']}"
                + (" · " + ", ".join(extra) if extra else ""))
    what = f"„{inputs['wunsch']}“" if inputs["wunsch"] else ""
    mood = "" if inputs["stimmung"] == "auto" else inputs["stimmung"]
    head = " ".join(x for x in (mood, what) if x) or "Story"
    return f"Story **{head}** · {inputs['sprache']} · {inputs['laenge']} · Bilder: {inputs['bilder']}"


# --------------------------------------------------------------------------- GitHub

def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def comment(repo: str, number: int, text: str) -> None:
    gh("issue", "comment", str(number), "--repo", repo, "--body", text + "\n\n<sub>CUDI · automatisch</sub>")


def main() -> int:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text("utf-8"))
    issue = event["issue"]
    repo = os.environ["GITHUB_REPOSITORY"]
    number = int(issue["number"])
    if MARKER not in (issue.get("body") or ""):
        print("Kein CUDI-Auftrag – nichts zu tun.")
        return 0
    if not allowed(event):
        comment(repo, number, "Aufträge kann nur der Besitzer dieses Repositorys geben.")
        gh("issue", "close", str(number), "--repo", repo, "--reason", "not planned", check=False)
        return 0
    gh("label", "create", LABEL, "--repo", repo, "--color", "2fd6f0", "--description", "Auftrag aus der CUDI-App",
       "--force", check=False)
    gh("issue", "edit", str(number), "--repo", repo, "--add-label", LABEL, check=False)
    try:
        workflow, inputs = build_order(parse_body(issue.get("body") or ""), presets())
    except ValueError as exc:
        comment(repo, number, f"❌ **Auftrag nicht verstanden:** {exc}\n\nBitte in der CUDI-App neu starten.")
        gh("issue", "close", str(number), "--repo", repo, "--reason", "not planned", check=False)
        return 0
    inputs["issue"] = str(number)
    branch = event.get("repository", {}).get("default_branch", "main")
    args = ["workflow", "run", workflow, "--repo", repo, "--ref", branch]
    for key, value in inputs.items():
        args += ["-f", f"{key}={value}"]
    started = gh(*args, check=False)
    if started.returncode != 0:
        comment(repo, number, "❌ **Der Cloud-Ablauf ließ sich nicht starten.**\n\n```text\n"
                + (started.stderr or started.stdout)[-1500:] + "\n```")
        return 1
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    comment(repo, number,
            f"✅ **Auftrag angenommen:** {summary_line(workflow, inputs)}\n\n"
            f"Der Cloud-Ablauf startet jetzt und braucht meist 10 bis 20 Minuten. Sobald das Video fertig ist, "
            f"steht es hier – mit Download-Links und den Texten für YouTube und TikTok.\n\n"
            f"Fortschritt: {server}/{repo}/actions/workflows/{workflow}")
    print(f"Gestartet: {workflow} {inputs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
