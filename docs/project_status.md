# Projektstatus CUDI + Digitales Gehirn

Stand: 2026-10-26 · Phase 1 (Bestandsaufnahme) abgeschlossen · Beginn Phase 3 (kritischer Startfehler behoben)

Diese Datei beschreibt den **tatsächlichen** Codezustand. Alle Aussagen zu Tests beziehen sich nur auf
Tests, die wirklich ausgeführt wurden (Abschnitt 6).

---

## 1. Was ist im Repository vorhanden?

| Bereich | Umfang |
|---|---|
| Python-Dateien (Root + `plugins/`) | 29 Dateien, ca. 16 900 Zeilen |
| Hauptanwendung | `cudi_supreme_gui.py` (PySide6/Qt, 5 986 Zeilen) |
| „Gehirn“ | `cudi_brain.py` (1 631 Zeilen, ohne Sprachmodell) |
| Datenbanken | `cudi_brain_memory.db`, `cudi_learning.db` (alle Tabellen **leer**) |
| Backup | `CUDI_BACKUPS/CUDI_AUTO_BACKUP_20251009_084156/` (ältere Kopien + `cudi_autonomous_knowledge.db` mit 40 Wissenseinträgen) |
| Erzeugte Dateien | `cudi_generated/`, `cudi_content/`, `cudi_research/`, `cudi_production_data/` (Vorlagen-/Demo-Ausgaben) |
| Tests | bisher keine echten Tests; neu: `tests/test_event_bus.py` |
| Dokumentation | `README.md` (beschreibt eine **ältere, nicht mehr vorhandene** Architektur), `README_CUDI_SUPREME.md`, diverse Status-Markdowns mit Erfolgsmeldungen, die nicht dem Code entsprechen |

### Nicht vorhanden (obwohl im Master-Prompt oder im Code erwähnt)

* **Keine zweite Codebasis „Digitales Gehirn“.** Das einzige Gehirn-Modul ist `cudi_brain.py`.
  Wenn das Digitale Gehirn als eigenes Projekt existiert, liegt es nicht in diesem Repository.
* Keine der im Master-Prompt genannten Dateien existiert: `main.py`, `brain.py`, `voice.py`,
  `local_llm.py`, `netzwerk_listener.py`, `self_improve.py`, `cudi_master_functions.py`,
  `memory.json`, `settings.json`, `knowledge_base.json`, `feedback_log.json`, `task_log.json`,
  `kollektiv.json`, `schreibstil.json`, `training_data.json`.
* Vom Code importierte, aber fehlende Module: `llm_integration`, `advanced_voice_engine`,
  `plugin_manager`, `advanced_web_intelligence`, `autonomous_thinking`, `cudi_ai_settings_dialog`,
  `cudi_auto_self_diagnosis`, `game_app_learning_system`, `desktop_gui/main_window`,
  `cudi_autonomous_intelligence` (nur im Backup), `cudi_backup_manager` (nur im Backup).
  Die Importe sind meist mit `try/except` abgefangen – die Funktionen fehlen dann still.

---

## 2. Funktionen von CUDI (GUI + Assistent)

Legende: ✅ funktioniert · 🟡 teilweise · ❌ fehlerhaft/vorgetäuscht · ⬜ nicht vorhanden

| Funktion | Status | Befund |
|---|---|---|
| GUI-Start (`python cudi_supreme_gui.py`) | ✅ (seit Fix) | Hing vorher unter Python 3.13 dauerhaft beim Start (Event-Bus). Behoben, siehe `known_issues.md` KI-01. |
| Chat-Fenster, Nachrichtenanzeige | ✅ | funktioniert |
| Natürliche Antworten | ❌ | Antworten sind feste Textbausteine (Zufallsauswahl). Kein Sprachmodell wird im Standardweg genutzt. |
| Sprachmodell-Anbindung (`AdvancedCommunicationEngine`) | 🟡 | Code für OpenAI, Anthropic und Ollama vorhanden, aber: veraltete Modellnamen, kein Gesprächsverlauf, System-Prompt und Nutzernachricht in einer Nachricht vermischt; im Standard-Chatweg wird die Engine praktisch nie erreicht. |
| Intent-Erkennung | ❌ | Schlüsselwort-Treffer per Teilstring („hi“ trifft „nichts“, „ja“ trifft „Jahr“), drei konkurrierende Implementierungen. |
| Aktionen/Werkzeuge | ❌ | „Absolut-Fallback: immer eine Datei erstellen“ – fast jede Nachricht erzeugt eine Markdown-Vorlagendatei in `cudi_content/`. Das ist die Ursache für „Markdown-Liste statt Handlung“. |
| Slash-Befehle (`/file`, `/research`, `/learn`, `/exec`) | ❌ | `cudi_command_router.py` existiert, wird aber nur von einer überschriebenen (toten) Methode aufgerufen. `/exec` erzeugt nur eine Vorlagendatei. |
| Web-Recherche | 🟡 | DuckDuckGo-Instant-Answer-Abfrage vorhanden; bei Fehler wird trotzdem „Ich habe gelernt“ gemeldet. Installiert fehlende Pakete zur Laufzeit per `pip`. |
| Plugins | 🟡 | `plugins/rechnungsassistent.py` ist ein echtes Tkinter-Plugin. Der Plugin-Manager listet sonst 6 fest eingetragene „Plugins“, die keine eigenen Dateien haben. |
| Sprachsteuerung / Sprachausgabe | ⬜ | `get_voice_engine()` gibt `None` zurück; Statusanzeige meldet trotzdem „✅ Ready“. |
| Selbstdiagnose / Selbstheilung | ❌ | `_with_auto_repair` ruft nicht existierende Methoden auf; Fehler werden als „ausgeführt (Fallback)“ gemeldet. 22 Stellen mit `pass  # Optimized error handling` verschlucken Fehler. |
| Cloud-Synchronisierung | ❌ | `cudi_unified_cloud_system.py` meldet „Google Drive verbunden“ ohne echte Verbindung (simuliert). |
| Telemetrie / Event-Bus | ✅ | `cudi_telemetry.py`, `cudi_event_bus.py` funktionieren (Event-Bus seit Fix ohne Hänger). |
| Rechnungsassistent-Plugin | 🟡 | eigenständig nutzbar, nicht mit Gedächtnis/Orchestrierung verbunden (nicht im Detail getestet). |

## 3. Funktionen des Digitalen Gehirns (`cudi_brain.py`)

| Funktion | Status | Befund |
|---|---|---|
| Arbeitsgedächtnis (`WorkingMemory`) | 🟡 | hält aktive Konzepte im RAM, wird nicht für Antworten genutzt |
| Langzeitgedächtnis (`LongTermMemory`, SQLite) | 🟡 | Tabellen episodisch/semantisch/prozedural/assoziativ; nur episodische Einträge werden geschrieben |
| Abruf aus dem Gedächtnis | ❌ | `_answer_from_memory` erwartet eine Liste, bekommt ein Dict → Fehler wird verschluckt |
| „Merke dir …“ | ❌ | `learn_new_information` ruft nicht existierende Methode `store_concept` auf (AttributeError) |
| Recherche | ❌ | `_perform_external_research` ist simuliert (4 feste Begriffe, sonst „Recherche läuft …“) |
| Lernen (`ContinuousLearning`) | ❌ | speichert die Platzhaltertexte als „gelerntes Wissen“ → verschmutzt das Gedächtnis |
| Emotionserkennung, Metakognition | 🟡 | Schlüsselwort-Heuristik, Kennzahlen sind feste Schätzwerte |
| Quellen, Zeitstempel, Konflikterkennung, Dokumentenimport, Projektgedächtnis | ⬜ | nicht vorhanden |

## 4. Doppelte, konkurrierende und isolierte Komponenten

* **18 doppelt definierte Methoden** in `CUDISupremeMainWindow` (u. a. `init_ui`, `send_message`,
  `process_user_input`, `init_cudi_supreme`). In Python gewinnt die zweite Definition – die erste
  ist toter Code (dort hing z. B. der Command-Router).
* **Drei Konversations-Weichen** mit gleicher Schlüsselwortliste: `cudi_conversation_handler.py`,
  `process_user_input_no_questions_original`, `_handle_normal_conversation`.
* **Mindestens sechs getrennte Wissens-/Gedächtnisspeicher:** `cudi_brain_memory.db`,
  `cudi_learning.db`, `config/knowledge_base.json`, `cudi_generated/learning_data_*.json`,
  `cudi_generated/cudi_learning_log.json`, `data/cloud_sync.db`, dazu die verwaiste
  `cudi_autonomous_knowledge.db` im Backup. Keiner liest die Daten der anderen.
* **Zwei GUI-Frameworks:** Hauptanwendung PySide6, aber `cudi_supreme_harmonized.py` und
  `cudi_self_healing_addon.py` nutzen PyQt5; zusätzlich Tkinter (Hilfe-System, Plugin-Dialog, Plugin).
* **Fünf Startwege:** `cudi_supreme_gui.py`, `launch_cudi_supreme.py`, `launch_cudi_perfect.py`,
  `LAUNCH_CUDI_SUPREME_GUI.py` (benötigt fehlendes `desktop_gui/`), `CUDI_SUPREME.bat`,
  zusätzlich `scripts/cudi-start-safe.js`, `cudi-diagnose.sh`, `CUDI-Diagnose.ps1`.
* **Zwei Plugin-Manager:** `simple_plugin_manager.py` und `simple_plugin_manager_enhanced.py`.

## 5. Wiederverwendbare Bestandteile

* PySide6-Oberfläche (Layout, Navigation, Chat-Ansicht, Theme) – als Hülle gut weiterverwendbar.
* `cudi_event_bus.py` und `cudi_telemetry.py` – sauber getrennt, nun getestet bzw. lauffähig.
* `AdvancedCommunicationEngine` – Grundidee eines Modellanbieter-Wechsels; wird in einen Model Manager überführt.
* `SystemInterface` in `cudi_brain.py` – Ansatz für erlaubte/verbotene Operationen (Basis für Berechtigungen).
* SQLite-Schema-Ideen des Langzeitgedächtnisses (episodisch/semantisch/prozedural).
* `plugins/rechnungsassistent.py` als echtes Plugin-Beispiel.

## 6. Tatsächlich ausgeführte Tests (2026-10-26, Linux, Python 3.13)

| Test | Ergebnis |
|---|---|
| `CudiBrain` direkt: „Hallo CUDI.“ | ❌ Antwort: „Basierend auf meiner Recherche: Recherche zu hallo: Recherche zu 'hallo' läuft …“ |
| `CudiBrain` direkt: „Kannst du programmieren?“ | ❌ gleiche Platzhalterantwort |
| `CudiBrain`: „Merke dir: Mein Lieblingseditor ist VS Code“ → „Was ist mein Lieblingseditor?“ | ❌ nicht gespeichert, nicht wiedergefunden |
| `CudiBrain.learn_new_information()` | ❌ `AttributeError: 'LongTermMemory' object has no attribute 'store_concept'` |
| GUI-Start (offscreen) vor Fix | ❌ blockiert dauerhaft in `cudi_event_bus.start_sync` (Traceback gesichert) |
| GUI-Start (offscreen) nach Fix | ✅ Fenster initialisiert, Event-Bus läuft im Hintergrund |
| GUI-Chat „Hallo CUDI.“ | 🟡 feste Begrüßung („Hey! Ich bin bereit für deine Aufgaben! 🚀“), stabil |
| GUI-Chat „Kannst du programmieren?“ | ❌ erzeugt zweimal eine Markdown-Vorlagendatei in `cudi_content/`, meldet „Ich habe über 'programmieren' gelernt!“, obwohl nur ein Fehler-Platzhalter gespeichert wurde |
| `pytest tests/` | ✅ 3 bestanden (`test_event_bus.py`) |

Abnahmetests A–K aus dem Master-Prompt: nur A (stabil, aber nicht natürlich) und G (teilweise) sind
heute erfüllbar; B, C, D, E, F, H, I, K scheitern am aktuellen Code. Ziel der nächsten Phasen ist,
diese Tests automatisiert grün zu bekommen.

## 7. Was wurde in dieser Sitzung geändert?

1. `cudi_event_bus.py`: `start_sync()` startet den Worker jetzt in einem eigenen Hintergrund-Thread
   statt den GUI-Hauptthread zu blockieren; neu `stop_sync()`; `emit_sync()` leitet Events
   thread-sicher an den Bus-Loop weiter.
2. `tests/test_event_bus.py`: 3 Regressionstests (Start im Hauptthread, Zustellung an Abonnenten, Stopp).
3. `requirements.txt`: fehlendes `PySide6` (das tatsächlich verwendete GUI-Framework) ergänzt.
4. Diese Dokumentation unter `docs/`.

Keine bestehende Funktion wurde entfernt.
