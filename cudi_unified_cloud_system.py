#!/usr/bin/env python3
"""
CUDI Vereinheitlichtes Cloud-System
Zentrale Cloud-Synchronisation und -Verwaltung für alle CUDI-Dienste
"""

import sys
import os
import json
import hashlib
import threading
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging

class CUDIUnifiedCloudSystem:
    """Vereinheitlichtes Cloud-System für CUDI"""
    
    def __init__(self, config_file=None):
        self.cudi_dir = Path(__file__).parent
        self.config_file = config_file or self.cudi_dir / "config" / "cloud_config.json"
        self.config_file.parent.mkdir(exist_ok=True)
        
        self.cloud_db = self.cudi_dir / "data" / "cloud_sync.db"
        self.cloud_db.parent.mkdir(exist_ok=True)
        
        self.sync_status = {
            "enabled": False,
            "connected": False,
            "last_sync": None,
            "pending_uploads": 0,
            "pending_downloads": 0,
            "provider": None
        }
        
        self.setup_logging()
        self.load_config()
        self.setup_database()
        
        # Sync-Thread
        self.sync_thread = None
        self.sync_running = False
        
    def setup_logging(self):
        """Setup Logging"""
        log_file = self.cudi_dir / "logs" / "cloud_sync.log"
        log_file.parent.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('CUDICloudSync')
        
    def load_config(self):
        """Lade Cloud-Konfiguration"""
        default_config = {
            "providers": {
                "google_drive": {
                    "name": "Google Drive",
                    "enabled": False,
                    "credentials": {},
                    "sync_folders": ["data", "logs", "plugins"],
                    "auto_sync": True,
                    "sync_interval": 300  # 5 Minuten
                },
                "onedrive": {
                    "name": "Microsoft OneDrive",
                    "enabled": False,
                    "credentials": {},
                    "sync_folders": ["data", "logs", "plugins"],
                    "auto_sync": True,
                    "sync_interval": 300
                },
                "dropbox": {
                    "name": "Dropbox",
                    "enabled": False,
                    "credentials": {},
                    "sync_folders": ["data", "logs", "plugins"],
                    "auto_sync": True,
                    "sync_interval": 300
                },
                "local_network": {
                    "name": "Lokales Netzwerk",
                    "enabled": False,
                    "path": "",
                    "sync_folders": ["data", "logs", "plugins"],
                    "auto_sync": True,
                    "sync_interval": 60
                }
            },
            "sync_settings": {
                "conflict_resolution": "ask",  # ask, local_wins, remote_wins, merge
                "bandwidth_limit": 0,  # 0 = unlimited, sonst KB/s
                "only_wifi": False,
                "pause_on_battery": True,
                "encryption": True,
                "compression": True
            },
            "security": {
                "encrypt_data": True,
                "encrypt_logs": False,
                "master_password": "",
                "two_factor": False
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    # Merge mit Defaults
                    self.config = self.merge_configs(default_config, saved_config)
            except Exception as e:
                self.logger.error(f"Fehler beim Laden der Cloud-Config: {e}")
                self.config = default_config
        else:
            self.config = default_config
            
    def merge_configs(self, default, saved):
        """Merge Konfigurationen"""
        result = default.copy()
        for key, value in saved.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.merge_configs(result[key], value)
            else:
                result[key] = value
        return result
        
    def save_config(self):
        """Speichere Cloud-Konfiguration"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Cloud-Config: {e}")
            return False
            
    def setup_database(self):
        """Setup Cloud-Sync-Datenbank"""
        try:
            conn = sqlite3.connect(self.cloud_db)
            cursor = conn.cursor()
            
            # Sync-Status Tabelle
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_status (
                    file_path TEXT PRIMARY KEY,
                    local_hash TEXT,
                    remote_hash TEXT,
                    local_modified TIMESTAMP,
                    remote_modified TIMESTAMP,
                    last_sync TIMESTAMP,
                    sync_status TEXT,
                    provider TEXT,
                    conflict_resolved BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Sync-History Tabelle
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action TEXT,
                    file_path TEXT,
                    provider TEXT,
                    status TEXT,
                    details TEXT
                )
            ''')
            
            # Conflict-Resolution Tabelle
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    local_hash TEXT,
                    remote_hash TEXT,
                    conflict_type TEXT,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolution TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            
            self.logger.info("Cloud-Sync-Datenbank initialisiert")
            
        except Exception as e:
            self.logger.error(f"Fehler beim Setup der Cloud-DB: {e}")
            
    def get_enabled_providers(self):
        """Gib aktivierte Cloud-Provider zurück"""
        enabled = []
        for provider_id, provider_config in self.config.get('providers', {}).items():
            if provider_config.get('enabled', False):
                enabled.append({
                    'id': provider_id,
                    'name': provider_config.get('name', provider_id),
                    'config': provider_config
                })
        return enabled
        
    def enable_provider(self, provider_id, credentials=None):
        """Aktiviere Cloud-Provider"""
        if provider_id not in self.config.get('providers', {}):
            return False, f"Unbekannter Provider: {provider_id}"
            
        try:
            # Provider-spezifische Initialisierung
            if provider_id == "google_drive":
                success, message = self.init_google_drive(credentials)
            elif provider_id == "onedrive":
                success, message = self.init_onedrive(credentials)
            elif provider_id == "dropbox":
                success, message = self.init_dropbox(credentials)
            elif provider_id == "local_network":
                success, message = self.init_local_network(credentials)
            else:
                success, message = False, "Provider nicht implementiert"
                
            if success:
                self.config['providers'][provider_id]['enabled'] = True
                if credentials:
                    self.config['providers'][provider_id]['credentials'] = credentials
                self.save_config()
                
                self.logger.info(f"Provider {provider_id} aktiviert")
                
            return success, message
            
        except Exception as e:
            self.logger.error(f"Fehler beim Aktivieren von {provider_id}: {e}")
            return False, str(e)
            
    def init_google_drive(self, credentials):
        """Initialisiere Google Drive"""
        # Vereinfacht - echte Implementierung würde Google API verwenden
        if not credentials or 'client_id' not in credentials:
            return False, "Google Drive Credentials fehlen"
            
        # Hier würde OAuth-Flow stattfinden
        # Für Demo: Simuliere erfolgreiche Verbindung
        self.logger.info("Google Drive Verbindung simuliert")
        return True, "Google Drive verbunden"
        
    def init_onedrive(self, credentials):
        """Initialisiere OneDrive"""
        if not credentials or 'client_id' not in credentials:
            return False, "OneDrive Credentials fehlen"
            
        self.logger.info("OneDrive Verbindung simuliert")
        return True, "OneDrive verbunden"
        
    def init_dropbox(self, credentials):
        """Initialisiere Dropbox"""
        if not credentials or 'access_token' not in credentials:
            return False, "Dropbox Access Token fehlt"
            
        self.logger.info("Dropbox Verbindung simuliert")
        return True, "Dropbox verbunden"
        
    def init_local_network(self, credentials):
        """Initialisiere lokales Netzwerk"""
        if not credentials or 'path' not in credentials:
            return False, "Netzwerk-Pfad fehlt"
            
        network_path = Path(credentials['path'])
        if not network_path.exists():
            return False, f"Netzwerk-Pfad nicht erreichbar: {network_path}"
            
        self.config['providers']['local_network']['path'] = str(network_path)
        self.logger.info(f"Lokales Netzwerk verbunden: {network_path}")
        return True, "Lokales Netzwerk verbunden"
        
    def start_auto_sync(self):
        """Starte automatische Synchronisation"""
        if self.sync_running:
            return
            
        enabled_providers = self.get_enabled_providers()
        if not enabled_providers:
            self.logger.warning("Keine Cloud-Provider aktiviert")
            return
            
        self.sync_running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        
        self.logger.info("Automatische Synchronisation gestartet")
        
    def stop_auto_sync(self):
        """Stoppe automatische Synchronisation"""
        self.sync_running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
            
        self.logger.info("Automatische Synchronisation gestoppt")
        
    def _sync_loop(self):
        """Haupt-Sync-Schleife"""
        while self.sync_running:
            try:
                enabled_providers = self.get_enabled_providers()
                
                for provider in enabled_providers:
                    if not self.sync_running:
                        break
                        
                    provider_config = provider['config']
                    if provider_config.get('auto_sync', False):
                        self.sync_with_provider(provider['id'])
                        
                # Warte bis zum nächsten Sync-Intervall
                if self.sync_running:
                    min_interval = min(
                        p['config'].get('sync_interval', 300) 
                        for p in enabled_providers
                        if p['config'].get('auto_sync', False)
                    ) if enabled_providers else 300
                    
                    time.sleep(min_interval)
                    
            except Exception as e:
                self.logger.error(f"Fehler in Sync-Loop: {e}")
                time.sleep(60)  # Bei Fehlern: 1 Minute warten
                
    def sync_with_provider(self, provider_id):
        """Synchronisiere mit spezifischem Provider"""
        try:
            provider_config = self.config['providers'].get(provider_id, {})
            if not provider_config.get('enabled', False):
                return False, "Provider nicht aktiviert"
                
            sync_folders = provider_config.get('sync_folders', [])
            
            self.logger.info(f"Starte Sync mit {provider_id}")
            
            for folder_name in sync_folders:
                folder_path = self.cudi_dir / folder_name
                if folder_path.exists():
                    self._sync_folder(folder_path, provider_id)
                    
            self.sync_status['last_sync'] = datetime.now().isoformat()
            self.sync_status['provider'] = provider_id
            
            self.logger.info(f"Sync mit {provider_id} abgeschlossen")
            return True, "Sync erfolgreich"
            
        except Exception as e:
            self.logger.error(f"Fehler beim Sync mit {provider_id}: {e}")
            return False, str(e)
            
    def _sync_folder(self, folder_path, provider_id):
        """Synchronisiere einen Ordner"""
        try:
            for file_path in folder_path.rglob("*"):
                if file_path.is_file() and not self._should_skip_file(file_path):
                    self._sync_file(file_path, provider_id)
                    
        except Exception as e:
            self.logger.error(f"Fehler beim Sync von {folder_path}: {e}")
            
    def _should_skip_file(self, file_path):
        """Prüfe ob Datei übersprungen werden soll"""
        skip_patterns = [
            "*.tmp", "*.temp", "*.lock", "*~", "*.bak",
            "__pycache__", ".git", ".svn", "node_modules"
        ]
        
        file_str = str(file_path)
        for pattern in skip_patterns:
            if pattern.replace("*", "") in file_str:
                return True
                
        # Zu große Dateien überspringen (>100MB)
        try:
            if file_path.stat().st_size > 100 * 1024 * 1024:
                return True
        except:
            pass
            
        return False
        
    def _sync_file(self, file_path, provider_id):
        """Synchronisiere eine einzelne Datei"""
        try:
            rel_path = file_path.relative_to(self.cudi_dir)
            
            # Lokale Datei-Info
            local_hash = self._calculate_file_hash(file_path)
            local_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
            
            # Status aus DB laden
            conn = sqlite3.connect(self.cloud_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT local_hash, remote_hash, local_modified, remote_modified, last_sync
                FROM sync_status WHERE file_path = ? AND provider = ?
            ''', (str(rel_path), provider_id))
            
            result = cursor.fetchone()
            
            if result:
                db_local_hash, db_remote_hash, db_local_mod, db_remote_mod, last_sync = result
                
                # Prüfe ob Upload nötig
                if local_hash != db_local_hash:
                    self._upload_file(file_path, provider_id)
                    
            else:
                # Neue Datei - Upload
                self._upload_file(file_path, provider_id)
                
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Fehler beim Sync von {file_path}: {e}")
            
    def _upload_file(self, file_path, provider_id):
        """Lade Datei in Cloud hoch"""
        try:
            rel_path = file_path.relative_to(self.cudi_dir)
            
            # Provider-spezifischer Upload
            if provider_id == "local_network":
                success = self._upload_to_local_network(file_path, provider_id)
            else:
                # Für andere Provider: Simuliere Upload
                success = True
                self.logger.info(f"Upload simuliert: {rel_path} -> {provider_id}")
                
            if success:
                # Status in DB aktualisieren
                self._update_sync_status(file_path, provider_id, "uploaded")
                
                # History-Eintrag
                self._add_sync_history("upload", str(rel_path), provider_id, "success")
                
        except Exception as e:
            self.logger.error(f"Fehler beim Upload von {file_path}: {e}")
            self._add_sync_history("upload", str(rel_path), provider_id, "error", str(e))
            
    def _upload_to_local_network(self, file_path, provider_id):
        """Upload zu lokalem Netzwerk"""
        try:
            network_path = Path(self.config['providers']['local_network']['path'])
            rel_path = file_path.relative_to(self.cudi_dir)
            target_path = network_path / "CUDI_Sync" / rel_path
            
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            import shutil
            shutil.copy2(file_path, target_path)
            
            self.logger.info(f"Datei kopiert: {rel_path} -> {target_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Fehler beim Netzwerk-Upload: {e}")
            return False
            
    def _calculate_file_hash(self, file_path):
        """Berechne SHA256-Hash einer Datei"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            self.logger.error(f"Fehler beim Hash-Berechnen für {file_path}: {e}")
            return ""
            
    def _update_sync_status(self, file_path, provider_id, action):
        """Aktualisiere Sync-Status in DB"""
        try:
            rel_path = file_path.relative_to(self.cudi_dir)
            local_hash = self._calculate_file_hash(file_path)
            local_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
            
            conn = sqlite3.connect(self.cloud_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO sync_status 
                (file_path, local_hash, remote_hash, local_modified, remote_modified, last_sync, sync_status, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(rel_path), local_hash, local_hash,  # remote_hash = local_hash nach Upload
                local_modified, local_modified,  # remote_modified = local_modified nach Upload
                datetime.now(), action, provider_id
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Fehler beim Update des Sync-Status: {e}")
            
    def _add_sync_history(self, action, file_path, provider_id, status, details=""):
        """Füge Sync-History-Eintrag hinzu"""
        try:
            conn = sqlite3.connect(self.cloud_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO sync_history (action, file_path, provider, status, details)
                VALUES (?, ?, ?, ?, ?)
            ''', (action, file_path, provider_id, status, details))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Fehler beim Hinzufügen der Sync-History: {e}")
            
    def get_sync_status(self):
        """Gib aktuellen Sync-Status zurück"""
        try:
            enabled_providers = self.get_enabled_providers()
            
            # Pending Uploads/Downloads zählen
            conn = sqlite3.connect(self.cloud_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) FROM sync_status 
                WHERE local_hash != remote_hash OR remote_hash IS NULL
            ''')
            pending_uploads = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM sync_conflicts WHERE resolved = FALSE
            ''')
            pending_conflicts = cursor.fetchone()[0]
            
            conn.close()
            
            self.sync_status.update({
                "enabled": len(enabled_providers) > 0,
                "connected": len(enabled_providers) > 0,
                "providers": [p['name'] for p in enabled_providers],
                "pending_uploads": pending_uploads,
                "pending_conflicts": pending_conflicts,
                "auto_sync_running": self.sync_running
            })
            
            return self.sync_status
            
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen des Sync-Status: {e}")
            return self.sync_status
            
    def get_sync_history(self, limit=50):
        """Gib Sync-History zurück"""
        try:
            conn = sqlite3.connect(self.cloud_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT timestamp, action, file_path, provider, status, details
                FROM sync_history 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'timestamp': row[0],
                    'action': row[1],
                    'file_path': row[2],
                    'provider': row[3],
                    'status': row[4],
                    'details': row[5]
                })
                
            conn.close()
            return history
            
        except Exception as e:
            self.logger.error(f"Fehler beim Abrufen der Sync-History: {e}")
            return []
            
    def manual_sync(self, provider_id=None):
        """Führe manuellen Sync durch"""
        try:
            if provider_id:
                return self.sync_with_provider(provider_id)
            else:
                # Sync mit allen aktiven Providern
                enabled_providers = self.get_enabled_providers()
                results = []
                
                for provider in enabled_providers:
                    success, message = self.sync_with_provider(provider['id'])
                    results.append((provider['name'], success, message))
                    
                return results
                
        except Exception as e:
            self.logger.error(f"Fehler beim manuellen Sync: {e}")
            return False, str(e)
            
    def cleanup_old_history(self, days=30):
        """Räume alte Sync-History auf"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            conn = sqlite3.connect(self.cloud_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM sync_history 
                WHERE timestamp < ?
            ''', (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.logger.info(f"{deleted_count} alte Sync-History-Einträge entfernt")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Fehler beim Aufräumen der History: {e}")
            return 0

def main():
    """Hauptfunktion für Tests"""
    cloud_system = CUDIUnifiedCloudSystem()
    
    print("🌤️ CUDI Cloud-System Test")
    print("=" * 40)
    
    # Status anzeigen
    status = cloud_system.get_sync_status()
    print(f"Cloud-Status: {status}")
    
    # Provider aktivieren (Beispiel)
    success, message = cloud_system.enable_provider("local_network", {
        "path": "C:/temp/cudi_sync"
    })
    print(f"Provider aktiviert: {success} - {message}")
    
    # Manueller Sync
    if success:
        print("\nStarte manuellen Sync...")
        results = cloud_system.manual_sync()
        print(f"Sync-Ergebnisse: {results}")

if __name__ == "__main__":
    main()