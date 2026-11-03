# CUDI – persönlicher KI-Kollege mit Digitalem Gehirn

CUDI ist ein lokaler Desktop-Assistent (Python, PySide6): ein Kollege im Stil von J.A.R.V.I.S., der
natürlich mit dir spricht, sich erinnert, deine Projekte und Dokumente kennt und Aufgaben über echte
Werkzeuge erledigt – mit Rückfrage vor jeder Veränderung.

## Schnellstart

**Windows:** Doppelklick auf `CUDI_STARTEN.bat` (richtet beim ersten Start alles selbst ein).
**macOS/Linux:** `./cudi_starten.sh` · **VS Code:** F5 → „CUDI starten (Fenster)“

Von Hand:

```
pip install -r requirements-core.txt
python main.py            # Fenster
python main.py --cli      # Chat im Terminal
python main.py --diagnose # Selbstdiagnose
```

Für freie Antworten ein Sprachmodell anschließen: **Ollama** (lokal, kostenlos) oder einen
**Claude**/OpenAI-Schlüssel in `.env` (Vorlage: `.env.example`). Details: [docs/user_guide.md](docs/user_guide.md).

## Was funktioniert

* Chat über einen zentralen Orchestrator mit Werkzeugen, Berechtigungsstufen und ehrlichem Status
* Digitales Gehirn in einer SQLite-Datenbank: Langzeitgedächtnis (Quelle, Status, Widerspruchserkennung),
  Gesprächsverlauf, Projektgedächtnis, Aufgaben, Dokumentwissen mit Fundstellen, Feedback, Verlaufsprotokoll
* Dokumentimport: PDF, DOCX, TXT, Markdown, JSON, CSV
* Sprachmodelle: Ollama, Claude (`claude-opus-5-5`), OpenAI – mit Ausweichreihenfolge
* Selbstdiagnose, tägliche Sicherung, Wiederherstellung, Export
* Aufgeräumtes Hauptfenster: Chat, Gedächtnis, Projekte, Aufgaben, Dokumente, Modelle, Werkzeuge, Diagnose, Einstellungen
* 55 automatische Tests (`python -m pytest tests/`), darunter die Abnahmetests A–K

Noch nicht eingebaut: Sprachsteuerung, Websuche, Code ausführen, E-Mail/Kalender, Kreativstudio.

## Aufbau

```
main.py              Start
cudi/                neuer Kern (core, brain, models, tools, diagnostics, config)
ui/                  Hauptfenster (Standard)
cudi_supreme_gui.py  alte Oberfläche, startbar mit --alt
tests/               automatische Tests
docs/                Status, Architektur, Plan, Entscheidungen, bekannte Fehler, Anleitung
```

Die übrigen `cudi_*.py`-Dateien sind der Altbestand; sie bleiben erhalten, bis ihre Ablösung
freigegeben ist (siehe [docs/implementation_plan.md](docs/implementation_plan.md), Vorschlag V8).

## Dokumentation

* [docs/user_guide.md](docs/user_guide.md) – Bedienung
* [docs/project_status.md](docs/project_status.md) – was fertig und getestet ist
* [docs/architecture.md](docs/architecture.md) – Aufbau und Zuständigkeiten
* [docs/implementation_plan.md](docs/implementation_plan.md) – nächste Schritte und Vorschläge
* [docs/decisions.md](docs/decisions.md) – Architekturentscheidungen
* [docs/known_issues.md](docs/known_issues.md) – bekannte Fehler
