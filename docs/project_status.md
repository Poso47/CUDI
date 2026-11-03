# Projektstatus CUDI + Digitales Gehirn

Stand: 2026-10-26 · Phase 1–2 abgeschlossen · Phase 3 (Kern), Phase 4 (Digitales Gehirn) und
Phase 6 (neues Hauptfenster) umgesetzt

Diese Datei beschreibt den **tatsächlichen** Codezustand. Testergebnisse stammen nur aus Tests, die
wirklich ausgeführt wurden (Abschnitt 4). Die ursprüngliche Bestandsaufnahme (Phase 1) steht in
Abschnitt 6.

---

## 1. Kurzfassung

CUDI hat jetzt einen echten, getesteten Kern im Paket `cudi/` und ein neues, aufgeräumtes
Hauptfenster (`ui/main_window.py`), das nur echte Funktionen zeigt. Alles läuft über den Kern:

* **Ein Weg für jede Nachricht:** Absicht → Kontext aus dem Digitalen Gehirn → Sprachmodell mit
  Werkzeugen (oder Regel) → Berechtigungsprüfung → Ausführung → Qualitätsprüfung → Speicherung.
* **Keine vorgetäuschten Aktionen mehr im Chat:** Jede Aktion erscheint mit ihrem echten Status
  (✅ ausgeführt · ❌ fehlgeschlagen · ⛔ abgelehnt). Es entstehen keine automatischen
  Vorlagendateien mehr.
* **Ein Gedächtnis:** eine SQLite-Datenbank `data/cudi_brain.db` für Erinnerungen, Gesprächsverlauf,
  Projekte, Aufgaben, Dokumente, Verlauf/Feedback und Modellaufrufe.
* **Austauschbare Sprachmodelle:** Ollama (lokal), Claude (Anthropic), OpenAI – mit
  Ausweichreihenfolge. Ist keins erreichbar, sagt CUDI das klar und arbeitet eingeschränkt weiter.

## 2. Was funktioniert (implementiert und getestet)

| Bereich | Funktion | Wo |
|---|---|---|
| Start | `python main.py` (Fenster), `--cli` (Terminal), `--diagnose` | `main.py`, `cudi/cli.py` |
| Einstellungen | Standardwerte → `config/settings.json` → `.env`/Umgebungsvariablen; Schlüssel nie in Dateien des Repos | `cudi/config/settings.py` |
| Protokoll | `logs/cudi.log` (rotierend) | `cudi/config/logging_config.py` |
| Orchestrator | Ablaufsteuerung, Werkzeugschleife (max. 8 Schritte), Unterbrechung für Freigaben, Qualitätsprüfung | `cudi/core/orchestrator.py` |
| Absichtserkennung | Befehle, „merke dir“, „vergiss“, „künftig …“, Feedback, Ja/Nein, Rückfragen; DE/EN | `cudi/core/intent_router.py` |
| Berechtigungen | Stufen 1–5; ab Stufe 3 Freigabe (Dialog oder „ja/nein“), Stufe 5 immer; „für diese Sitzung erlauben“ | `cudi/core/permissions.py` |
| Persönlichkeit | Jarvis-artiger Kollege, handelt statt aufzuzählen, fragt gezielt nach, ehrlich bei Grenzen | `cudi/core/persona.py` |
| Gedächtnis | Speichern nur auf Wunsch, Quelle/Zeitstempel/Status (bestätigt/vorläufig/veraltet), Duplikaterkennung, Widerspruchserkennung mit Rückfrage, Korrektur, Löschen, Export | `cudi/brain/memory.py` |
| Arbeitskontext | Gesprächsverlauf in der DB (überlebt Neustart), offene Rückfragen, zuletzt bearbeitete Dateien | `cudi/brain/conversation.py` |
| Projektgedächtnis | Projekte, Ziele, Anforderungen, Entscheidungen, Probleme, getestete Lösungen, nächste Schritte, Aufgaben | `cudi/brain/projects.py` |
| Wissen/Dokumente | Import PDF, DOCX, TXT, MD, JSON, CSV; Abschnitte mit Fundstelle (Seite/Abschnitt/Zeilen); Duplikaterkennung; Volltextsuche (FTS5 + Wortteile) | `cudi/brain/knowledge.py` |
| Kontextaufbau | Vorlieben/Fakten, passende Erinnerungen, aktives Projekt, Dokumentauszüge (als Daten markiert), Widerspruchshinweise | `cudi/brain/context_builder.py` |
| Lernen | Feedback („richtig/falsch“, „Lösung hat (nicht) funktioniert“), Vorlieben („künftig …“), Hinweis an das Modell, wenn ein identischer Werkzeugaufruf schon gescheitert ist | `cudi/brain/episodes.py`, Orchestrator |
| Verlaufsprotokoll | jede Werkzeugausführung, Fehler, Feedback, Modellaufruf (Dauer, Tokens) | `cudi/brain/episodes.py` |
| Modelle | Ollama (lokal, nimmt installiertes Modell, weicht ohne Werkzeugunterstützung aus), Claude (offizielle SDK, Standard `claude-opus-5-5`, serverseitiges Ersatzmodell bei Ablehnung), OpenAI | `cudi/models/` |
| Werkzeuge (25) | Dateien auflisten/lesen/schreiben (nur Arbeitsordner, Sicherung vor Überschreiben), Gedächtnis, Projekte, Aufgaben, Dokumente, Diagnose, Sicherung/Wiederherstellung, Export, Altbestand-Import | `cudi/tools/` |
| Selbstdiagnose | kritisch / Warnung / optional, mit Lösungsvorschlag | `cudi/diagnostics/health.py` |
| Sicherung | täglich automatisch beim Start (die letzten 10), manuell `/sicherung`, Wiederherstellung mit vorheriger Sicherheitskopie | `cudi/brain/database.py` |
| Hauptfenster (Standard) | Navigation mit Chat, Gedächtnis (suchen, korrigieren, löschen, exportieren), Projekte (anlegen, aktiv setzen, Einträge), Aufgaben (Status setzen), Dokumente (importieren, durchsuchen mit Fundstelle), Modelle (Status, erneut prüfen), Werkzeuge (Stufe, Freigaben), Diagnose, Einstellungen (Name, Anrede, Modelle, Freigabestufe, Datenschutz); Sprechblasen passen sich Text und Fenster an; Freigabe-Dialog; Enter sendet | `ui/main_window.py`, `ui/pages.py`, `ui/chat_view.py`, `ui/theme.py` |
| Alte Oberfläche (`--alt`) | Chat → Kern, Freigabe-Dialog, Menü „🧠 Gehirn“; Stil-Kaskade und Fenstergröße korrigiert | `cudi_supreme_gui.py`, `ui/brain_dialog.py` |
| Start | Doppelklick `CUDI_STARTEN.bat` / `cudi_starten.sh` (richtet `.venv` selbst ein), VS Code F5 | Starter, `.vscode/launch.json` |

## 3. Was (noch) nicht funktioniert

* **Kein Sprachmodell vorinstalliert:** Ohne Ollama oder API-Schlüssel beantwortet CUDI nur Befehle,
  Gedächtnis- und Dokumentfragen. Einrichtung: `docs/user_guide.md`.
* **Alte Oberfläche** (`python main.py --alt`): Ihre Knöpfe (Quick Actions, „Train Model“,
  Tool-Launcher, Plugin-Manager, Selbstheilung, Cloud) laufen über die alte Logik und sind teils
  Attrappen; das Layout bleibt dort eng (KI-16). Das neue Standardfenster enthält diese Knöpfe nicht.
* Nicht implementiert: Sprachsteuerung, Websuche, Code ausführen/Tests starten, E-Mail/Kalender,
  semantische Suche (Embeddings), Agenten-Rollen, Kreativ-/Videostudio, Synchronisierung zwischen
  Geräten. Vorschläge dazu: `implementation_plan.md`.
* Offene Freigaben gehen bei einem Neustart verloren (bewusst: nichts wird ohne erneute Freigabe ausgeführt).

## 4. Tatsächlich ausgeführte Tests (2026-10-26, Linux, Python 3.13)

**Automatisch:** `python -m pytest tests/` → **55 bestanden, 0 fehlgeschlagen**

| Datei | Inhalt |
|---|---|
| `tests/test_acceptance.py` | Abnahmetests A–K aus dem Master-Prompt (25 Tests) |
| `tests/test_brain.py` | Gedächtnisregeln, Vorlieben, Feedback, Fehler-Lernen, Dokumente als Daten, Datenschutz-Schalter, Altbestand, keine Schlüssel in Einstellungen, Zugangsdaten-Dateien gesperrt, tolerante Werkzeugparameter |
| `tests/test_models.py` | Ollama/OpenAI/Claude-Anfrageformat, Werkzeugaufrufe, Fehlermeldungen, Ablehnung – ohne Netzwerk (Attrappen) |
| `tests/test_event_bus.py` | Start-Hänger der GUI (Regression) |
| `tests/test_ui.py` | Neues Hauptfenster offscreen: Chat-Rundlauf, alle Bereiche, Freigabe-Dialog schreibt Datei, Sprechblasen-Breite/-Höhe, Einstellungen ohne Schlüssel |

Abnahmetests im Einzelnen (alle bestanden): A Hallo-Chat (mit/ohne Modell) · B „Kannst du
programmieren?“ fragt nach dem Ziel, erzeugt nichts · C Werkzeug wird aufgerufen, echter Status,
Fehler wird nie als Erfolg gemeldet · D Erinnerung übersteht Neustart und erreicht das Modell ·
E Projektstand und Verlauf überstehen Neustart · F DOCX/PDF-Import, Antwort mit Fundstelle,
Doppelimport erkannt · G fehlendes/ausfallendes Modell wird gemeldet, Ausweichen auf nächstes
Modell · H Widerspruch → Rückfrage, alte Angabe wird „veraltet“ statt gelöscht · I Schreiben/Löschen
braucht Freigabe, Ablehnung wirkt, Schreiben außerhalb des Arbeitsordners blockiert · J alte Module
und GUI-Methoden bleiben erhalten · K Neustart ohne Duplikate, Integrität, Sicherung/Wiederherstellung.

Hinweis: In allen Tests mit Sprachmodell wird ein **Fake-Modell** mit festem Drehbuch verwendet.
Geprüft wird damit die Verarbeitung (Kontext, Werkzeuge, Freigaben, Status) – nicht die
Antwortqualität eines echten Modells. Ein echtes Modell war in dieser Umgebung nicht verfügbar.

**Manuell (automatisiert gesteuert):**
* Neues Hauptfenster offscreen bei 900×600, 1280×720 und 1920×1080 mit Bildschirmfotos aller Bereiche:
  keine Überlappungen, keine abgeschnittenen Texte, Sprechblasen umbrechen sinnvoll.
* Starter `cudi_starten.sh` aus frischer Kopie: legt `.venv` an, installiert, startet. `CUDI_STARTEN.bat`
  folgt demselben Ablauf, konnte aber mangels Windows hier nicht ausgeführt werden.
* Echte PySide6-Oberfläche im Offscreen-Modus: „Hallo CUDI.“, „Kannst du programmieren?“,
  „Schreib mir ein Hallo-Welt-Skript …“ (Freigabe-Dialog → Datei `workspace/hallo.py` entsteht),
  „Merke dir …“ – alles über den neuen Kern; keine neue Datei in `cudi_content/`; Menü „🧠 Gehirn“
  und Gehirn-Ansicht zeigen echte Daten.
* `python main.py --diagnose` und `python main.py --cli` ohne Sprachmodell: laufen, melden fehlende
  Modelle mit Einrichtungshinweis.

## 5. Änderungen an bestehenden Dateien

* `cudi_supreme_gui.py`: `send_message` leitet an den neuen Kern weiter (alte Verarbeitung bleibt als
  Rückfallebene, falls der Kern nicht lädt); neue Methoden `_init_cudi_core`, `_send_to_core`,
  `_run_core`, `_on_core_result`, `_ask_core_confirmation`, `_open_brain_dialog`,
  `_import_document_dialog`, `_open_workspace`; `new_chat` startet auch im Kern ein neues Gespräch;
  Signal `core_result_ready`; `import html`. **Keine bestehende Methode entfernt.**
* `cudi_event_bus.py`: Start-Hänger behoben (siehe `known_issues.md` KI-01).
* `requirements.txt`: PySide6 ergänzt. Neu: `requirements-core.txt` (schlanke Installation).
* `.gitignore`: Laufzeitdaten (`data/`, `logs/`, `workspace/`, `import/`, `.env`, `config/*.json` der Laufzeit).
* `README.md`: neu geschrieben (die alte Fassung beschrieb nicht vorhandene Dateien).

---

## 6. Ursprüngliche Bestandsaufnahme (Phase 1, unverändert gültig für den Altbestand)

* 29 Python-Dateien (~16 900 Zeilen); Hauptanwendung `cudi_supreme_gui.py` (PySide6, eine Klasse mit
  220 Methoden, davon 18 doppelt definiert).
* **Kein separates „Digitales Gehirn“-Projekt im Repository**; einziges Gehirn-Modul war
  `cudi_brain.py` (ohne Sprachmodell, Antworten aus Textbausteinen, „Merke dir“ defekt).
* Die im Master-Prompt genannten Dateien (`main.py`, `brain.py`, `voice.py`, `local_llm.py`,
  `memory.json`, `settings.json` …) existierten nicht; elf importierte Module fehlten.
* Ursache für „Markdown-Liste statt Handlung“: ein Rückfallzweig erzeugte bei fast jeder Nachricht
  eine Vorlagendatei (`known_issues.md` KI-02) – im Chat jetzt durch den Orchestrator ersetzt.
* Mindestens sechs getrennte Wissensspeicher; drei konkurrierende Konversationsweichen; Selbstheilung
  rief nicht existierende Methoden auf; 22 verschluckte Fehler; simulierte Cloud-Verbindung.
