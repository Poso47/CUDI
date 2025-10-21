#!/usr/bin/env python3
"""
CUDI PERFECT LAUNCHER - Harmonized System Entry Point
Launches CUDI with perfect component synchronization
"""

import sys
import os
from pathlib import Path

def main():
    """Perfect CUDI launch sequence"""
    print("[LAUNCH] CUDI PERFECT LAUNCHER")
    print("=" * 40)
    
    # Ensure we're in the right directory
    cudi_path = Path(__file__).parent
    os.chdir(cudi_path)
    
    # Add to Python path
    sys.path.insert(0, str(cudi_path))
    
    try:
        # Launch harmonized CUDI
        print("[START] Starting CUDI Supreme Harmonized...")
        
        # Try harmonized version first
        try:
            from cudi_supreme_gui import CUDISupremeMainWindow
            print("[OK] Using CUDI Supreme GUI")
        except ImportError:
            # Fallback to harmonized version if available
            try:
                from cudi_supreme_harmonized import CUDISupremeMainWindow
                print("[OK] Using CUDI Harmonized Version")
            except ImportError:
                raise ImportError("No CUDI main window class found")
        
        # Launch application
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        
        app = QApplication(sys.argv)
        app.setApplicationName("CUDI Supreme")
        
        window = CUDISupremeMainWindow()
        window.show()

        print("[DONE] CUDI launched successfully!")
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"[ERROR] Launch failed: {e}")
        print("[RECOVERY] Attempting emergency launch...")
        
        # Emergency fallback
        try:
            import subprocess
            subprocess.run([sys.executable, "cudi_supreme_gui.py"])
        except Exception as emergency_error:
            print(f"[ERROR] Emergency launch also failed: {emergency_error}")
            print("[SUPPORT] Please check system requirements and try again.")

if __name__ == "__main__":
    main()
