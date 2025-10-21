#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CUDI BRAIN GUI INTEGRATION TEST
==============================
Test der CudiBrain Integration in der GUI
"""

import sys
from pathlib import Path

# GUI Imports
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QLineEdit, QPushButton
from PySide6.QtCore import QTimer, Qt

# CudiBrain Import
from cudi_brain import CudiBrain

class CudiBrainTestWindow(QMainWindow):
    """Einfache Test-GUI für CudiBrain"""
    
    def __init__(self):
        super().__init__()
        self.brain = None
        self.init_ui()
        self.init_brain()
        
    def init_ui(self):
        """Initialisiert einfache UI"""
        self.setWindowTitle("🧠 CUDI Brain Test")
        self.setGeometry(200, 200, 800, 600)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Chat Display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display)
        
        # Input
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Testen Sie CudiBrain...")
        self.input_field.returnPressed.connect(self.send_message)
        layout.addWidget(self.input_field)
        
        # Send Button
        send_btn = QPushButton("📨 Senden")
        send_btn.clicked.connect(self.send_message)
        layout.addWidget(send_btn)
        
        # Dark Theme
        self.setStyleSheet("""
            QMainWindow { background-color: #0d1117; color: #ffffff; }
            QTextEdit { background-color: #161b22; color: #ffffff; border: 1px solid #30363d; }
            QLineEdit { background-color: #21262d; color: #ffffff; border: 1px solid #30363d; padding: 8px; }
            QPushButton { background-color: #238636; color: white; border: none; padding: 8px; }
        """)
        
    def init_brain(self):
        """Initialisiert CudiBrain"""
        try:
            self.brain = CudiBrain()
            self.add_message("🧠 System", "CudiBrain erfolgreich initialisiert!")
            self.add_message("🧠 System", "Alle kognitiven Systeme sind online.")
            self.add_message("🤖 CUDI", "Hallo! Ich bin CUDI mit vollständiger kognitiver Architektur. Wie kann ich Ihnen helfen?")
        except Exception as e:
            self.add_message("❌ System", f"CudiBrain Fehler: {e}")
            
    def add_message(self, sender, message):
        """Fügt Nachricht hinzu"""
        self.chat_display.append(f"<b>{sender}:</b> {message}")
        
    def send_message(self):
        """Sendet Nachricht an CudiBrain"""
        message = self.input_field.text().strip()
        if not message:
            return
            
        self.add_message("👤 Du", message)
        self.input_field.clear()
        
        if self.brain:
            try:
                # CudiBrain verwenden
                context = {"test_mode": True}
                response = self.brain.understand_and_respond(message, context)
                self.add_message("🤖 CUDI", response)
            except Exception as e:
                self.add_message("❌ Error", f"CudiBrain Fehler: {e}")
        else:
            self.add_message("❌ Error", "CudiBrain nicht verfügbar")

def main():
    app = QApplication(sys.argv)
    
    window = CudiBrainTestWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    print("🧠 Starte CudiBrain GUI Test...")
    main()