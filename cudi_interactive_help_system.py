#!/usr/bin/env python3
"""
CUDI Interaktives Hilfesystem
Intelligente, kontextbezogene Hilfe und FAQ-System für CUDI
"""

import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading

class CUDIInteractiveHelpSystem:
    """Interaktives Hilfesystem für CUDI"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.cudi_dir = Path(__file__).parent
        self.help_data_file = self.cudi_dir / "data" / "help_system.json"
        self.help_data_file.parent.mkdir(exist_ok=True)
        
        self.help_data = self.load_help_data()
        self.current_context = "general"
        self.search_history = []
        
        self.setup_ui()
        
    def load_help_data(self):
        """Lade Hilfe-Daten"""
        default_help_data = {
            "categories": {
                "getting_started": {
                    "name": "Erste Schritte",
                    "icon": "🚀",
                    "description": "Grundlagen und erste Schritte mit CUDI"
                },
                "features": {
                    "name": "Funktionen",
                    "icon": "⚡",
                    "description": "Alle CUDI-Funktionen im Detail"
                },
                "troubleshooting": {
                    "name": "Problemlösung",
                    "icon": "🔧",
                    "description": "Häufige Probleme und Lösungen"
                },
                "advanced": {
                    "name": "Erweitert",
                    "icon": "🎯",
                    "description": "Fortgeschrittene Funktionen und Konfiguration"
                },
                "programming": {
                    "name": "Programmierung",
                    "icon": "💻",
                    "description": "CUDI für Entwickler und Programmierer"
                }
            },
            "topics": {
                "getting_started": [
                    {
                        "id": "first_start",
                        "title": "CUDI zum ersten Mal starten",
                        "tags": ["start", "anfang", "erstmalig"],
                        "content": """
**So starten Sie CUDI zum ersten Mal:**

1. **Einfachster Weg:** Doppelklick auf `CUDI_WEB_START.bat`
   - Öffnet CUDI im Browser
   - Sehr benutzerfreundlich
   - Keine Kommandozeile erforderlich

2. **Desktop-Version:** Doppelklick auf `CUDI_GUI_START.bat`
   - Native Windows-Anwendung
   - Schnell und responsive

3. **Vollautomatisch:** Doppelklick auf `CUDI_ULTIMATE_INSTANT_START.bat`
   - CUDI arbeitet selbstständig
   - Keine Benutzerinteraktion erforderlich

**Nach dem Start:**
- Warten Sie bis CUDI vollständig geladen ist
- Bei der Web-Version öffnet sich automatisch der Browser
- Bei Problemen: Schauen Sie in die Anleitung "FERTIG_LOSLEGEN.txt"
                        """
                    },
                    {
                        "id": "basic_commands",
                        "title": "Grundlegende Befehle",
                        "tags": ["befehle", "kommandos", "grundlagen"],
                        "content": """
**Grundlegende CUDI-Befehle:**

**Programmierung:**
- "Erstelle mir ein Backup-Tool"
- "Schreibe ein Python-Programm für..."
- "Optimiere meinen Code"
- "Erstelle eine To-Do-App"

**System:**
- "Analysiere mein System"
- "Räume meinen Computer auf"
- "Erstelle ein Backup"
- "Überprüfe die Performance"

**Lernen:**
- "Lerne Python Webentwicklung"
- "Erkläre mir Künstliche Intelligenz"
- "Wie funktioniert Machine Learning?"

**Hilfe:**
- "Hilfe" oder "Help"
- "Was kannst du?"
- "Zeige mir alle Funktionen"

**Tipps:**
- CUDI versteht deutsche und englische Befehle
- Sprechen Sie natürlich - keine speziellen Syntax nötig
- Bei Unklarheiten fragt CUDI nach
                        """
                    },
                    {
                        "id": "interface_overview",
                        "title": "Benutzeroberflächen-Übersicht",
                        "tags": ["interface", "gui", "oberfläche"],
                        "content": """
**CUDI hat 4 verschiedene Benutzeroberflächen:**

**1. Web-Interface (Empfohlen)** 🌐
- Läuft im Browser
- Moderne, intuitive Bedienung
- Chat-Bereich für Kommunikation
- Quick-Buttons für häufige Aufgaben
- Status-Anzeige

**2. Desktop-GUI** 🖥️
- Native Windows-Anwendung
- Schnell und responsive
- Alle Funktionen verfügbar
- Offline nutzbar

**3. Terminal mit Hilfe** 💻
- Für fortgeschrittene Nutzer
- Eingebaute Hilfe-Funktionen
- Sehr schnell
- Scriptfähig

**4. Vollautomatischer Modus** ⚡
- CUDI arbeitet selbstständig
- Keine Benutzerinteraktion
- Ideal für Hintergrund-Aufgaben
- "Fire and Forget"

**Navigation:**
- In allen Interfaces: Einfach Befehle eingeben
- Web/GUI: Buttons für schnelle Aktionen
- Terminal: Tippen Sie "help" für Hilfe
                        """
                    }
                ],
                "features": [
                    {
                        "id": "autonomous_programming",
                        "title": "Autonome Programmierung",
                        "tags": ["programmierung", "autonom", "code"],
                        "content": """
**CUDI kann selbstständig programmieren:**

**Was CUDI erstellen kann:**
- 🐍 **Python-Programme:** Web-Apps, Desktop-Apps, Scripts
- 🌐 **Web-Entwicklung:** HTML, CSS, JavaScript, Flask, Django
- 🖥️ **Desktop-Anwendungen:** Tkinter, PyQt, Electron
- 🛠️ **Utilities:** Backup-Tools, Datei-Organizer, Systemtools
- 🎮 **Spiele:** Einfache Spiele und Lernprogramme

**Beispiel-Befehle:**
- "Erstelle mir einen Passwort-Generator"
- "Baue eine Web-App für To-Do-Listen"
- "Schreibe ein Backup-Tool für meine Dateien"
- "Entwickle ein Snake-Spiel"

**Wie es funktioniert:**
1. Sie beschreiben was Sie möchten
2. CUDI plant die Implementierung
3. CUDI schreibt den Code
4. CUDI testet das Programm
5. Sie erhalten das fertige Programm

**Besonderheiten:**
- Vollständige Programme, nicht nur Code-Snippets
- Automatische Fehlerkorrektur
- Dokumentation inklusive
- Benutzerfreundliche Interfaces
                        """
                    },
                    {
                        "id": "continuous_learning",
                        "title": "Kontinuierliches Lernen",
                        "tags": ["lernen", "ki", "verbesserung"],
                        "content": """
**CUDI lernt kontinuierlich und verbessert sich:**

**Was CUDI lernt:**
- 🧠 **Neue Programmiersprachen und Frameworks**
- 🔧 **Bessere Problemlösungsstrategien**
- 📊 **Optimierungstechniken**
- 🎯 **Ihre Präferenzen und Arbeitsweise**

**Lernquellen:**
- Ihre Projekte und Feedback
- Internet-Recherche
- Code-Analyse und -Optimierung
- Selbst-Evaluation

**Sichtbare Verbesserungen:**
- Bessere Code-Qualität über Zeit
- Schnellere Problemlösung
- Passendere Vorschläge
- Erweiterte Funktionalitäten

**Lern-Kontrolle:**
- Lernen kann aktiviert/deaktiviert werden
- Verschiedene Lern-Modi verfügbar
- Transparent: Sie sehen was CUDI lernt
- Privatsphäre: Sensible Daten bleiben lokal

**Beispiele:**
- Nach mehreren Python-Projekten: Bessere Python-Skills
- Nach Web-Entwicklung: Verbesserte HTML/CSS/JS
- Nach Ihrem Feedback: Angepasster Kommunikationsstil
                        """
                    },
                    {
                        "id": "system_optimization",
                        "title": "System-Optimierung",
                        "tags": ["optimierung", "system", "performance"],
                        "content": """
**CUDI kann Ihr System analysieren und optimieren:**

**System-Analyse:**
- 🔍 **Performance-Monitoring**
- 📊 **Ressourcen-Überwachung**
- 🗂️ **Datei-System-Analyse**
- 🔒 **Sicherheits-Check**

**Optimierungen:**
- 🧹 **Aufräumen:** Temporäre Dateien, Duplikate
- ⚡ **Performance:** Startup-Programme, Services
- 📦 **Speicher:** Disk-Cleanup, Archivierung
- 🔧 **Registry:** Windows-Registry-Optimierung

**Automatische Optimierung:**
- Regelmäßige Hintergrund-Scans
- Intelligente Vorschläge
- Sichere Optimierungen ohne Risiko
- Backup vor jeder Änderung

**Beispiel-Befehle:**
- "Analysiere mein System"
- "Optimiere die Performance"
- "Räume meinen Computer auf"
- "Erstelle ein System-Backup"

**Sicherheit:**
- Alle Änderungen werden protokolliert
- Rückgängig-Funktion verfügbar
- Nur sichere Optimierungen
- Benutzer-Bestätigung bei kritischen Änderungen
                        """
                    }
                ],
                "troubleshooting": [
                    {
                        "id": "startup_problems",
                        "title": "CUDI startet nicht",
                        "tags": ["start", "fehler", "problem"],
                        "content": """
**CUDI startet nicht? Hier sind die Lösungen:**

**Schritt 1: Python-Installation prüfen**
```
python --version
```
- Sollte Python 3.8 oder neuer anzeigen
- Falls nicht: Python von python.org installieren

**Schritt 2: Richtige .bat-Datei verwenden**
- ✅ **Empfohlen:** `CUDI_WEB_START.bat`
- ✅ **Alternative:** `CUDI_GUI_START.bat`
- ✅ **Notfall:** `CUDI_ULTIMATE_INSTANT_START.bat`

**Schritt 3: Fehlermeldungen lesen**
- Schwarzes Fenster öffnet sich kurz? → Fehlermeldung notieren
- "Python not found"? → Python installieren
- "Module not found"? → Abhängigkeiten installieren

**Schritt 4: Automatische Reparatur**
```
python cudi_auto_self_diagnosis.py
```
- Führt automatische System-Diagnose durch
- Repariert häufige Probleme automatisch

**Schritt 5: Manuelle Problemlösung**
- Alle Dateien im selben Ordner?
- Windows-Benutzer: PowerShell als Administrator
- Antivirus-Software temporär deaktivieren
- Windows Defender Echtzeitschutz prüfen

**Letzte Rettung:**
- Komplettes CUDI-Verzeichnis neu entpacken
- Python neu installieren
- System-Neustart
                        """
                    },
                    {
                        "id": "performance_issues",
                        "title": "CUDI läuft langsam",
                        "tags": ["langsam", "performance", "geschwindigkeit"],
                        "content": """
**CUDI läuft langsam? So beschleunigen Sie es:**

**Häufige Ursachen:**
- 🐌 **Zu wenig RAM:** < 4GB verfügbar
- 🔥 **Hohe CPU-Last:** Andere Programme belasten System
- 💾 **Festplatte voll:** < 1GB freier Speicher
- 🌐 **Langsame Internet-Verbindung**

**Sofort-Lösungen:**

**1. Andere Programme schließen**
- Browser-Tabs reduzieren
- Unnötige Programme beenden
- Task-Manager öffnen (Strg+Shift+Esc)

**2. CUDI-Modus ändern**
- AI-Einstellungen → Performance → "Schnell"
- Parallele Verarbeitung aktivieren
- Cache aktivieren

**3. System-Optimierung**
```
CUDI: "Optimiere mein System"
```

**4. CUDI-Diagnose**
```
python cudi_auto_self_diagnosis.py
```

**Langfristige Verbesserungen:**
- Mehr RAM installieren (empfohlen: 8GB+)
- SSD statt HDD verwenden
- Regelmäßige System-Wartung
- Windows-Updates installieren

**Performance-Überwachung:**
- Task-Manager: Ressourcen-Nutzung prüfen
- CUDI Status: Zeigt interne Performance
- Diagnosis-Reports: Detaillierte Analyse
                        """
                    },
                    {
                        "id": "connection_errors",
                        "title": "Verbindungsfehler",
                        "tags": ["verbindung", "internet", "netzwerk"],
                        "content": """
**Verbindungsprobleme lösen:**

**Web-Interface lädt nicht:**

**1. Port-Konflikte prüfen**
- Standard-Port: 8000
- Falls belegt: CUDI startet automatisch anderen Port
- Browser: http://localhost:8000 oder http://localhost:8001

**2. Firewall-Einstellungen**
- Windows Firewall: Python erlauben
- Antivirus: CUDI als sicher markieren
- Router: Lokale Verbindungen überprüfen

**3. Browser-Probleme**
- Cache leeren (Strg+F5)
- Andere Browser testen
- Inkognito-Modus verwenden
- Browser-Extensions deaktivieren

**Internet-Zugriff funktioniert nicht:**

**1. Proxy-Einstellungen**
- Systemeinstellungen → Netzwerk → Proxy
- Falls Proxy: CUDI-Konfiguration anpassen

**2. DNS-Probleme**
- DNS-Server ändern (8.8.8.8, 1.1.1.1)
- DNS-Cache leeren: `ipconfig /flushdns`

**3. Netzwerk-Diagnose**
```
ping google.com
nslookup google.com
```

**CUDI Offline-Modus:**
- Die meisten Funktionen arbeiten offline
- Nur Web-Recherche benötigt Internet
- Lokale Programmierung funktioniert immer
                        """
                    }
                ],
                "advanced": [
                    {
                        "id": "plugin_system",
                        "title": "Plugin-System",
                        "tags": ["plugins", "erweiterungen", "addons"],
                        "content": """
**CUDI Plugin-System nutzen:**

**Plugin-Manager öffnen:**
- GUI: Menü → Extras → Plugin Manager
- Web: Einstellungen → Plugins
- Terminal: `plugins` Befehl

**Verfügbare Plugins:**
- 📧 **Email Assistant:** E-Mail-Automatisierung
- 📅 **Calendar Manager:** Terminverwaltung
- 📂 **File Organizer:** Intelligente Datei-Organisation
- 🌐 **Web Scraper:** Datenextraktion
- 💻 **Code Analyzer:** Code-Verbesserungen

**Plugin installieren:**
1. Plugin Manager öffnen
2. "Verfügbar" Tab
3. Plugin auswählen
4. "Installieren" klicken

**Eigene Plugins entwickeln:**
1. Plugin Manager → "Entwicklung"
2. Template erstellen
3. Python-Code schreiben
4. Plugin testen und aktivieren

**Plugin-Struktur:**
```python
class MeinPlugin:
    def __init__(self):
        self.name = "Mein Plugin"
        self.version = "1.0.0"
    
    def activate(self):
        # Plugin-Aktivierung
        pass
    
    def execute(self, command):
        # Plugin-Hauptfunktion
        pass
```

**Plugin-API:**
- CUDI-Integration über Standardschnittstellen
- Event-System für Kommunikation
- Konfiguration über JSON-Dateien
- Automatische Dokumentation
                        """
                    },
                    {
                        "id": "ai_configuration",
                        "title": "AI-Konfiguration",
                        "tags": ["ai", "einstellungen", "konfiguration"],
                        "content": """
**AI-Einstellungen anpassen:**

**AI-Einstellungen öffnen:**
- GUI: Menü → Einstellungen → AI-Einstellungen
- Web: Einstellungen-Rad → AI-Konfiguration

**Wichtige Einstellungen:**

**1. AI-Modus**
- **Basis:** Schnell, grundlegende Funktionen
- **Intelligent:** Ausgewogen, empfohlen
- **Experte:** Gründlich, langsamer

**2. Antwort-Stil**
- **Professionell:** Formell, sachlich
- **Freundlich:** Persönlich, hilfreich
- **Casual:** Locker, umgangssprachlich

**3. Lern-Verhalten**
- **Kontinuierliches Lernen:** Ein/Aus
- **Lernrate:** 0.1 (konservativ) - 1.0 (aggressiv)
- **Auto-Skill-Entwicklung:** Neue Fähigkeiten lernen

**4. Performance**
- **Antwort-Geschwindigkeit:** Schnell/Ausgewogen/Gründlich
- **Parallele Verarbeitung:** Für Mehrkern-CPUs
- **Cache:** Wiederholte Anfragen beschleunigen

**5. Sicherheit**
- **Sicherer Modus:** Verhindert riskante Aktionen
- **Berechtigungen:** Vor Aktionen nachfragen
- **Backup:** Automatische Sicherungen

**Erweiterte Parameter:**
- **Temperature:** Kreativität (0.0-2.0)
- **Max Tokens:** Antwortlänge
- **Context Window:** Gedächtnisgröße
                        """
                    }
                ],
                "programming": [
                    {
                        "id": "code_generation",
                        "title": "Code-Generierung",
                        "tags": ["code", "programmierung", "generierung"],
                        "content": """
**CUDI für Code-Generierung nutzen:**

**Unterstützte Sprachen:**
- 🐍 **Python:** Web, Desktop, Data Science, AI
- 🌐 **JavaScript:** Frontend, Backend (Node.js)
- 🎨 **HTML/CSS:** Webseiten, UI-Design
- ⚙️ **Batch/PowerShell:** Automatisierung
- 📊 **SQL:** Datenbank-Queries

**Code-Anfragen stellen:**

**Konkret beschreiben:**
❌ "Schreibe Code"
✅ "Erstelle ein Python-Programm das CSV-Dateien einliest und Diagramme erstellt"

**Mit Beispielen:**
"Erstelle eine To-Do-App mit folgenden Funktionen:
- Aufgaben hinzufügen/löschen
- Als erledigt markieren
- In Datei speichern"

**Best Practices angeben:**
"Schreibe sauberen Python-Code mit:
- Docstrings für Funktionen
- Error-Handling
- Type-Hints
- PEP 8 Standard"

**Code-Qualität:**
- CUDI schreibt produktionsreifen Code
- Automatische Tests inklusive
- Dokumentation und Kommentare
- Moderne Best Practices

**Code-Review:**
- CUDI erklärt den generierten Code
- Verbesserungsvorschläge möglich
- Iterative Entwicklung
- Performance-Optimierung

**Projekt-Struktur:**
CUDI erstellt vollständige Projekte:
```
mein_projekt/
├── main.py
├── requirements.txt
├── README.md
├── tests/
└── docs/
```
                        """
                    }
                ]
            },
            "quick_help": {
                "shortcuts": [
                    {"key": "F1", "action": "Hilfe öffnen"},
                    {"key": "Ctrl+H", "action": "Schnellhilfe"},
                    {"key": "Ctrl+/", "action": "Befehlsreferenz"},
                    {"key": "Esc", "action": "Aktion abbrechen"}
                ],
                "common_commands": [
                    "Hilfe", "Help", "Was kannst du?", "Zeige Funktionen",
                    "Erstelle Programm", "Optimiere System", "Lerne neues Thema"
                ]
            },
            "troubleshooting_wizard": {
                "steps": [
                    {
                        "question": "Was für ein Problem haben Sie?",
                        "options": ["CUDI startet nicht", "Läuft langsam", "Fehler beim Ausführen", "Anderes Problem"]
                    }
                ]
            }
        }
        
        if self.help_data_file.exists():
            try:
                with open(self.help_data_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    # Merge mit Defaults
                    return {**default_help_data, **saved_data}
            except Exception as e:
                print(f"Fehler beim Laden der Hilfe-Daten: {e}")
                
        return default_help_data
        
    def save_help_data(self):
        """Speichere Hilfe-Daten"""
        try:
            with open(self.help_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.help_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Fehler beim Speichern der Hilfe-Daten: {e}")
            
    def setup_ui(self):
        """Erstelle Hilfe-UI"""
        self.window = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        self.window.title("CUDI Hilfe & Support")
        self.window.geometry("1000x700")
        self.window.configure(bg='#1e1e1e')
        
        # Style konfigurieren
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#1e1e1e')
        style.configure('TLabel', background='#1e1e1e', foreground='white')
        style.configure('TButton', background='#0078d4', foreground='white')
        
        # Hauptframe
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header mit Suche
        self.setup_header(main_frame)
        
        # Hauptinhalt
        self.setup_main_content(main_frame)
        
        # Status Bar
        self.status_bar = ttk.Label(main_frame, text="CUDI Hilfe-System bereit",
                                   relief='sunken')
        self.status_bar.pack(fill='x', side='bottom', pady=(10, 0))
        
    def setup_header(self, parent):
        """Setup Header mit Suche"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', pady=(0, 10))
        
        # Titel
        title_label = ttk.Label(header_frame, text="🆘 CUDI Hilfe & Support", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(side='left')
        
        # Suche
        search_frame = ttk.Frame(header_frame)
        search_frame.pack(side='right')
        
        ttk.Label(search_frame, text="🔍").pack(side='left', padx=(0, 5))
        
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side='left', padx=(0, 5))
        self.search_entry.bind('<KeyRelease>', self.on_search)
        self.search_entry.bind('<Return>', self.perform_search)
        
        ttk.Button(search_frame, text="Suchen", 
                  command=self.perform_search).pack(side='left')
        
    def setup_main_content(self, parent):
        """Setup Hauptinhalt"""
        # Paned Window für Layout
        paned_window = ttk.PanedWindow(parent, orient='horizontal')
        paned_window.pack(fill='both', expand=True)
        
        # Linke Seite: Navigation
        self.setup_navigation(paned_window)
        
        # Rechte Seite: Inhalt
        self.setup_content_area(paned_window)
        
    def setup_navigation(self, parent):
        """Setup Navigation"""
        nav_frame = ttk.Frame(parent)
        parent.add(nav_frame, weight=1)
        
        # Navigation Header
        nav_header = ttk.Label(nav_frame, text="📚 Kategorien", 
                              font=('Arial', 12, 'bold'))
        nav_header.pack(anchor='w', padx=10, pady=10)
        
        # Kategorien-Tree
        self.nav_tree = ttk.Treeview(nav_frame, show='tree')
        self.nav_tree.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # Kategorien hinzufügen
        categories = self.help_data.get('categories', {})
        for cat_id, cat_info in categories.items():
            cat_node = self.nav_tree.insert('', 'end', 
                                           text=f"{cat_info['icon']} {cat_info['name']}",
                                           values=[cat_id])
            
            # Topics in Kategorie
            topics = self.help_data.get('topics', {}).get(cat_id, [])
            for topic in topics:
                self.nav_tree.insert(cat_node, 'end',
                                    text=f"  📄 {topic['title']}",
                                    values=[cat_id, topic['id']])
        
        # Navigation Events
        self.nav_tree.bind('<<TreeviewSelect>>', self.on_nav_select)
        
        # Quick Actions
        quick_frame = ttk.LabelFrame(nav_frame, text="Schnellhilfe")
        quick_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        ttk.Button(quick_frame, text="🚀 Erste Schritte",
                  command=lambda: self.show_topic('getting_started', 'first_start')).pack(fill='x', padx=5, pady=2)
        ttk.Button(quick_frame, text="🔧 Problemlösung",
                  command=self.start_troubleshooting_wizard).pack(fill='x', padx=5, pady=2)
        ttk.Button(quick_frame, text="💻 Befehls-Referenz",
                  command=self.show_command_reference).pack(fill='x', padx=5, pady=2)
        ttk.Button(quick_frame, text="❓ FAQ",
                  command=self.show_faq).pack(fill='x', padx=5, pady=2)
        
    def setup_content_area(self, parent):
        """Setup Inhaltsbereich"""
        content_frame = ttk.Frame(parent)
        parent.add(content_frame, weight=3)
        
        # Content Header
        self.content_header = ttk.Label(content_frame, text="Willkommen bei CUDI Hilfe!", 
                                       font=('Arial', 14, 'bold'))
        self.content_header.pack(anchor='w', padx=10, pady=10)
        
        # Content Text Area
        self.content_text = scrolledtext.ScrolledText(
            content_frame, 
            wrap='word',
            bg='#2d2d30',
            fg='white',
            insertbackground='white',
            font=('Consolas', 10)
        )
        self.content_text.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # Default Content
        self.show_welcome_screen()
        
        # Content Footer
        footer_frame = ttk.Frame(content_frame)
        footer_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        ttk.Button(footer_frame, text="📤 Feedback senden",
                  command=self.send_feedback).pack(side='left')
        ttk.Button(footer_frame, text="📋 Als PDF exportieren",
                  command=self.export_help).pack(side='left', padx=(10, 0))
        ttk.Button(footer_frame, text="🔄 Aktualisieren",
                  command=self.refresh_help).pack(side='right')
        
    def show_welcome_screen(self):
        """Zeige Willkommens-Bildschirm"""
        welcome_text = """
🎉 Willkommen beim CUDI Hilfe-System!

Hier finden Sie alles was Sie über CUDI wissen müssen:

📚 KATEGORIEN:
🚀 Erste Schritte - Grundlagen und erste Schritte
⚡ Funktionen - Alle CUDI-Funktionen im Detail  
🔧 Problemlösung - Häufige Probleme und Lösungen
🎯 Erweitert - Fortgeschrittene Konfiguration
💻 Programmierung - CUDI für Entwickler

🔍 SUCHE:
Verwenden Sie das Suchfeld oben rechts um schnell Antworten zu finden.

⚡ SCHNELLHILFE:
• F1 - Diese Hilfe öffnen
• Ctrl+H - Kontext-sensitive Hilfe
• "Hilfe" in CUDI eingeben

🆘 SOFORTHILFE:

Häufigste Fragen:
• CUDI startet nicht → Problemlösung → "CUDI startet nicht"
• Langsame Performance → Problemlösung → "CUDI läuft langsam"  
• Erste Schritte → Erste Schritte → "CUDI zum ersten Mal starten"

📞 SUPPORT:
Bei weiteren Fragen nutzen Sie das Feedback-System oder die CUDI-Community.

Viel Erfolg mit CUDI! 🤖✨
        """
        
        self.content_text.delete('1.0', tk.END)
        self.content_text.insert('1.0', welcome_text)
        
    def on_nav_select(self, event):
        """Navigation ausgewählt"""
        selection = self.nav_tree.selection()
        if not selection:
            return
            
        values = self.nav_tree.item(selection[0])['values']
        if len(values) == 2:  # Topic ausgewählt
            category, topic_id = values
            self.show_topic(category, topic_id)
        elif len(values) == 1:  # Kategorie ausgewählt
            category = values[0]
            self.show_category(category)
            
    def show_topic(self, category, topic_id):
        """Zeige spezifisches Topic"""
        topics = self.help_data.get('topics', {}).get(category, [])
        topic = next((t for t in topics if t['id'] == topic_id), None)
        
        if topic:
            self.content_header.config(text=f"📄 {topic['title']}")
            self.content_text.delete('1.0', tk.END)
            self.content_text.insert('1.0', topic['content'])
            
            # Tags anzeigen
            if 'tags' in topic:
                tags_text = f"\n\n🏷️ Tags: {', '.join(topic['tags'])}"
                self.content_text.insert(tk.END, tags_text)
                
        self.update_status(f"Topic angezeigt: {topic['title'] if topic else topic_id}")
        
    def show_category(self, category):
        """Zeige Kategorie-Übersicht"""
        cat_info = self.help_data.get('categories', {}).get(category, {})
        topics = self.help_data.get('topics', {}).get(category, [])
        
        self.content_header.config(text=f"{cat_info.get('icon', '📁')} {cat_info.get('name', category)}")
        
        content = f"{cat_info.get('description', '')}\n\n"
        content += f"📋 TOPICS IN DIESER KATEGORIE:\n\n"
        
        for i, topic in enumerate(topics, 1):
            content += f"{i}. 📄 {topic['title']}\n"
            if 'tags' in topic:
                content += f"   🏷️ {', '.join(topic['tags'][:3])}\n"
            content += "\n"
            
        self.content_text.delete('1.0', tk.END)
        self.content_text.insert('1.0', content)
        
        self.update_status(f"Kategorie angezeigt: {cat_info.get('name', category)}")
        
    def on_search(self, event):
        """Suche bei Eingabe"""
        search_term = self.search_var.get().strip()
        if len(search_term) >= 3:
            self.perform_search()
            
    def perform_search(self, event=None):
        """Führe Suche durch"""
        search_term = self.search_var.get().strip().lower()
        if not search_term:
            return
            
        # Suche in allen Topics
        results = []
        
        for category, topics in self.help_data.get('topics', {}).items():
            for topic in topics:
                # Suche in Titel, Tags und Inhalt
                searchable_text = f"{topic['title']} {' '.join(topic.get('tags', []))} {topic['content']}".lower()
                
                if search_term in searchable_text:
                    # Relevanz-Score basierend auf Position und Häufigkeit
                    score = 0
                    if search_term in topic['title'].lower():
                        score += 10
                    if any(search_term in tag.lower() for tag in topic.get('tags', [])):
                        score += 5
                    score += searchable_text.count(search_term)
                    
                    results.append({
                        'category': category,
                        'topic': topic,
                        'score': score
                    })
        
        # Sortiere nach Relevanz
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Zeige Suchergebnisse
        self.show_search_results(search_term, results)
        
        # Zu Suchhistorie hinzufügen
        if search_term not in self.search_history:
            self.search_history.append(search_term)
            if len(self.search_history) > 10:
                self.search_history.pop(0)
                
    def show_search_results(self, search_term, results):
        """Zeige Suchergebnisse"""
        self.content_header.config(text=f"🔍 Suchergebnisse für '{search_term}'")
        
        if not results:
            content = f"Keine Ergebnisse für '{search_term}' gefunden.\n\n"
            content += "💡 Versuchen Sie:\n"
            content += "• Andere Suchbegriffe verwenden\n"
            content += "• Rechtschreibung prüfen\n"
            content += "• Allgemeinere Begriffe verwenden\n"
            content += "• Die Kategorien durchstöbern\n"
        else:
            content = f"🎯 {len(results)} Ergebnisse gefunden:\n\n"
            
            for i, result in enumerate(results[:10], 1):  # Top 10 Ergebnisse
                topic = result['topic']
                category = result['category']
                cat_info = self.help_data.get('categories', {}).get(category, {})
                
                content += f"{i}. 📄 {topic['title']}\n"
                content += f"   📂 {cat_info.get('name', category)}\n"
                if 'tags' in topic:
                    content += f"   🏷️ {', '.join(topic['tags'][:3])}\n"
                content += f"   🎯 Relevanz: {result['score']}\n\n"
                
        self.content_text.delete('1.0', tk.END)
        self.content_text.insert('1.0', content)
        
        self.update_status(f"Suche durchgeführt: {len(results)} Ergebnisse für '{search_term}'")
        
    def start_troubleshooting_wizard(self):
        """Starte Problemlösungs-Assistent"""
        self.content_header.config(text="🔧 Problemlösungs-Assistent")
        
        content = """
🔧 PROBLEMLÖSUNGS-ASSISTENT

Bitte wählen Sie das Problem aus, das Sie haben:

1. 🚫 CUDI startet nicht
   • Python-Fehler
   • Datei nicht gefunden
   • Berechtigungsprobleme

2. 🐌 CUDI läuft langsam
   • Hohe CPU-/Memory-Nutzung
   • Lange Antwortzeiten
   • System hängt

3. 🌐 Verbindungsprobleme
   • Web-Interface lädt nicht
   • Internet-Zugriff funktioniert nicht
   • Port-Konflikte

4. 💻 Programmierfehler
   • Code wird nicht generiert
   • Fehlermeldungen beim Ausführen
   • Unerwartete Ergebnisse

5. ⚙️ Konfigurationsprobleme
   • Einstellungen werden nicht gespeichert
   • Plugins funktionieren nicht
   • Berechtigungsfehler

6. 🆘 Anderes Problem
   • Unbekannter Fehler
   • Frage zur Bedienung
   • Feature-Request

🎯 AUTOMATISCHE DIAGNOSE:
Für eine vollständige Systemdiagnose führen Sie aus:
```
python cudi_auto_self_diagnosis.py
```

💡 TIPP: Die meisten Probleme löst die automatische Diagnose!
        """
        
        self.content_text.delete('1.0', tk.END)
        self.content_text.insert('1.0', content)
        
        self.update_status("Problemlösungs-Assistent gestartet")
        
    def show_command_reference(self):
        """Zeige Befehls-Referenz"""
        self.content_header.config(text="💻 Befehls-Referenz")
        
        content = """
💻 CUDI BEFEHLS-REFERENZ

🚀 ERSTE SCHRITTE:
• "Hilfe" / "Help" - Diese Hilfe anzeigen
• "Was kannst du?" - CUDI-Funktionen anzeigen
• "Zeige mir Beispiele" - Beispiel-Befehle

📝 PROGRAMMIERUNG:
• "Erstelle mir ein [Programmtyp]" - Program generieren
• "Schreibe Python-Code für [Aufgabe]" - Spezifischer Code
• "Optimiere meinen Code" - Code-Verbesserung
• "Erkläre mir [Konzept]" - Programmier-Hilfe

🔧 SYSTEM:
• "Analysiere mein System" - System-Analyse
• "Optimiere Performance" - System-Optimierung
• "Erstelle Backup" - Datensicherung
• "Räume auf" - System-Cleanup

📚 LERNEN:
• "Lerne [Thema]" - Neues Thema lernen
• "Erkläre [Konzept]" - Konzept erklären
• "Recherchiere [Thema]" - Internet-Recherche
• "Zeige Fortschritt" - Lernstatus anzeigen

⚙️ EINSTELLUNGEN:
• "Öffne Einstellungen" - Konfiguration
• "Ändere [Einstellung]" - Spezifische Einstellung
• "Zeige Status" - System-Status
• "Aktiviere [Feature]" - Feature einschalten

🔍 DIAGNOSE:
• "Diagnose" - System-Check
• "Teste Verbindung" - Netzwerk-Test
• "Prüfe Updates" - Update-Check
• "Zeige Logs" - Log-Dateien anzeigen

💡 TIPPS:
• CUDI versteht natürliche Sprache
• Seien Sie so spezifisch wie möglich
• Bei Unklarheiten fragt CUDI nach
• Verwenden Sie Beispiele für bessere Ergebnisse
        """
        
        self.content_text.delete('1.0', tk.END)
        self.content_text.insert('1.0', content)
        
        self.update_status("Befehls-Referenz angezeigt")
        
    def show_faq(self):
        """Zeige FAQ"""
        self.content_header.config(text="❓ Häufige Fragen (FAQ)")
        
        content = """
❓ HÄUFIGE FRAGEN (FAQ)

🔥 TOP-FRAGEN:

Q: Was ist CUDI?
A: CUDI ist ein autonomer KI-Assistent, der programmieren, lernen und Ihr System optimieren kann.

Q: Welche Programmiersprachen kann CUDI?
A: Python, JavaScript, HTML/CSS, SQL, Batch/PowerShell und mehr.

Q: Ist CUDI kostenlos?
A: Ja, CUDI ist komplett kostenlos und Open Source.

Q: Brauche ich Internet?
A: Nein, die meisten Funktionen arbeiten offline. Nur für Recherche wird Internet benötigt.

Q: Wie sicher ist CUDI?
A: Sehr sicher - CUDI läuft lokal, fragt vor Änderungen nach und erstellt Backups.

🚀 START & INSTALLATION:

Q: Welche Systemanforderungen hat CUDI?
A: Windows 10+, Python 3.8+, 4GB RAM (empfohlen: 8GB), 2GB freier Speicher.

Q: Wie installiere ich CUDI?
A: Einfach entpacken und eine .bat-Datei doppelklicken. Keine Installation nötig!

Q: CUDI startet nicht - was tun?
A: 1) Python installieren, 2) Alle Dateien im selben Ordner, 3) Als Administrator ausführen.

⚡ BEDIENUNG:

Q: Wie spreche ich mit CUDI?
A: Ganz natürlich auf Deutsch oder Englisch. Beispiel: "Erstelle mir ein Backup-Tool"

Q: Welche Interface soll ich verwenden?
A: Für Anfänger: Web-Interface. Für Profis: Desktop-GUI. Für Automatisierung: Terminal.

Q: Kann CUDI meine Dateien löschen?
A: Nur wenn Sie es explizit möchten. CUDI fragt immer nach und erstellt Backups.

💻 PROGRAMMIERUNG:

Q: Wie gut ist CUDIs Code?
A: Produktionsreif mit Tests, Dokumentation und modernen Best Practices.

Q: Kann CUDI komplexe Programme erstellen?
A: Ja! Von einfachen Scripts bis zu kompletten Web-Anwendungen.

Q: Lernt CUDI aus meinen Projekten?
A: Ja, CUDI wird mit jedem Projekt besser und lernt Ihre Präferenzen.

🔧 PROBLEME:

Q: CUDI läuft langsam - warum?
A: Meist zu wenig RAM oder andere Programme belasten das System.

Q: Kann ich CUDI erweitern?
A: Ja! Mit dem Plugin-System können Sie eigene Funktionen hinzufügen.

Q: Wo finde ich Logs bei Problemen?
A: Im /logs/ Ordner. Automatische Diagnose: python cudi_auto_self_diagnosis.py

📞 SUPPORT:

Q: Wo bekomme ich Hilfe?
A: Diese Hilfe, Feedback-System, oder die CUDI-Community.

Q: Kann ich Features vorschlagen?
A: Ja! Nutzen Sie das Feedback-System oder entwickeln Sie Plugins.

Q: Gibt es Updates?
A: CUDI aktualisiert sich automatisch und lernt kontinuierlich dazu.
        """
        
        self.content_text.delete('1.0', tk.END)
        self.content_text.insert('1.0', content)
        
        self.update_status("FAQ angezeigt")
        
    def send_feedback(self):
        """Feedback senden"""
        feedback_window = tk.Toplevel(self.window)
        feedback_window.title("Feedback senden")
        feedback_window.geometry("500x400")
        feedback_window.configure(bg='#1e1e1e')
        
        # Feedback-Form
        frame = ttk.Frame(feedback_window)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        ttk.Label(frame, text="📤 Feedback an CUDI-Team", 
                 font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        ttk.Label(frame, text="Typ:").pack(anchor='w')
        feedback_type = ttk.Combobox(frame, values=["Bug-Report", "Feature-Request", "Verbesserung", "Lob", "Anderes"])
        feedback_type.pack(fill='x', pady=(0, 10))
        
        ttk.Label(frame, text="Nachricht:").pack(anchor='w')
        feedback_text = scrolledtext.ScrolledText(frame, height=10, wrap='word')
        feedback_text.pack(fill='both', expand=True, pady=(0, 10))
        
        ttk.Button(frame, text="📤 Senden", 
                  command=lambda: self.submit_feedback(feedback_type.get(), feedback_text.get('1.0', tk.END))).pack()
        
    def submit_feedback(self, feedback_type, message):
        """Feedback absenden"""
        # Feedback in Datei speichern
        feedback_file = self.cudi_dir / "data" / "feedback.json"
        feedback_file.parent.mkdir(exist_ok=True)
        
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": feedback_type,
            "message": message.strip(),
            "help_context": self.current_context
        }
        
        try:
            if feedback_file.exists():
                with open(feedback_file, 'r', encoding='utf-8') as f:
                    feedback_data = json.load(f)
            else:
                feedback_data = []
                
            feedback_data.append(feedback_entry)
            
            with open(feedback_file, 'w', encoding='utf-8') as f:
                json.dump(feedback_data, f, indent=2, ensure_ascii=False)
                
            messagebox.showinfo("Feedback", "Vielen Dank für Ihr Feedback!")
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Feedback konnte nicht gespeichert werden: {e}")
            
    def export_help(self):
        """Hilfe als PDF exportieren"""
        messagebox.showinfo("Export", "PDF-Export wird in einer zukünftigen Version verfügbar sein.")
        
    def refresh_help(self):
        """Hilfe-Daten aktualisieren"""
        self.help_data = self.load_help_data()
        self.update_status("Hilfe-Daten aktualisiert")
        
    def update_status(self, message):
        """Status-Bar aktualisieren"""
        self.status_bar.config(text=f"{datetime.now().strftime('%H:%M:%S')} - {message}")
        
    def show(self):
        """Zeige Hilfe-Dialog"""
        self.window.mainloop()

def main():
    """Hauptfunktion"""
    app = CUDIInteractiveHelpSystem()
    app.show()

if __name__ == "__main__":
    main()