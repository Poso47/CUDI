#!/usr/bin/env python3
"""
CUDI_SUPREME Launcher
Startet die ultimate AI mit allen Funktionen
"""

import sys
import os
import subprocess
from pathlib import Path

# CUDI Directory hinzufügen
cudi_dir = Path(__file__).parent
sys.path.insert(0, str(cudi_dir))

def install_requirements():
    """Installiert fehlende Requirements"""
    requirements = [
        "PySide6",
        "torch",
        "transformers", 
        "sentence-transformers",
        "pyttsx3",
        "speechrecognition",
        "pyaudio",
        "requests",
        "beautifulsoup4",
        "selenium",
        "psutil",
        "cryptography"
    ]
    
    print("🔧 Überprüfe Requirements...")
    missing = []
    
    for req in requirements:
        try:
            __import__(req.replace("-", "_"))
            print(f"✅ {req}")
        except ImportError:
            missing.append(req)
            print(f"❌ {req}")
    
    if missing:
        print(f"\n📦 Installiere fehlende Packages: {', '.join(missing)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            print("✅ Alle Requirements installiert!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Installation fehlgeschlagen: {e}")
            return False
    
    return True

def get_llm():
    """Returns LLM Integration instance"""
    try:
        from llm_integration import LLMIntegration
        return LLMIntegration()
    except ImportError:
        return None

def get_voice_engine():
    """Returns Voice Engine instance"""
    try:
        from advanced_voice_engine import AdvancedVoiceEngine
        return AdvancedVoiceEngine()
    except ImportError:
        return None

def get_plugin_manager():
    """Returns Plugin Manager instance"""
    try:
        from plugin_manager import PluginManager
        return PluginManager()
    except ImportError:
        return None

def launch_cudi_supreme():
    """Startet CUDI_SUPREME"""
    print("🚀 Starte CUDI_SUPREME...")
    
    try:
        # GUI starten
        from cudi_supreme_gui import CUDISupremeMainWindow
        from PySide6.QtWidgets import QApplication
        
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        # Dark Theme
        app.setStyleSheet("""
            QApplication {
                background-color: #0d1117;
                color: #ffffff;
            }
        """)
        
        window = CUDISupremeMainWindow()
        window.show()
        
        print("✅ CUDI_SUPREME gestartet!")
        return app.exec()
        
    except Exception as e:
        print(f"❌ Fehler beim Starten: {e}")
        print("\n🔧 Versuche Fallback...")
        
        # Fallback zu desktop_gui
        try:
            from desktop_gui.main_window import CUDIMainWindow
            from PySide6.QtWidgets import QApplication
            
            app = QApplication(sys.argv)
            app.setStyle("Fusion")
            
            window = CUDIMainWindow()
            window.show()
            
            print("✅ Fallback GUI gestartet!")
            return app.exec()
            
        except Exception as e2:
            print(f"❌ Auch Fallback fehlgeschlagen: {e2}")
            return 1

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 CUDI_SUPREME LAUNCHER")
    print("Ultimate AI Assistant")
    print("=" * 50)
    
    # Requirements prüfen
    if not install_requirements():
        print("❌ Requirements konnten nicht installiert werden!")
        sys.exit(1)
    
    # CUDI_SUPREME starten
    exit_code = launch_cudi_supreme()
    
    print("\n👋 CUDI_SUPREME beendet.")
    sys.exit(exit_code)
