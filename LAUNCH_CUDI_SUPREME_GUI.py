#!/usr/bin/env python3
"""
🚀 CUDI_SUPREME Launcher - Startet die ECHTE moderne GUI
Garantiert die richtige PySide6 GUI mit intelligenter Denkstruktur
"""

import sys
import os
from pathlib import Path

# Setze den korrekten Pfad
cudi_root = Path(__file__).parent
desktop_gui_path = cudi_root / "desktop_gui"
sys.path.insert(0, str(cudi_root))
sys.path.insert(0, str(desktop_gui_path))

def start_cudi_supreme():
    """Startet CUDI_SUPREME mit der modernen GUI"""
    print("🚀 CUDI_SUPREME - Moderne GUI wird gestartet...")
    print("🧠 Mit intelligenter Denkstruktur")
    print("🎨 Mit modernem PySide6 Design")
    print("=" * 60)
    
    try:
        # Wechsle ins GUI-Verzeichnis
        os.chdir(str(desktop_gui_path))
        
        # Importiere und starte die moderne GUI
        from PySide6.QtWidgets import QApplication
        import main_window
        
        # Erstelle QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        
        print("✅ PySide6 erfolgreich geladen")
        print("✅ CUDI Desktop GUI wird gestartet...")
        
        # Erstelle und zeige Hauptfenster
        window = main_window.CUDIMainWindow()
        window.show()
        
        print("🎉 CUDI_SUPREME GUI ist gestartet!")
        print("💬 Intelligente Denkstruktur aktiv")
        print("🔒 WebAgent-Features verfügbar")
        print("🎨 Modernes Design geladen")
        print("=" * 60)
        print("📋 Features verfügbar:")
        print("   🧠 Intelligenter Chat mit Denkstruktur")
        print("   🎯 Dashboard mit Echtzeit-Übersicht")
        print("   🔒 WebAgent für sichere Automation")
        print("   📊 Analytics und Leistungsmetriken")
        print("   🎨 Modernes Material Design")
        print("   📱 Responsive Layout")
        
        # Starte Event-Loop
        return app.exec()
        
    except ImportError as e:
        print(f"❌ PySide6 nicht verfügbar: {e}")
        print("🔧 Installieren Sie PySide6:")
        print("   pip install PySide6")
        return False
        
    except Exception as e:
        print(f"❌ Fehler beim Starten: {e}")
        print("🔧 Überprüfen Sie die Installation")
        return False

if __name__ == "__main__":
    try:
        success = start_cudi_supreme()
        if not success:
            print("\n🔧 Problemlösung:")
            print("1. pip install PySide6")
            print("2. Überprüfen Sie alle CUDI-Module")
            print("3. Starten Sie aus dem korrekten Verzeichnis")
            input("\nDrücken Sie Enter zum Beenden...")
    except KeyboardInterrupt:
        print("\n👋 CUDI_SUPREME beendet")
    except Exception as e:
        print(f"\n💥 Unerwarteter Fehler: {e}")
        input("Drücken Sie Enter zum Beenden...")
