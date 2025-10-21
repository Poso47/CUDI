# CUDI - Digitaler Assistent

CUDI (Computer Understanding & Digital Intelligence) ist ein vollwertiger digitaler Assistent, der als Ihr digitaler Zwilling fungiert und weitreichende Systemzugriffe sowie Automatisierungsfähigkeiten bietet.

## 🎯 Projektbeschreibung

CUDI ist darauf ausgelegt, als vollständiger digitaler Assistent zu fungieren, der:
- **Vollständigen Systemzugriff** hat (mit Admin-Rechten)
- **Internet-Recherchen** durchführt und Datenbanken aufbaut
- **Projekte automatisch erstellt** und verwaltet
- **Hintergrundaufgaben** ausführt und plant
- **System-Wartung** automatisiert
- Als **digitaler Zwilling** des Benutzers agiert

## 🚀 Installation & Start

### Schnelle Installation
```bash
# 1. Alle Dateien in einem Ordner zusammenfassen
# 2. Setup ausführen:
python setup.py

# 3. CUDI starten (verschiedene Optionen):

# Neue Advanced GUI (EMPFOHLEN):
start_cudi_gui.bat
# oder
python start_advanced_gui.py

# Klassische GUI:
start_cudi.bat
# oder
python startup.py
```

### Manuelle Installation
```bash
# Abhängigkeiten installieren
pip install -r requirements.txt

# CUDI mit Advanced GUI starten
python advanced_gui.py
```

## 🎮 Benutzer-Interfaces

### 🌟 Advanced GUI (NEU!)
**Moderne Tab-basierte Oberfläche mit:**
- **💬 Chat-Tab**: Direkte Kommunikation + Emotions-Panel
- **🧠 Wissen-Tab**: Wissensdatenbank mit Suche & Management
- **🖥️ System-Tab**: System-Monitoring & Datei-Management  
- **📁 Projekte-Tab**: Projekt-Erstellung & -Verwaltung
- **⚡ Aufgaben-Tab**: Hintergrundaufgaben & Automation
- **📜 Logs-Tab**: System-Protokolle & Export-Funktionen

**Start**: `python start_advanced_gui.py` oder `start_cudi_gui.bat`

### 🎮 Klassische GUI
**Einfache Chat-Oberfläche mit Buttons:**
**Erste Reihe:**
- **Sprechen**: Spracheingabe (mockup)
- **Denken**: Simuliert Denkprozess
- **Wissen**: Zeigt gespeicherte Informationen
- **Plugins**: Plugin-Verwaltung
- **Logs**: System-Logs anzeigen
- **Emotion**: Aktuelle "Stimmung" der KI

**Zweite Reihe:**
- **System**: System-Informationen abrufen
- **Projekte**: Projekt-Management
- **Aufgaben**: Hintergrundaufgaben verwalten
- **Internet**: Web-Recherche starten
- **Reinigen**: System-Wartung durchführen

### Chat-Befehle
```
# System-Befehle
"erstelle datei beispiel.txt"
"lösche datei unwichtig.log"
"führe aus dir"
"system info"

# Internet-Recherche
"suche im internet Python Tutorials"
"lade herunter https://example.com/file.zip"
"recherchiere Künstliche Intelligenz"

# Projekt-Management
"erstelle projekt MeinWebsite"
"liste projekte"
"lösche projekt AltesZeug"

# Automatisierung
"führe im hintergrund aus python script.py"
"plane aufgabe täglich system backup"
"system reinigen"
```

## 🔧 Technische Details

### Architektur
```
CUDI/
├── main.py              # Haupt-GUI und Entry Point
├── brain.py             # KI-Logik und Befehlsverarbeitung
├── system_access.py     # Vollständiger Systemzugriff
├── internet_research.py # Web-Scraping und Recherche
├── project_manager.py   # Automatische Projekterstellung
├── task_automation.py   # Hintergrundaufgaben und Planung
├── startup.py           # Startup-Script mit Fehlerbehandlung
├── setup.py             # Automatische Installation
└── requirements.txt     # Python-Abhängigkeiten
```

### Abhängigkeiten
- **psutil**: System-Monitoring
- **requests**: HTTP-Anfragen
- **beautifulsoup4**: Web-Scraping
- **schedule**: Aufgaben-Planung
- **sqlite3**: Lokale Datenbank
- **tkinter**: GUI-Framework

### Sicherheitshinweise
⚠️ **WICHTIG**: CUDI erfordert erweiterte Systemrechte und kann:
- Dateien systemweit erstellen/löschen
- Programme ausführen
- Registry-Änderungen vornehmen
- Netzwerkzugriffe durchführen

## 🎯 Anwendungsszenarien

### Als persönlicher Assistent
```python
# Tägliche Aufgaben automatisieren
"plane aufgabe täglich backup erstellen"
"system reinigen"
"erstelle projekt Monatsreport"
```

### Als Entwicklungshelfer
```python
# Projekte schnell aufsetzen
"erstelle projekt WebApp"
"suche im internet React Best Practices"
"führe im hintergrund aus npm install"
```

### Als System-Administrator
```python
# System überwachen und warten
"system info"
"führe aus sfc /scannow"
"lösche datei C:/temp/cache.tmp"
```

## 🔮 Erweiterungsmöglichkeiten

Das Projekt ist modular aufgebaut und kann erweitert werden mit:
- **Spracherkennung**: Echte Voice-to-Text Integration
- **API-Integration**: OpenAI, Google APIs
- **Machine Learning**: Lokale AI-Modelle
- **Netzwerk-Management**: Remote-System-Zugriff
- **Cloud-Integration**: Dropbox, Google Drive
- **Überwachung**: System-Alerts und Benachrichtigungen

## 📄 Lizenz

Dieses Projekt ist für Bildungszwecke und persönliche Nutzung gedacht. Bei kommerziellem Einsatz beachten Sie bitte die Lizenzen der verwendeten Bibliotheken.

## ⚠️ Haftungsausschluss

CUDI ist ein experimentelles Projekt. Die Nutzung erfolgt auf eigene Verantwortung. Erstellen Sie vor dem Einsatz Backups wichtiger Daten.

---

**Entwickelt als vollwertiger digitaler Assistent mit dem Ziel, als digitaler Zwilling zu fungieren.**
