#!/usr/bin/env python3
"""Zentraler Start von CUDI.

    python main.py              Desktop-Oberfläche (PySide6)
    python main.py --cli        Chat im Terminal
    python main.py --diagnose   Selbstdiagnose ausgeben
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="CUDI – persönlicher KI-Kollege")
    parser.add_argument("--cli", action="store_true", help="Chat im Terminal statt Fenster")
    parser.add_argument("--diagnose", action="store_true", help="Selbstdiagnose ausgeben und beenden")
    args = parser.parse_args()

    # Ältere Module arbeiten mit relativen Pfaden – deshalb immer im Projektordner starten
    os.chdir(BASE_DIR)
    sys.path.insert(0, str(BASE_DIR))

    if args.diagnose:
        from cudi.core.application import get_app
        from cudi.diagnostics.health import report
        print(report(get_app()))
        return 0
    if args.cli:
        from cudi.cli import run
        run()
        return 0

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as e:
        print("Die Oberfläche benötigt PySide6 (pip install PySide6).")
        print(f"Fehler: {e}")
        print("Alternativ im Terminal starten: python main.py --cli")
        return 1

    import cudi_supreme_gui

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = cudi_supreme_gui.CUDISupremeMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
