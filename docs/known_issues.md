# Bekannte Fehler und Integrationsprobleme

Stand: 2026-10-26. Status: 🔴 offen · 🟢 behoben. Reproduktionen wurden unter Linux/Python 3.13
mit der GUI im Offscreen-Modus (`QT_QPA_PLATFORM=offscreen`) bzw. direkt in Python durchgeführt.

| ID | Status | Schwere | Kurzbeschreibung |
|---|---|---|---|
| KI-01 | 🟢 | kritisch | GUI hängt beim Start (Event-Bus blockiert Hauptthread) |
| KI-02 | 🔴 | kritisch | Fast jede Nachricht erzeugt eine Markdown-Vorlagendatei statt einer Antwort/Handlung |
| KI-03 | 🔴 | kritisch | Kein Sprachmodell im Standard-Chatweg; Antworten sind Textbausteine |
| KI-04 | 🔴 | hoch | Vorgetäuschte Erfolgsmeldungen |
| KI-05 | 🔴 | hoch | Selbstheilung ruft nicht existierende Methoden auf |
| KI-06 | 🔴 | hoch | „Merke dir …“ funktioniert nicht; Gedächtnisabruf defekt |
| KI-07 | 🔴 | hoch | Sechs getrennte Wissensspeicher, keiner liest den anderen |
| KI-08 | 🔴 | mittel | 18 doppelt definierte GUI-Methoden; Command-Router ist toter Code |
| KI-09 | 🔴 | mittel | Schlüsselwort-Erkennung per Teilstring |
| KI-10 | 🔴 | mittel | 22 verschluckte Ausnahmen (`pass  # Optimized error handling`) |
| KI-11 | 🔴 | mittel | Laufzeit-Installation von Paketen per `pip` |
| KI-12 | 🔴 | mittel | Harmonizer-Skripte schreiben Quellcode per Regex um |
| KI-13 | 🔴 | niedrig | Fehlende Module, mehrere Startwege, PyQt5/PySide6/Tkinter gemischt |
| KI-14 | 🔴 | niedrig | README beschreibt eine nicht vorhandene Architektur |
| KI-15 | 🔴 | niedrig | Laufzeitdaten (Logs, generierte Dateien) liegen im Repository |

---

### KI-01 – GUI hängt beim Start 🟢 behoben

* **Symptom:** Fenster erscheint nicht; Programm hängt nach „📊 Event-Bus synchron aktiviert“.
* **Ursache:** `CUDIEventBus.start_sync()` rief im GUI-Hauptthread `asyncio.run(self._process_events())`
  auf – eine Endlosschleife. Unter Python 3.13 liefert `asyncio.get_event_loop()` im Hauptthread
  noch einen Loop, daher wurde dieser Zweig erreicht (in Nebenthreads nicht – deshalb trat der
  Fehler nur beim echten Start auf).
* **Reproduktion:** `tests/test_event_bus.py::test_start_sync_returns_in_main_thread` (vor dem Fix:
  Timeout nach 15 s; Traceback endete in `cudi_event_bus.py:89 start_sync`).
* **Lösung:** Worker läuft in eigenem Daemon-Thread mit eigenem Loop; `emit_sync()` nutzt
  `run_coroutine_threadsafe`; neu `stop_sync()`. 3 Tests grün; GUI startet offscreen.

### KI-02 – Vorlagendatei statt Antwort („Markdown-Liste statt Handlung“)

* **Reproduktion:** GUI starten, „Kannst du programmieren?“ senden.
* **Beobachtet:** zwei Meldungen „📤 CUDI Fallback – Ich erstelle Content basierend auf deiner
  Nachricht“ und eine neue Datei `cudi_content/content_response_<Zeit>.md` mit generischem Text.
* **Ursache:** `_force_real_action_fallback()` (`cudi_supreme_gui.py`, Kommentar „Absolute Fallback:
  Immer eine Datei erstellen“) wird in `process_user_input()` sowohl im Zweig „Intent erkannt“ als
  auch „nicht erkannt“ aufgerufen. `process_user_input_no_questions_original()` erzeugt bei mehr als
  zwei Wörtern ebenfalls Dateien.
* **Lösungsweg:** Orchestrator ersetzt diesen Pfad; Dateien werden nur noch erstellt, wenn der Nutzer
  das ausdrücklich verlangt und die Berechtigung vorliegt. **Erfordert Zustimmung**, da bestehendes
  Verhalten entfernt wird (siehe `implementation_plan.md`, Entscheidung E-1).

### KI-03 – Kein Sprachmodell im Standardweg

* `CudiBrain` enthält kein Sprachmodell; „Recherche“ ist simuliert (4 fest eingetragene Begriffe).
* `AdvancedCommunicationEngine` wird nur erreicht, wenn `self.brain` fehlt – das ist nie der Fall.
* Zusätzlich: veraltete Modellnamen (`gpt-4`, `claude-3-sonnet-20240229`, `llama2`), kein
  Gesprächsverlauf, Systemprompt und Nutzertext in einer einzigen Nachricht.

### KI-04 – Vorgetäuschte Erfolgsmeldungen

* „✅ Ich habe über 'programmieren' gelernt!“, obwohl nur `{"definition": "… (Recherche-Fehler,
  Basis-Info)", "source": "fallback"}` gespeichert wurde.
* `except`-Zweige melden „Datei-Erstellung ausgeführt (Fallback)“ / „Aktionen ausgeführt
  (Minimal-Fallback)“, obwohl ein Fehler auftrat.
* `cudi_unified_cloud_system.py`: „Google Drive verbunden“ – laut Kommentar simuliert.
* Statusanzeige „Voice ✅ Ready“, obwohl `get_voice_engine()` `None` liefert.

### KI-05 – Selbstheilung defekt

* `_with_auto_repair()` ruft `_attempt_perfect_repair` und `_execute_perfect_fallback` auf – beide
  existieren nicht. Jeder Fehler in einer überwachten Aktion löst daher einen `AttributeError` aus, der
  weiter außen als Erfolg (KI-04) gemeldet wird.

### KI-06 – Gedächtnis „Merke dir“ / Abruf

* `CudiBrain.learn_new_information()` → `AttributeError: 'LongTermMemory' object has no attribute 'store_concept'`.
* `_answer_from_memory()` erwartet eine Liste von Dicts, `retrieve_relevant_memories()` liefert ein
  Dict von Listen → Fehler wird verschluckt, generische Antwort.
* `_research_and_learn()` speichert den Platzhalter „Recherche zu '…' läuft“ als gelerntes Wissen.

### KI-07 – Getrennte Wissensspeicher

`cudi_brain_memory.db`, `cudi_learning.db`, `config/knowledge_base.json`,
`cudi_generated/learning_data_*.json`, `cudi_generated/cudi_learning_log.json`, `data/cloud_sync.db`,
dazu verwaist `CUDI_BACKUPS/…/cudi_autonomous_knowledge.db` (40 Einträge, Modul fehlt).

### KI-08 – Doppelte Methoden / toter Code

Doppelt in `CUDISupremeMainWindow`: `init_ui`, `init_cudi_supreme`, `connect_signals`,
`add_chat_message`, `send_message`, `process_user_input`, `clear_chat`, `export_chat`,
`open_plugin_manager`, `open_help_system`, `run_self_diagnosis`, `open_ai_settings`,
`launch_web_scraper`, `launch_email_assistant`, `launch_calendar_manager`, `launch_file_organizer`,
`handle_message_received`, `handle_status_changed`. Nur die jeweils zweite Definition ist aktiv; der
Aufruf von `CUDICommandRouter.route_command` steht in der inaktiven ersten `send_message`.

### KI-09 – Schlüsselwort-Erkennung per Teilstring

`'hi' in message` trifft „nichts“, „ja“ trifft „Jahr“, „ok“ trifft „Kokosnuss“. Fragen ohne
Schlüsselwort landen im Datei-Fallback (KI-02).

### KI-10 – Verschluckte Fehler

22 Stellen in `cudi_supreme_gui.py` mit `except Exception as e: pass  # Optimized error handling`.
Entstanden durch `cudi_perfect_harmonizer.py`, das `print(...)` in `except`-Blöcken per Regex durch
`pass` ersetzt hat. `cudi_supreme_gui.py.backup` ist eine ältere Fassung (5 452 Zeilen) ohne diese
Ersetzungen; sie enthält aber nicht alle späteren Änderungen und ist daher kein 1:1-Wiederherstellungspunkt.

### KI-11 – Paketinstallation zur Laufzeit

`_real_web_search()` führt bei fehlendem `bs4` `pip install requests beautifulsoup4` aus – ohne
Rückfrage. Verstößt gegen „keinen beliebigen Code ohne Zustimmung ausführen“.

### KI-12 – Harmonizer-Skripte

`cudi_perfect_harmonizer.py` verschiebt Dateien nach Mustern (`advanced_*.py`, `conversation_*.py` …)
und schreibt Quellcode per Regex um; enthält den festen Pfad `c:/Users/cakgu/Desktop/PROJEKTE MITTE/CUDI`.
Nicht mehr ausführen.

### KI-13 – Fehlende Module / Startwege / Frameworks

Siehe `project_status.md` Abschnitt 1 und 4. `LAUNCH_CUDI_SUPREME_GUI.py` benötigt das fehlende
Verzeichnis `desktop_gui/`. `cudi_supreme_harmonized.py` importiert PyQt5 und gleichzeitig die
PySide6-GUI.

### KI-14 – Veraltete README

`README.md` beschreibt `main.py`, `brain.py`, `system_access.py`, `setup.py`, `start_advanced_gui.py`
– keine dieser Dateien existiert. Wird in Phase 10 neu geschrieben (vorher Rückfrage nicht nötig, da
nur Dokumentation).

### KI-15 – Laufzeitdaten im Repository

`cudi_generated/`, `cudi_content/`, `cudi_research/`, `cudi_production_data/` (erfundene Demo-Kunden-
und Finanzdaten aus `cudi_production_data_generator.py`), `__pycache__/`-Dateien im Backup sind
versioniert. Vorschlag: in `.gitignore` aufnehmen, sobald die Ausgabeorte im neuen Kern festgelegt sind.
