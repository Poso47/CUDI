#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sicheres Aufräum-Skript für CUDI-Workspace.
- Verschiebt nur offensichtliche Temp-/Log-/Cache-Dateien in ein datiertes Archiv.
- Nichts wird endgültig gelöscht (reversibel).

Gruppen (erste Iteration, risikoarm):
- __pycache__/ Verzeichnisse
- logs/ Verzeichnis und log-Dateien
- downloads/ und generated_code/ (temporär)
- Reports/Status-JSONs mit bekannten Mustern

Nutzung:
  python cleanup_workspace.py          # Dry-Run (zeigt nur an)
  python cleanup_workspace.py --apply  # Verschiebt in Archiv
    python cleanup_workspace.py --aggressive             # Dry-Run: Alles außer Kern-Dateien archivieren
    python cleanup_workspace.py --aggressive --apply     # Aggressiv anwenden (whitelist-basiert)
"""
import sys
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / f"CLEANUP_ARCHIVE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Kandidaten (risikoarm)
DIRS = [
    "__pycache__",
    "logs",
    "downloads",
    "generated_code",
]

FILES = [
    "log.txt",
    "cudi_webagent.log",
    "cudi_live_test_report.json",
    "system_analysis_report.json",
    "SYSTEM_STATUS_REPORT.json",
]

GLOB_FILES = [
    "**/__pycache__",  # rekursiv Caches
    "cudi_production_demo_report_*.json",
]

IGNORE_PARTS = {'.venv', '.git', 'CUDI_BACKUPS', 'backups', 'CLEANUP_ARCHIVE'}
IGNORE_PREFIXES = ('CLEANUP_ARCHIVE_',)

# Whitelist für aggressiven Modus: Dateien/Ordner, die definitiv bleiben sollen
KEEP_FILES = {
    'cudi_supreme_gui.py',
    'cudi_brain.py',
    'simple_plugin_manager_enhanced.py',
    'simple_plugin_manager.py',
    'cudi_plugin_manager_dialog.py',
    'cudi_unified_cloud_system.py',
    'cudi_interactive_help_system.py',
    'cleanup_workspace.py',
    'requirements.txt',
    'README.md',
    'README_CUDI_SUPREME.md',
    'launch_cudi_supreme.py',
    'LAUNCH_CUDI_SUPREME_GUI.py',
    'CUDI_SUPREME.bat',
}

KEEP_DIRS = {
    'plugins',
    'config',
}

def collect_paths():
    items = []
    for d in DIRS:
        p = ROOT / d
        if p.exists():
            items.append(p)
    for f in FILES:
        p = ROOT / f
        if p.exists():
            items.append(p)
    for pattern in GLOB_FILES:
        for p in ROOT.glob(pattern):
            if p.exists():
                items.append(p)
    # Duplikate entfernen, Kinder nach Eltern sortieren
    unique = []
    seen = set()
    for p in items:
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    # Pfade filtern, die in ignorierten Bereichen liegen
    def is_ignored(path: Path) -> bool:
        try:
            resolved_parts = path.resolve().parts
        except Exception:
            resolved_parts = path.parts
        for part in resolved_parts:
            if part in IGNORE_PARTS:
                return True
            if any(part.startswith(prefix) for prefix in IGNORE_PREFIXES):
                return True
        return False

    unique = [p for p in unique if not is_ignored(p)]
    unique.sort(key=lambda p: str(p.relative_to(ROOT)))
    return unique

def collect_aggressive_paths():
    """Sammelt alle Elemente außer Whitelist (Kern) und ignorierten Bereichen."""
    items = []
    for p in ROOT.iterdir():
        name = p.name
        if name in IGNORE_PARTS:
            continue
        if any(name.startswith(prefix) for prefix in IGNORE_PREFIXES):
            continue
        if p.is_dir() and name in KEEP_DIRS:
            continue
        if p.is_file() and name in KEEP_FILES:
            continue
        items.append(p)
    return items

def move_to_archive(paths, apply=False):
    if not apply:
        print("[Dry-Run] Folgende Elemente würden archiviert werden:")
        for p in paths:
            print(" -", p.relative_to(ROOT))
        return
    ARCHIVE.mkdir(exist_ok=True)
    for p in paths:
        rel = p.relative_to(ROOT)
        dest = ARCHIVE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(p), str(dest))
            print(f"Archiviert: {rel} -> {dest.relative_to(ROOT)}")
        except Exception as e:
            print(f"Fehler beim Verschieben {rel}: {e}")

def main():
    apply = "--apply" in sys.argv
    aggressive = "--aggressive" in sys.argv
    paths = collect_aggressive_paths() if aggressive else collect_paths()
    if not paths:
        print("Nichts zu archivieren – Workspace sieht bereits sauber aus.")
        return
    if aggressive and not apply:
        print("[Aggressiver Dry-Run] Folgende Elemente würden (außer Kern) archiviert werden:")
        for p in paths:
            print(" -", p.relative_to(ROOT))
        print("\nHinweis: Führe mit --aggressive --apply aus, um die Archivierung tatsächlich vorzunehmen.")
        return
    move_to_archive(paths, apply=apply)
    if not apply and not aggressive:
        print("\nHinweis: Führe mit --apply aus, um die Archivierung tatsächlich vorzunehmen.")

if __name__ == "__main__":
    main()
