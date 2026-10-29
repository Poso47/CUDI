"""Kommandozeile.

Beispiele:
  python -m cudi_video presets                      # verfügbare Vorlagen
  python -m cudi_video make hoechste-gebaeude       # Video (DE + EN) erzeugen
  python -m cudi_video make presets/meins.yaml --langs de --nur-skript
  python -m cudi_video web                          # Web-Oberfläche (auch fürs Handy)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import config


def _load(spec_arg: str, count: int | None):
    from .spec import find_preset, load_spec

    path = Path(spec_arg)
    if path.suffix in (".yaml", ".yml") and path.exists():
        return load_spec(path, count)
    return find_preset(spec_arg, count)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cudi_video", description="Ranking-Faktenvideos für TikTok & YouTube Shorts")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("presets", help="Vorlagen anzeigen")

    mk = sub.add_parser("make", help="Video erzeugen")
    mk.add_argument("spec", help="Vorlagen-ID oder Pfad zu einer YAML-Datei")
    mk.add_argument("--langs", default=None, help="z. B. de,en")
    mk.add_argument("--count", type=int, default=None, help="Anzahl Plätze (3–20)")
    mk.add_argument("--nur-skript", action="store_true", help="nur Recherche + Skript + Prüfbericht")
    mk.add_argument("--ohne-ki", action="store_true", help="kein Sprachmodell verwenden")
    mk.add_argument("--ohne-bilder", action="store_true", help="keine Commons-Bilder laden")
    mk.add_argument("--streng", action="store_true",
                    help="abbrechen, wenn ein Platz nicht von mindestens einer unabhängigen Quelle bestätigt ist")

    web = sub.add_parser("web", help="Web-Oberfläche starten")
    web.add_argument("--host", default="0.0.0.0")
    web.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

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
        uvicorn.run("cudi_video.web.app:app", host=args.host, port=args.port)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
