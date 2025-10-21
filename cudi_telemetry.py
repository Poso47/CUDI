"""
CUDI TELEMETRIE SYSTEM
Zentrale Logging und Monitoring Funktionalität
Entspricht CUDI Maintenance Mode Anforderungen
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading
from collections import defaultdict

class CUDITelemetry:
    """Zentrale Telemetrie für alle CUDI Operationen"""
    
    def __init__(self):
        self.log_dir = Path("cudi_logs")
        self.log_dir.mkdir(exist_ok=True)
        
        self.session_id = f"session_{int(time.time())}"
        self.metrics = defaultdict(int)
        self.events = []
        self.lock = threading.RLock()
        
        # Event-Kategorien
        self.EVENT_CATEGORIES = {
            'ACTION_START': 'System startet Aktion',
            'ACTION_SUCCESS': 'Aktion erfolgreich abgeschlossen', 
            'ACTION_FAIL': 'Aktion fehlgeschlagen',
            'FILE_CREATED': 'Datei erstellt',
            'RESEARCH_START': 'Research gestartet',
            'RESEARCH_COMPLETE': 'Research abgeschlossen',
            'CONTENT_GENERATED': 'Content generiert',
            'LEARNING_EVENT': 'Lernvorgang dokumentiert',
            'SYSTEM_STATUS': 'System Status Update'
        }
        
        self._init_session_log()
    
    def _init_session_log(self):
        """Initialisiert Session-Log"""
        session_log = {
            'session_id': self.session_id,
            'start_time': datetime.now().isoformat(),
            'system': 'CUDI_SUPREME',
            'version': '2.0',
            'events': []
        }
        
        log_file = self.log_dir / f"{self.session_id}.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(session_log, f, indent=2, ensure_ascii=False)
    
    def log(self, event: str, data: Dict[str, Any] = None, context: str = None) -> str:
        """
        Hauptlogfunktion - entspricht cudi_telemetry.log(event,...)
        
        Args:
            event: Event-Typ (ACTION_START, ACTION_SUCCESS, etc.)
            data: Event-Daten
            context: Zusätzlicher Kontext
            
        Returns:
            Event-ID für Referenz
        """
        with self.lock:
            event_id = f"evt_{int(time.time()*1000)}_{len(self.events)}"
            
            log_entry = {
                'event_id': event_id,
                'event_type': event,
                'timestamp': datetime.now().isoformat(),
                'data': data or {},
                'context': context,
                'session_id': self.session_id
            }
            
            # Zu internen Events hinzufügen
            self.events.append(log_entry)
            
            # Metrics aktualisieren
            self.metrics[event] += 1
            self.metrics['total_events'] += 1
            
            # In Haupt-Logfile schreiben
            self._write_to_log(log_entry)
            
            # Console-Output für wichtige Events
            if event in ['ACTION_SUCCESS', 'ACTION_FAIL', 'FILE_CREATED']:
                print(f"[TELEMETRY] {event} - {data.get('description', 'N/A')}")
            
            return event_id
    
    def _write_to_log(self, entry: Dict[str, Any]):
        """Schreibt Entry in Log-Datei"""
        try:
            log_file = self.log_dir / f"{self.session_id}.json"
            
            # Lade existierende Daten
            with open(log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            
            # Füge neues Event hinzu
            log_data['events'].append(entry)
            log_data['last_update'] = datetime.now().isoformat()
            
            # Schreibe zurück
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"⚠️ Telemetry write error: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Liefert aktuelle Metriken"""
        with self.lock:
            return {
                'session_id': self.session_id,
                'total_events': len(self.events),
                'event_counts': dict(self.metrics),
                'uptime': time.time() - int(self.session_id.split('_')[1]),
                'last_activity': self.events[-1]['timestamp'] if self.events else None
            }
    
    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Liefert letzte Events"""
        with self.lock:
            return self.events[-limit:] if self.events else []
    
    def export_session_data(self) -> str:
        """Exportiert komplette Session-Daten"""
        export_file = self.log_dir / f"export_{self.session_id}_{int(time.time())}.json"
        
        export_data = {
            'session_info': {
                'session_id': self.session_id,
                'export_time': datetime.now().isoformat(),
                'total_events': len(self.events)
            },
            'metrics': self.get_metrics(),
            'events': self.events
        }
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return str(export_file)

# GLOBALE TELEMETRIE INSTANZ
_telemetry_instance = None

def get_telemetry() -> CUDITelemetry:
    """Singleton für Telemetrie-System"""
    global _telemetry_instance
    if _telemetry_instance is None:
        _telemetry_instance = CUDITelemetry()
    return _telemetry_instance

def log(event: str, data: Dict[str, Any] = None, context: str = None) -> str:
    """Shortcut für Telemetrie-Logging"""
    return get_telemetry().log(event, data, context)

if __name__ == "__main__":
    # Test des Telemetrie-Systems
    telemetry = CUDITelemetry()
    
    # Test Events
    telemetry.log('ACTION_START', {'action': 'file_creation', 'user': 'test'})
    telemetry.log('FILE_CREATED', {'path': 'test.py', 'size': 1024})
    telemetry.log('ACTION_SUCCESS', {'action': 'file_creation', 'duration_ms': 150})
    
    # Metriken anzeigen
    metrics = telemetry.get_metrics()
    print("📊 Telemetrie-Test:")
    print(f"  Session: {metrics['session_id']}")
    print(f"  Events: {metrics['total_events']}")
    print(f"  Event-Counts: {metrics['event_counts']}")
    
    # Export testen
    export_path = telemetry.export_session_data()
    print(f"[TELEMETRY] Export created: {export_path}")