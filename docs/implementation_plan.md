# Implementierungsplan

Jeder Schritt endet mit einem **überprüfbaren Ergebnis** (automatischer Test oder reproduzierbare
Prüfung). Reihenfolge = Priorität. Grundlage: `project_status.md`, `architecture.md`, `decisions.md`.

## Offene Entscheidungen des Nutzers

| ID | Frage | Auswirkung |
|---|---|---|
| E-1 | Darf der heutige Chat-Pfad (Textbausteine + automatische Vorlagendateien, KI-02) durch den neuen Orchestrator **ersetzt** werden? Die alten Methoden bleiben im Code, werden aber nicht mehr aufgerufen. | Voraussetzung für Schritt 3.6 |
| F-1 | Welches Sprachmodell soll CUDI nutzen? (a) lokal über Ollama, (b) Anthropic-API, (c) OpenAI-API, (d) mehrere mit Reihenfolge | Standardkonfiguration in Schritt 3.3 |
| F-2 | Ist das „Digitale Gehirn“ ein separates Projekt/Repository? Falls ja: wo liegt es? | Falls ja, Bestandsaufnahme ergänzen, bevor Phase 4 beginnt |
| F-3 | Sollen die 40 Wissenseinträge aus der Backup-Datenbank importiert werden (als „unbestätigt“)? | Schritt 4.6 |

---

## Phase 1 – Bestandsaufnahme ✅ abgeschlossen

Ergebnis: `docs/project_status.md`, `docs/known_issues.md`.

## Phase 2 – Zielarchitektur und Integrationsplan ✅ abgeschlossen (Entwurf)

Ergebnis: `docs/architecture.md` (inkl. Zuordnungstabelle), `docs/decisions.md`, dieses Dokument.

## Phase 3 – Gemeinsamer Kern (als Nächstes)

| Schritt | Inhalt | Prüfung | Status |
|---|---|---|---|
| 3.0 | Startblocker beheben (Event-Bus, KI-01) | `tests/test_event_bus.py` grün, GUI startet | ✅ |
| 3.1 | Paket `cudi/` mit `config/settings.py` (JSON + Umgebungsvariablen, `.env.example`) und `logging_config.py` | Tests: Standardwerte, Überschreiben per Umgebungsvariable, keine Schlüssel im Repo | offen |
| 3.2 | `core/results.py` + `core/permissions.py` (Stufen 1–5, Bestätigungs-Callback) | Test I: Stufe-4-Aktion ohne Bestätigung wird abgelehnt | offen |
| 3.3 | `models/model_manager.py` + Anbieter Ollama/Anthropic/OpenAI, Fallback-Kette, ehrliche Fehlermeldung | Test G: kein Anbieter erreichbar → klare Meldung, kein Textbaustein; Anbieter per Fake-Provider testbar | offen |
| 3.4 | `tools/registry.py` + erste echte Werkzeuge: Datei lesen/auflisten/schreiben im Arbeitsordner (mit Sicherung) | Test C: Werkzeug wird aufgerufen, Datei existiert danach, Status korrekt | offen |
| 3.5 | `core/intent_router.py` + `core/orchestrator.py`: LLM-Werkzeugaufrufe, Regel-Fallback für „merke dir“, Slash-Befehle, Rückfragen bei fehlenden Angaben | Test A, B (headless, mit Fake-Modell) | offen |
| 3.6 | GUI-Anbindung: `send_message` → Worker-Thread → `Orchestrator.handle()`; Bestätigungsdialog für Stufe ≥ 3 | GUI-Smoke-Test offscreen: „Hallo CUDI.“ und „Kannst du programmieren?“ erzeugen **keine** Dateien | wartet auf E-1 |
| 3.7 | Einheitlicher Start `main.py` + Selbstdiagnose beim Start (Python-Version, PySide6, Datenbank, Modell) | Diagnosebericht mit kritisch/Warnung/optional; optionales Modul fehlt → App startet trotzdem | offen |

## Phase 4 – Digitales Gehirn

| Schritt | Inhalt | Prüfung |
|---|---|---|
| 4.1 | `brain/database.py`: `cudi_brain.db`, Schema-Version, Migrationen, Sicherung/Wiederherstellung | Test K: Neustart ohne Datenverlust/Duplikate; Backup → Restore identisch |
| 4.2 | `brain/memory.py`: Erinnerungen mit Quelle, Zeitstempel, Status, Deduplizierung, Korrektur, Löschung, Export | Test D: speichern → neue Instanz → wiederfinden |
| 4.3 | Widerspruchserkennung | Test H: zwei widersprüchliche Angaben → Konflikt + Rückfrage |
| 4.4 | `brain/working_memory.py` + `context_builder.py`: Gesprächsverlauf und relevante Erinnerungen fließen in den Prompt | Test: gespeicherte Präferenz beeinflusst Antwort (Fake-Modell prüft Prompt) |
| 4.5 | `brain/projects.py`: Projektgedächtnis + Entscheidungsprotokoll | Test E: Projektstand nach Neustart verfügbar |
| 4.6 | `brain/knowledge.py` + `tools/document_tools.py`: Import PDF/DOCX/TXT/MD/JSON/CSV, Abschnitte, FTS5, Duplikaterkennung, Fundstellen; Migration `config/knowledge_base.json` | Test F: Dokument mit eindeutiger Information → Frage → Antwort mit Fundstelle |
| 4.7 | Feedback („richtig/falsch/so künftig“) → Speicherung + Verwendung | Test: Feedback ändert gespeicherte Präferenz nachvollziehbar |

## Phase 5 – Agenten und Werkzeugnutzung

Rollen Research, Document, Coding, Planning, Quality als Konfiguration (Prompt + erlaubte Werkzeuge)
über dem Orchestrator; Quality-Prüfung vor Ausgabe. Werkzeuge: Projektdateien untersuchen, Tests
ausführen (Stufe 4, Bestätigung), Websuche (nur wenn freigegeben). Prüfung: mehrstufige Aufgabe mit
Werkzeugaufrufen und geprüftem Ergebnis.

## Phase 6 – Benutzeroberfläche

Ansichten Gehirn (Erinnerungen/Wissen/Dokumente), Aufgaben, Projekte, Modelle, Werkzeuge, Diagnose,
Einstellungen – jeweils mit echten Daten aus dem Kern. Nicht verfügbare Funktionen (Sprache, Cloud)
werden als „nicht verfügbar“ angezeigt statt „✅ Ready“.

## Phase 7 – Diagnose und Selbstverbesserung

Ersetzt die defekte Selbstheilung (KI-05) durch Diagnose + Reparaturvorschlag + Test + Freigabe.

## Phase 8 – Kreativ-/Produktionsmodul

Eigenes Modul; erst nach stabiler Basis. Skript → Storyboard → Assets-Plan → Timeline; externe
Anbieter nur über Schnittstelle, keine vorgetäuschten Dienste.

## Phase 9 – Gesamtprüfung · Phase 10 – Übergabe

Abnahmetests A–K automatisiert, neue README und `docs/user_guide.md`.

---

## Nächster sinnvoller Schritt

Schritte 3.1–3.5 können ohne weitere Entscheidung umgesetzt werden (neues Paket, ändert kein
bestehendes Verhalten). Schritt 3.6 benötigt Antwort auf **E-1**, der Standardanbieter auf **F-1**.
