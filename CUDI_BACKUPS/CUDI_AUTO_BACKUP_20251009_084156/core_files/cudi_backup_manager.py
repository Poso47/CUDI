#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CUDI SYSTEM - VOLLSTÄNDIGES BACKUP UND RESTORE SCRIPT
===================================================
Automatisches Backup aller wichtigen CUDI-Komponenten
"""

import os
import sys
import shutil
import json
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

class CUDIBackupManager:
    """Verwaltet Backups des gesamten CUDI-Systems"""
    
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.backup_dir = self.base_path / "CUDI_BACKUPS"
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def create_full_backup(self):
        """Erstellt vollständiges Backup"""
        print("🔄 Starte vollständiges CUDI Backup...")
        
        # Backup-Verzeichnis erstellen
        backup_path = self.backup_dir / f"CUDI_FULL_BACKUP_{self.timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # 1. Kernkomponenten sichern
        self._backup_core_files(backup_path)
        
        # 2. Datenbanken sichern
        self._backup_databases(backup_path)
        
        # 3. Konfigurationen sichern
        self._backup_configurations(backup_path)
        
        # 4. Backup-Info erstellen
        self._create_backup_info(backup_path)
        
        # 5. ZIP-Archive erstellen
        zip_path = self._create_zip_archive(backup_path)
        
        print(f"✅ Vollständiges Backup erstellt: {zip_path}")
        return zip_path
        
    def _backup_core_files(self, backup_path):
        """Sichert alle Kern-Dateien"""
        core_files = [
            "cudi_brain.py",
            "cudi_supreme_gui.py", 
            "cudi_autonomous_intelligence.py",
            "test_cudi_brain_gui.py",
            "INTEGRATION_ERFOLG_BACKUP.md"
        ]
        
        core_dir = backup_path / "core_files"
        core_dir.mkdir(exist_ok=True)
        
        for file_name in core_files:
            source = self.base_path / file_name
            if source.exists():
                shutil.copy2(source, core_dir / file_name)
                print(f"  ✅ {file_name} gesichert")
            else:
                print(f"  ⚠️ {file_name} nicht gefunden")
                
    def _backup_databases(self, backup_path):
        """Sichert alle SQLite-Datenbanken"""
        db_files = [
            "cudi_memory.db",
            "cudi_emotions.db", 
            "cudi_learning.db",
            "cudi_metacognition.db",
            "cudi_cognitive_memory.db",
            "cudi_autonomous_knowledge.db",
            "cudi_brain_memory.db"
        ]
        
        db_dir = backup_path / "databases" 
        db_dir.mkdir(exist_ok=True)
        
        for db_name in db_files:
            source = self.base_path / db_name
            if source.exists():
                shutil.copy2(source, db_dir / db_name)
                print(f"  ✅ {db_name} gesichert")
                
                # Zusätzlich SQL-Dump erstellen
                self._create_sql_dump(source, db_dir / f"{db_name}.sql")
                
    def _backup_configurations(self, backup_path):
        """Sichert Konfigurationsdateien"""
        config_files = [
            "config.py",
            "BUILD_AI_ENHANCED.bat",
            "CUDI_COMPLETE_SYSTEM_OVERVIEW.md"
        ]
        
        config_dir = backup_path / "configurations"
        config_dir.mkdir(exist_ok=True)
        
        for config_file in config_files:
            source = self.base_path / config_file
            if source.exists():
                shutil.copy2(source, config_dir / config_file)
                print(f"  ✅ {config_file} gesichert")
                
    def _create_sql_dump(self, db_path, dump_path):
        """Erstellt SQL-Dump einer Datenbank"""
        try:
            conn = sqlite3.connect(db_path)
            with open(dump_path, 'w', encoding='utf-8') as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
            conn.close()
        except Exception as e:
            print(f"  ⚠️ SQL-Dump Fehler für {db_path}: {e}")
            
    def _create_backup_info(self, backup_path):
        """Erstellt Backup-Informationen"""
        info = {
            "backup_timestamp": self.timestamp,
            "backup_date": datetime.now().isoformat(),
            "cudi_version": "2.0 - CudiBrain Integration",
            "components": {
                "cudi_brain": "Vollständige kognitive Architektur",
                "gui_integration": "PySide6 GUI mit CudiBrain",
                "autonomous_intelligence": "Proaktive Antwortsysteme",
                "databases": "SQLite Persistierung"
            },
            "features": [
                "Menschenähnliches Verständnis",
                "Emotionale Intelligenz", 
                "Kontinuierliches Lernen",
                "Proaktive Antworten",
                "Persistente Persönlichkeit"
            ],
            "file_count": len(list(backup_path.rglob("*"))),
            "backup_size_mb": sum(f.stat().st_size for f in backup_path.rglob("*") if f.is_file()) / (1024*1024)
        }
        
        with open(backup_path / "backup_info.json", 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
            
    def _create_zip_archive(self, backup_path):
        """Erstellt ZIP-Archive"""
        zip_path = self.backup_dir / f"CUDI_BACKUP_{self.timestamp}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in backup_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(backup_path)
                    zipf.write(file_path, arcname)
                    
        return zip_path
        
    def restore_from_backup(self, backup_zip_path):
        """Stellt System aus Backup wieder her"""
        print(f"🔄 Stelle CUDI aus Backup wieder her: {backup_zip_path}")
        
        restore_dir = self.backup_dir / "RESTORE_TEMP"
        restore_dir.mkdir(exist_ok=True)
        
        # ZIP extrahieren
        with zipfile.ZipFile(backup_zip_path, 'r') as zipf:
            zipf.extractall(restore_dir)
            
        # Dateien wiederherstellen
        self._restore_files(restore_dir)
        
        # Aufräumen
        shutil.rmtree(restore_dir)
        
        print("✅ Wiederherstellung abgeschlossen")
        
    def _restore_files(self, restore_dir):
        """Stellt Dateien wieder her"""
        # Core Files
        core_dir = restore_dir / "core_files"
        if core_dir.exists():
            for file_path in core_dir.glob("*"):
                target = self.base_path / file_path.name
                shutil.copy2(file_path, target)
                print(f"  ✅ {file_path.name} wiederhergestellt")
                
        # Databases
        db_dir = restore_dir / "databases"
        if db_dir.exists():
            for file_path in db_dir.glob("*.db"):
                target = self.base_path / file_path.name
                shutil.copy2(file_path, target)
                print(f"  ✅ {file_path.name} wiederhergestellt")
                
        # Configurations
        config_dir = restore_dir / "configurations"
        if config_dir.exists():
            for file_path in config_dir.glob("*"):
                target = self.base_path / file_path.name
                shutil.copy2(file_path, target)
                print(f"  ✅ {file_path.name} wiederhergestellt")
                
    def list_backups(self):
        """Listet alle verfügbaren Backups"""
        if not self.backup_dir.exists():
            print("❌ Kein Backup-Verzeichnis gefunden")
            return []
            
        backups = list(self.backup_dir.glob("CUDI_BACKUP_*.zip"))
        backups.sort(reverse=True)  # Neueste zuerst
        
        print(f"📦 Verfügbare Backups ({len(backups)}):")
        for i, backup in enumerate(backups):
            size_mb = backup.stat().st_size / (1024*1024)
            print(f"  {i+1}. {backup.name} ({size_mb:.1f} MB)")
            
        return backups
        
    def verify_system_integrity(self):
        """Überprüft System-Integrität"""
        print("🔍 Überprüfe CUDI System-Integrität...")
        
        required_files = [
            "cudi_brain.py",
            "cudi_supreme_gui.py"
        ]
        
        missing_files = []
        for file_name in required_files:
            if not (self.base_path / file_name).exists():
                missing_files.append(file_name)
                
        if missing_files:
            print(f"❌ Fehlende Dateien: {missing_files}")
            return False
        else:
            print("✅ Alle kritischen Dateien vorhanden")
            return True

def main():
    """Hauptfunktion für Backup-Management"""
    print("🧠 CUDI Backup Manager")
    print("=" * 50)
    
    manager = CUDIBackupManager()
    
    while True:
        print("\nOptionen:")
        print("1. 💾 Vollständiges Backup erstellen")
        print("2. 📦 Backups auflisten")
        print("3. 🔄 Aus Backup wiederherstellen")
        print("4. 🔍 System-Integrität prüfen")
        print("5. ❌ Beenden")
        
        choice = input("\nWählen Sie eine Option (1-5): ").strip()
        
        if choice == "1":
            backup_path = manager.create_full_backup()
            print(f"\n✅ Backup erfolgreich erstellt: {backup_path}")
            
        elif choice == "2":
            manager.list_backups()
            
        elif choice == "3":
            backups = manager.list_backups()
            if backups:
                try:
                    idx = int(input("Backup-Nummer zum Wiederherstellen: ")) - 1
                    if 0 <= idx < len(backups):
                        manager.restore_from_backup(backups[idx])
                    else:
                        print("❌ Ungültige Backup-Nummer")
                except ValueError:
                    print("❌ Bitte geben Sie eine Zahl ein")
                    
        elif choice == "4":
            manager.verify_system_integrity()
            
        elif choice == "5":
            print("👋 Backup Manager beendet")
            break
            
        else:
            print("❌ Ungültige Option")

if __name__ == "__main__":
    main()