"""`python -m cudi_video.firma <trends|news|welt|briefing|ideen|putzen|lernen>` – führt einen Mitarbeiter einmal aus."""

from __future__ import annotations

import json
import logging
import os
import sys

from . import common


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if argv == ["export"]:                                # kompakte docs/firma/firma.json für die App
        from . import export
        print("firma.json", "geschrieben" if export.write() else "unverändert")
        return 0
    names = ("trends", "news", "ideen", "putzen", "lernen", "wissen", "welt", "briefing")
    if len(argv) == 2 and argv[0] == "uploads":              # Upload-Liste ergänzen (Notbetrieb-Workflow)
        from .lernen import main_merge
        return main_merge(argv[1:])
    if len(argv) != 1 or argv[0] not in names:
        print(f"Aufruf: python -m cudi_video.firma <{'|'.join(names)}|export> | uploads <datei>")
        return 2
    import time
    started = time.monotonic()
    try:
        module = __import__(f"cudi_video.firma.{argv[0]}", fromlist=["run"])
        data = module.run()
    except Exception as exc:                              # noqa: BLE001 – Fehler in den Status, Lauf bleibt „grün“
        print(f"{argv[0]}: Fehler {common.short_error(exc)}")
        common.record_status(argv[0], started, False, f"Fehler: {common.short_error(exc)}")
        return 0
    for note in (data or {}).get("hinweise", []) if isinstance(data, dict) else []:
        print("Hinweis:", note)
    print(json.dumps({k: v for k, v in (data or {}).items() if not isinstance(v, (list, dict))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    code = main(sys.argv[1:])
    sys.stdout.flush()
    os._exit(code)                                        # hängende Zeitlimit-Threads dürfen den Lauf nicht aufhalten
