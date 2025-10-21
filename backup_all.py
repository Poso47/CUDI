#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erstellt ein vollständiges ZIP-Backup des CUDI-Ordners (ohne .venv/.git).
Ziel: CUDI_BACKUPS/CUDI_FULL_BACKUP_YYYYMMDD_HHMMSS.zip
"""
from pathlib import Path
from datetime import datetime
import zipfile

ROOT = Path(__file__).resolve().parent
BACKUPS = ROOT / "CUDI_BACKUPS"
BACKUPS.mkdir(exist_ok=True)

EXCLUDE_DIRS = {'.git', '.venv', '__pycache__'}

def should_exclude(path: Path) -> bool:
    parts = set(path.parts)
    return any(part in EXCLUDE_DIRS for part in parts)

def create_backup():
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_path = BACKUPS / f"CUDI_FULL_BACKUP_{ts}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in ROOT.rglob('*'):
            if p.is_dir():
                continue
            if should_exclude(p):
                continue
            try:
                zf.write(p, p.relative_to(ROOT))
            except Exception:
                # weiter machen
                pass
    return zip_path

if __name__ == '__main__':
    zip_path = create_backup()
    print(f"Backup erstellt: {zip_path}")