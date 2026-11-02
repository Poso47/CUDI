"""Kommandozeile.

Beispiele:
  python -m cudi_video presets                      # verfügbare Vorlagen
  python -m cudi_video make hoechste-gebaeude       # Video (DE + EN) erzeugen
  python -m cudi_video make "die tiefsten Seen der Welt" --count 7   # freies Thema
  python -m cudi_video make presets/meins.yaml --langs de --nur-skript
  python -m cudi_video story "gruselige Story über einen Stalker im Wald"   # Reddit-Story-Video (Autopilot)
  python -m cudi_video story --stimmung funny --suchen                      # nur Vorschläge anzeigen
  python -m cudi_video story https://www.reddit.com/r/tifu/comments/abc123/ --nur-skelett
  python -m cudi_video auftrag '{"id": "a1b2", "art": "story", "stimmung": "creepy"}'   # Auftrag der CUDI-App
  python -m cudi_video web                          # Web-Oberfläche (auch fürs Handy)
  python -m cudi_video check                        # Selbsttest (bei Problemen zuerst ausführen)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import config


def _load(spec_arg: str, count: int | None):
    """Vorlagen-ID, YAML-Datei oder freies Thema ("die höchsten Berge der Alpen")."""
    from .spec import VideoSpec, find_preset, load_spec
    from .topics import plan_from_text

    path = Path(spec_arg)
    if path.suffix in (".yaml", ".yml") and path.exists():
        return load_spec(path, count)
    try:
        return find_preset(spec_arg, count)
    except KeyError:
        spec = VideoSpec.from_dict(plan_from_text(spec_arg, count))
        print(f"Thema verstanden: {spec.title['de']} / {spec.title['en']}")
        return spec


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cudi_video", description="Ranking-Faktenvideos für TikTok & YouTube Shorts")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("presets", help="Vorlagen anzeigen")

    mk = sub.add_parser("make", help="Video erzeugen")
    mk.add_argument("spec", help="Vorlagen-ID, Pfad zu einer YAML-Datei oder freies Thema in Anführungszeichen")
    mk.add_argument("--langs", default=None, help="z. B. de,en")
    mk.add_argument("--count", type=int, default=None, help="Anzahl Plätze (3–20)")
    mk.add_argument("--nur-skript", action="store_true", help="nur Recherche + Skript + Prüfbericht")
    mk.add_argument("--ohne-ki", action="store_true", help="kein Sprachmodell verwenden")
    mk.add_argument("--ohne-bilder", action="store_true", help="keine Commons-Bilder laden")
    mk.add_argument("--streng", action="store_true",
                    help="abbrechen, wenn ein Platz nicht von mindestens einer unabhängigen Quelle bestätigt ist")

    st = sub.add_parser("story", help="Reddit-Story-Video erzeugen")
    st.add_argument("wunsch", nargs="?", default="", help="Beschreibung („lustige Story über meinen Chef“) oder Reddit-Link")
    st.add_argument("--stimmung", choices=["creepy", "suspense", "funny", "drama", "revenge", "wholesome"])
    st.add_argument("--sprache", default="de", choices=["de", "en"])
    st.add_argument("--laenge", default="3min", choices=["kurz", "3min", "teile"])
    st.add_argument("--bilder", default="videos", choices=["videos", "images", "gameplay"])
    st.add_argument("--suchen", action="store_true", help="nur passende Storys anzeigen")
    st.add_argument("--nur-skelett", action="store_true", help="Skelett erstellen (story.json zum Bearbeiten), noch kein Video")
    st.add_argument("--ordner", help="bearbeitetes Skelett aus diesem Ausgabeordner rendern")
    st.add_argument("--nicht-entschaerfen", action="store_true", help="Kraftausdrücke nicht ersetzen")

    au = sub.add_parser("auftrag", help="Auftrag aus der CUDI-App (läuft in einer Claude-Cloud-Sitzung)")
    au.add_argument("auftrag", nargs="?", default="", help="Auftrag als JSON")
    au.add_argument("--weiter", metavar="ID", help="nach Claudes Übersetzung weiterrendern")
    au.add_argument("--dokument", metavar="ID", help="Dokument für die Ablage der App-Seite bauen")
    au.add_argument("--adressen", help='hochgeladene Dateien als JSON {"datei": "url"}')

    chk = sub.add_parser("check", help="Selbsttest: ffmpeg, Schriften, Stimme, Datenquellen")
    chk.add_argument("--ohne-netz", action="store_true", help="nur lokale Prüfungen")
    chk.add_argument("--ohne-stimme", action="store_true", help="KI-Stimme nicht testen")

    web = sub.add_parser("web", help="Web-Oberfläche starten")
    web.add_argument("--host", default="0.0.0.0")
    web.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    # Windows-Konsolen nutzen oft cp1252 -> Zeichen wie ✓ oder ⚠️ würden sonst abstürzen
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    if args.cmd == "story":
        return _story(args)

    if args.cmd == "auftrag":
        from .job import main as job_main

        return job_main(args)

    if args.cmd == "check":
        from .check import print_report, run_checks

        logging.getLogger().setLevel(logging.ERROR)
        print("CUDI Video – Selbsttest\n")
        rows, ready = run_checks(network=not args.ohne_netz, voice=not (args.ohne_stimme or args.ohne_netz))
        print_report(rows, ready)
        return 0 if ready else 1

    if args.cmd == "presets":
        from .spec import list_presets

        for spec in list_presets():
            print(f"{spec.id:24s} {spec.title.get('de', '')}")
        return 0

    if args.cmd == "make":
        from .pipeline import run

        spec = _load(args.spec, args.count)
        langs = args.langs.split(",") if args.langs else None
        result = run(
            spec, langs=langs, render=not args.nur_skript,
            use_llm=False if args.ohne_ki else None, images=not args.ohne_bilder, strict=args.streng,
            progress=lambda stage, f: print(f"[{f * 100:5.1f} %] {stage}", flush=True),
        )
        print(f"\nAusgabe: {result['output_dir']}")
        for lang, files in result["videos"].items():
            print(f"  {lang}: {files['video']} ({files['duration']} s)")
        for w in result["warnings"]:
            print(f"  ⚠️  {w}")
        return 0

    if args.cmd == "web":
        import uvicorn

        if args.host not in ("127.0.0.1", "localhost") and not config.WEB_TOKEN:
            print("Hinweis: Kein CUDI_VIDEO_TOKEN gesetzt – jeder im Netzwerk kann die Oberfläche nutzen.")
        ip = _lan_address() if args.host == "0.0.0.0" else None
        if ip:
            print(f"Vom Handy im selben WLAN öffnen:  http://{ip}:{args.port}")
        uvicorn.run("cudi_video.web.app:app", host=args.host, port=args.port)
        return 0
    return 1


def _story(args) -> int:
    from .story import pipeline

    def progress(stage: str, f: float) -> None:
        print(f"  {f:4.0%}  {stage}", flush=True)

    soften = not args.nicht_entschaerfen
    link = args.wunsch if "reddit.com" in args.wunsch or "redd.it" in args.wunsch else ""
    if args.ordner:
        result = pipeline.render(Path(args.ordner), progress=progress)
    elif args.suchen:
        found = pipeline.search(args.wunsch, args.stimmung, args.sprache, args.laenge)
        print(f"Stimmung: {found['plan']['mood']} · Stichwörter: {', '.join(found['plan']['keywords']) or '–'}")
        for note in found["notes"]:
            print(f"  ℹ️  {note}")
        for st in found["stories"]:
            print(f"  ⬆ {st['score']:>6}  r/{st['subreddit']:<20} {st['words']:>5} Wörter  {st['title'][:70]}\n"
                  f"           {st['url']}")
        return 0
    elif args.nur_skelett:
        story = None
        if not link:
            found = pipeline.search(args.wunsch, args.stimmung, args.sprache, args.laenge, limit=1)
            if not found["stories"]:
                print(" ".join(found["notes"]))
                return 1
            story = found["stories"][0]
        skeleton, folder = pipeline.prepare(story=story, url=link, lang=args.sprache, mood=args.stimmung,
                                            length=args.laenge, visuals=args.bilder, soften=soften)
        print(f"Skelett: {folder / 'story.json'} ({len(skeleton['parts'])} Teil(e), Stimmung {skeleton['mood']})")
        for note in skeleton["notes"] + skeleton["rights"]:
            print(f"  ℹ️  {note}")
        print(f"Anpassen und dann rendern mit:  python -m cudi_video story --ordner \"{folder}\"")
        return 0
    else:
        result = pipeline.autopilot(description="" if link else args.wunsch, mood=args.stimmung, url=link,
                                    lang=args.sprache, length=args.laenge, visuals=args.bilder, soften=soften,
                                    progress=progress)
    print(f"\nAusgabe: {result['output_dir']}")
    for key, files in result["videos"].items():
        print(f"  {key}: {files['video']} ({files['duration']} s)")
    for w in result["warnings"]:
        print(f"  ⚠️  {w}")
    return 0


def _lan_address() -> str | None:
    """IP dieses Rechners im WLAN/LAN, damit man die Adresse fürs Handy nicht suchen muss."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))      # UDP: wählt nur die Netzwerkkarte aus, sendet nichts
            ip = s.getsockname()[0]
    except OSError:
        return None
    return None if ip.startswith("127.") else ip


if __name__ == "__main__":
    sys.exit(main())
