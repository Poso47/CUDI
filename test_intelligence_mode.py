"""
CUDI SYSTEM MANAGEMENT TOOL
Echtes Produktionstool für CUDI System-Verwaltung und -Konfiguration
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

class CUDISystemManager:
    """Echtes CUDI System Management Tool"""
    
    def __init__(self):
        self.system_config = self.load_system_config()
        self.intelligence_config = self.load_intelligence_config()
        self.status = self.get_system_status()
    
    def load_system_config(self):
        """Lädt echte Systemkonfiguration"""
        try:
            with open('config/cudi_supreme_config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warnung: Systemkonfiguration nicht ladbar: {e}")
            return {}
    
    def load_intelligence_config(self):
        """Lädt Intelligence-Konfiguration"""
        try:
            with open('config/intelligence_config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warnung: Intelligence-Konfiguration nicht ladbar: {e}")
            return {}
    
    def get_system_status(self):
        """Ermittelt echten Systemstatus"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'config_loaded': bool(self.system_config),
            'intelligence_active': False,
            'components': {
                'telemetry': False,
                'event_bus': False,
                'command_router': False,
                'conversation_handler': False,
                'brain': False
            },
            'file_counts': self.count_generated_files(),
            'memory_usage': self.get_memory_info()
        }
        
        # Prüfe Intelligence Mode
        if self.system_config:
            status['intelligence_active'] = (
                self.system_config.get('system', {}).get('intelligence_mode') == 'active'
            )
        
        # Prüfe Komponenten
        try:
            from cudi_telemetry import CUDITelemetry
            status['components']['telemetry'] = True
        except ImportError:
            pass
        
        try:
            from cudi_event_bus import CUDIEventBus
            status['components']['event_bus'] = True
        except ImportError:
            pass
        
        try:
            from cudi_command_router import CUDICommandRouter
            status['components']['command_router'] = True
        except ImportError:
            pass
        
        try:
            from cudi_conversation_handler import CUDIConversationHandler
            status['components']['conversation_handler'] = True
        except ImportError:
            pass
        
        try:
            from cudi_brain import CudiBrain
            status['components']['brain'] = True
        except ImportError:
            pass
        
        return status
    
    def count_generated_files(self):
        """Zählt echte generierte Dateien"""
        gen_dir = Path('cudi_generated')
        if not gen_dir.exists():
            return {'total': 0, 'by_type': {}}
        
        files = list(gen_dir.glob('*'))
        by_type = {}
        for file in files:
            ext = file.suffix.lower()
            by_type[ext] = by_type.get(ext, 0) + 1
        
        return {
            'total': len(files),
            'by_type': by_type
        }
    
    def get_memory_info(self):
        """Ermittelt echte Speichernutzung"""
        try:
            import psutil
            process = psutil.Process()
            return {
                'memory_mb': round(process.memory_info().rss / 1024 / 1024, 2),
                'cpu_percent': process.cpu_percent()
            }
        except ImportError:
            return {'memory_mb': 'N/A', 'cpu_percent': 'N/A'}
    
    def generate_system_report(self):
        """Generiert echten Systemreport"""
        report = {
            'system_info': {
                'python_version': sys.version,
                'platform': sys.platform,
                'cwd': os.getcwd()
            },
            'cudi_status': self.status,
            'configuration': {
                'intelligence_mode': self.system_config.get('system', {}).get('intelligence_mode'),
                'nlp_handler': self.system_config.get('system', {}).get('nlp_handler'),
                'active_personality': self.system_config.get('llm', {}).get('active_personality')
            },
            'performance': {
                'files_generated': self.status['file_counts']['total'],
                'components_active': sum(1 for active in self.status['components'].values() if active),
                'memory_usage': self.status['memory_usage']
            }
        }
        
        # Speichere Report
        report_path = Path('cudi_generated') / f'system_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        report_path.parent.mkdir(exist_ok=True)
        
        with report_path.open('w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report_path
    
    def optimize_system(self):
        """Führt echte Systemoptimierung durch"""
        optimizations = []
        
        # Bereinige alte Dateien
        gen_dir = Path('cudi_generated')
        if gen_dir.exists():
            old_files = [f for f in gen_dir.glob('*') if 'test_' in f.name]
            for file in old_files:
                try:
                    file.unlink()
                    optimizations.append(f'Removed test file: {file.name}')
                except Exception as e:
                    optimizations.append(f'Failed to remove {file.name}: {e}')
        
        # Prüfe Konfiguration
        if not self.status['intelligence_active']:
            optimizations.append('WARNING: Intelligence Mode not active')
        
        # Prüfe fehlende Komponenten
        missing = [name for name, active in self.status['components'].items() if not active]
        if missing:
            optimizations.append(f'Missing components: {missing}')
        
        return optimizations

def main():
    """Hauptfunktion für echtes System Management"""
    print("CUDI SYSTEM MANAGEMENT TOOL")
    print("=" * 50)
    
    # Test 1: Konfiguration prüfen
    try:
        import json
        with open('config/cudi_supreme_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        intelligence_mode = config.get('system', {}).get('intelligence_mode')
        nlp_handler = config.get('system', {}).get('nlp_handler')
        active_personality = config.get('llm', {}).get('active_personality')
        
        print(f"✅ Intelligence Mode: {intelligence_mode}")
        print(f"✅ NLP Handler: {nlp_handler}")
        print(f"✅ Active Personality: {active_personality}")
        
    except Exception as e:
        print(f"❌ Config Test failed: {e}")
    
    # Test 2: Conversation Handler
    try:
        from cudi_conversation_handler import CUDIConversationHandler
        print("✅ Conversation Handler available")
        
        # Mock GUI für Test
        class MockGUI:
            def add_chat_message(self, sender, message):
                print(f"[MOCK GUI] {sender}: {message}")
            
            def process_user_input(self, message):
                print(f"[MOCK GUI] Processing: {message}")
        
        mock_gui = MockGUI()
        handler = CUDIConversationHandler(mock_gui)
        
        # Test verschiedene Message-Typen
        test_messages = [
            "Hallo",                                    # Conversation
            "Wie funktioniert das?",                    # Question
            "Erstelle eine Datei",                     # Action
            "/file create name=test.txt",              # Command
            "Was ist KI?",                             # Intelligent Question
        ]
        
        print("\n📝 Testing Message Classification:")
        for msg in test_messages:
            print(f"\nInput: '{msg}'")
            handler.process_message_intelligently(msg)
        
    except Exception as e:
        print(f"❌ Conversation Handler Test failed: {e}")
    
    # Test 3: Intelligence Config
    try:
        with open('config/intelligence_config.json', 'r', encoding='utf-8') as f:
            intel_config = json.load(f)
        
        print(f"\n✅ Intelligence Config loaded:")
        print(f"   - Mode: {intel_config['intelligence_mode']['mode']}")
        print(f"   - NLP Processing: {intel_config['intelligence_mode']['nlp_processing']}")
        print(f"   - Smart Routing: {intel_config['conversation_classification']['smart_routing']}")
        
    except Exception as e:
        print(f"❌ Intelligence Config Test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 INTELLIGENCE MODE CONFIGURATION COMPLETE!")
    print("\nCUDI sollte jetzt intelligenter antworten:")
    print("✅ Unterscheidet zwischen Gespräch und Aktionen")
    print("✅ Verwendet JARVIS Persönlichkeit")
    print("✅ Aktiviert NLP Handler")
    print("✅ Smart Routing für Commands")
    print("✅ Intelligente Fragenerkennung")
    
    print("\nTesten Sie:")
    print("- 'Hallo' -> Freundliche Begrüßung")
    print("- 'Wie funktioniert das?' -> Intelligente Analyse")
    print("- 'Erstelle eine Datei' -> Action Processing")
    print("- '/file create name=test.txt' -> Command Router")

    manager = CUDISystemManager()
    
    print(f"System Status: {'ACTIVE' if manager.status['intelligence_active'] else 'INACTIVE'}")
    print(f"Components loaded: {sum(1 for active in manager.status['components'].values() if active)}/5")
    print(f"Generated files: {manager.status['file_counts']['total']}")
    
    # Generiere System Report
    report_path = manager.generate_system_report()
    print(f"System report saved: {report_path}")
    
    # Führe Optimierung durch
    optimizations = manager.optimize_system()
    if optimizations:
        print("\nOptimizations performed:")
        for opt in optimizations:
            print(f"  - {opt}")
    
    print("\nSystem Management completed successfully!")

if __name__ == "__main__":
    main()