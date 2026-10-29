"""Selbsttest: prüft alles, was für ein Video nötig ist, und sagt bei Fehlern, was zu tun ist.

Aufruf: python -m cudi_video check
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config


def _row(ok: bool | None, name: str, detail: str = "", hint: str = "") -> dict:
    return {"ok": ok, "name": name, "detail": detail, "hint": hint}


def _timed(fn):
    start = time.time()
    try:
        detail = fn()
        return True, f"{detail} ({time.time() - start:.1f}s)".strip()
    except Exception as exc:  # jeder Fehler ist hier eine Diagnose, kein Absturz
        return False, f"{type(exc).__name__}: {str(exc)[:140]}"


def check_local() -> list[dict]:
    rows = []
    ok = sys.version_info >= (3, 10)
    rows.append(_row(ok, "Python", sys.version.split()[0], "" if ok else "Python 3.10 oder neuer installieren (python.org)"))
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        version = ""
        if path:
            out = subprocess.run([tool, "-version"], capture_output=True, text=True).stdout.split("\n")[0]
            version = " ".join(out.split()[:3])
        rows.append(_row(bool(path), tool, version or "nicht gefunden",
                         "" if path else "Windows: winget install Gyan.FFmpeg – danach Fenster neu öffnen"))
    for module in ("requests", "bs4", "lxml", "yaml", "PIL", "numpy", "edge_tts", "fastapi", "uvicorn"):
        try:
            importlib.import_module(module)
            rows.append(_row(True, f"Paket {module}"))
        except ImportError:
            rows.append(_row(False, f"Paket {module}", "fehlt", "pip install -r cudi_video/requirements.txt"))
    try:
        from .render.theme import FONT_CANDIDATES, _font_index

        index = _font_index()
        for weight in ("black", "bold", "regular"):
            found = next((n for n in FONT_CANDIDATES[weight] if n.lower() in index), None)
            rows.append(_row(found is not None, f"Schrift {weight}", found or "Standardschrift (sieht schlechter aus)",
                             "" if found else "Inter installieren oder .ttf/.otf nach video_assets/fonts/ legen"))
    except Exception as exc:
        rows.append(_row(False, "Schriften", str(exc)))
    try:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        probe = config.OUTPUT_DIR / ".schreibtest"
        probe.write_text("ok")
        probe.unlink()
        rows.append(_row(True, "Ausgabeordner", str(config.OUTPUT_DIR)))
    except OSError as exc:
        rows.append(_row(False, "Ausgabeordner", str(exc), "CUDI_VIDEO_OUTPUT auf einen beschreibbaren Ordner setzen"))
    return rows


def check_network() -> list[dict]:
    from . import net

    def wikidata():
        data = net.get_json("https://query.wikidata.org/sparql", params={"query": "SELECT ?x WHERE { wd:Q183 wdt:P2046 ?x }"},
                            headers={"Accept": "application/sparql-results+json"}, cache_hours=0, retries=1)
        return f"Fläche Deutschland: {data['results']['bindings'][0]['x']['value']} km²"

    def wikipedia():
        data = net.get_json("https://de.wikipedia.org/api/rest_v1/page/summary/Zugspitze", cache_hours=0, retries=1)
        return data.get("title", "")

    def commons():
        data = net.get_json("https://commons.wikimedia.org/w/api.php",
                            params={"action": "query", "titles": "File:Flag of Germany.svg", "prop": "imageinfo",
                                    "iiprop": "extmetadata", "format": "json", "formatversion": 2},
                            cache_hours=0, retries=1)
        return data["query"]["pages"][0]["imageinfo"][0]["extmetadata"]["LicenseShortName"]["value"]

    def worldbank():
        data = net.get_json("https://api.worldbank.org/v2/country/DEU/indicator/SP.POP.TOTL",
                            params={"format": "json", "mrnev": 1}, cache_hours=0, retries=1)
        return f"Einwohner DEU {data[1][0]['date']}: {data[1][0]['value']:,}"

    def factbook():
        data = net.get_json("https://raw.githubusercontent.com/factbook/factbook.json/master/europe/gm.json",
                            cache_hours=0, retries=1)
        return "Deutschland geladen" if "Geography" in data else "unerwartetes Format"

    def overpass():
        data = net.get_json(config.OVERPASS_URL, params={"data": '[out:json][timeout:20];nwr["wikidata"="Q3375"];out tags 1;'},
                            cache_hours=0, retries=1)
        return f"{len(data.get('elements', []))} Objekt(e)"

    checks = [
        ("Wikidata (Pflicht)", wikidata, "Internet/Firewall prüfen – ohne Wikidata keine Rankings"),
        ("Wikipedia", wikipedia, "Ohne Wikipedia: weniger Zusatzsätze und Bestätigungen"),
        ("Wikimedia Commons", commons, "Ohne Commons: Grafik-Karten statt Fotos/Flaggen"),
        ("Weltbank", worldbank, "Ohne Weltbank: weniger Bestätigungen bei Ländern"),
        ("CIA World Factbook", factbook, "Ohne Factbook: weniger Bestätigungen bei Ländern"),
        ("OpenStreetMap", overpass, "Ohne OSM: weniger Bestätigungen bei Höhen"),
    ]
    rows = []
    for name, fn, hint in checks:
        ok, detail = _timed(fn)
        rows.append(_row(ok, name, detail, "" if ok else hint))
    return rows


def check_voice() -> dict:
    from .models import Script, Segment
    from .tts import voice_script

    def run():
        with tempfile.TemporaryDirectory() as tmp:
            script = Script(lang="de", title="Test", segments=[Segment(kind="intro", text="Test der KI-Stimme. Eins, zwei, drei.")])
            voice_script(script, Path(tmp))
            seg = script.segments[0]
            return f"{config.VOICES['de']}: {seg.duration:.1f}s, {len(seg.words)} Wörter mit Zeitstempel"

    ok, detail = _timed(run)
    return _row(ok, "KI-Stimme (edge-tts)", detail, "" if ok else "Internetverbindung zu Microsoft-Sprachdienst prüfen")


def check_optional() -> list[dict]:
    from . import llm

    rows = []
    if llm.available():
        ok, detail = _timed(lambda: llm.chat("Antworte nur mit OK.", "Test")[:20])
        rows.append(_row(ok, "Sprachmodell", detail, "" if ok else "CUDI_LLM_BASE_URL / _API_KEY / _MODEL prüfen"))
    else:
        rows.append(_row(None, "Sprachmodell", "nicht eingerichtet (optional)"))
    rows.append(_row(None if not config.FACTCHECK_API_KEY else True, "Faktencheck-Suche",
                     "eingerichtet" if config.FACTCHECK_API_KEY else "nicht eingerichtet (optional)"))
    rows.append(_row(None if not config.WEB_TOKEN else True, "Zugangscode Web",
                     "gesetzt" if config.WEB_TOKEN else "nicht gesetzt (für Cloud/WLAN empfohlen)"))
    return rows


def run_checks(network: bool = True, voice: bool = True) -> tuple[list[dict], bool]:
    rows = check_local()
    if network:
        rows += check_network()
    if voice:
        rows.append(check_voice())
    rows += check_optional()
    required = {"Python", "ffmpeg", "ffprobe", "Wikidata (Pflicht)", "KI-Stimme (edge-tts)", "Ausgabeordner"}
    ready = all(r["ok"] for r in rows if r["name"] in required or r["name"].startswith("Paket"))
    return rows, ready


def print_report(rows: list[dict], ready: bool) -> None:
    symbols = {True: "✓", False: "✗", None: "–"}
    for r in rows:
        line = f" {symbols[r['ok']]} {r['name']:<24} {r['detail']}"
        print(line.rstrip())
        if r["hint"]:
            print(f"   → {r['hint']}")
    print()
    print("Alles bereit – viel Spaß beim Erstellen!" if ready else
          "Es fehlt noch etwas Wichtiges (siehe ✗ oben). Danach den Test erneut starten.")
