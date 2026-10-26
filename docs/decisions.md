# Architekturentscheidungen

Format: Entscheidung · Begründung · verworfene Alternativen · Status.
Status „vorgeschlagen“ = wird umgesetzt, sofern der Nutzer nicht widerspricht.
Status „wartet auf Zustimmung“ = wird erst nach ausdrücklicher Freigabe umgesetzt.

---

## D-001 PySide6-Oberfläche behalten

* **Entscheidung:** Die bestehende PySide6-GUI bleibt die Hauptoberfläche. Tkinter-/PyQt5-Teile
  werden nicht erweitert.
* **Begründung:** Die Hauptanwendung ist bereits PySide6 (Layout, Navigation, Theme funktionieren).
  Ein Framework-Wechsel brächte keinen Funktionsgewinn.
* **Verworfen:** Neuschreiben in Tkinter (Master-Prompt erwähnt Tkinter, vorhanden ist aber Qt);
  Web-Oberfläche.
* **Status:** angenommen.

## D-002 Logik in ein GUI-unabhängiges Paket `cudi/` auslagern

* **Entscheidung:** Neuer Kern (Orchestrator, Gedächtnis, Modelle, Werkzeuge) als Paket `cudi/`, das
  ohne GUI importier- und testbar ist. Die GUI ruft nur `Orchestrator.handle()` auf.
* **Begründung:** Die heutige 6 000-Zeilen-Klasse vermischt alles und ist nicht testbar. Ein
  separates Paket ermöglicht automatisierte Abnahmetests A–K ohne Bildschirm.
* **Verworfen:** Weiteres Ergänzen von Methoden in `cudi_supreme_gui.py` (verstärkt das Problem);
  kompletter Neubau inklusive GUI (verliert funktionierende Oberfläche).
* **Status:** umgesetzt (2026-10-26), Paket `cudi/`.

## D-003 Eine SQLite-Datenbank für das Digitale Gehirn, FTS5 statt Vektordatenbank

* **Entscheidung:** Eine Datei `cudi_brain.db` mit Schema-Versionstabelle und Migrationen; Volltextsuche
  über SQLite FTS5. Semantische Suche (Embeddings) erst, wenn die Datenmenge oder Suchqualität es
  erfordert – dann als optionale Erweiterung derselben Datenbank.
* **Begründung:** SQLite ist in Python enthalten, lokal, sicherungsfreundlich (eine Datei) und
  reicht für persönliche Datenmengen. FTS5 liefert Fundstellen und Ranking ohne Zusatzpaket.
* **Verworfen:** Vektordatenbank (Chroma/FAISS) von Anfang an – zusätzliche schwere Abhängigkeiten
  ohne belegten Bedarf; Weiterverwendung der sechs bestehenden Speicher – führt zu Doppelhaltung.
* **Status:** umgesetzt (`data/cudi_brain.db`, Schema v1; ergänzend Wortteil-Suche per LIKE). Bestehende `.db`-Dateien bleiben unverändert liegen.

## D-004 Model Manager mit Anbieter-Schnittstelle; Ollama lokal als Standard

* **Entscheidung:** Einheitliche Schnittstelle `generate(messages, tools=None)`; Anbieter Ollama
  (lokal), Anthropic, OpenAI. Reihenfolge und Modellnamen in `config/settings.json`; API-Schlüssel nur
  aus Umgebungsvariablen bzw. `.env` (nicht versioniert). Fallback-Kette; wenn kein Modell erreichbar
  ist, meldet CUDI das ausdrücklich statt Textbausteine auszugeben.
* **Begründung:** Datenschutz (lokale Verarbeitung zuerst), Austauschbarkeit, ehrliche Fehlermeldung.
* **Verworfen:** Fest verdrahtete Modellnamen im Code (heutiger Zustand); `transformers`/`torch`
  direkt in der App (mehrere GB, langsamer Start).
* **Status:** umgesetzt. Standardreihenfolge ollama → anthropic → openai (D-010); der Nutzer kann sie in `.env` ändern.

## D-005 Werkzeuge mit Berechtigungsstufen

* **Entscheidung:** Jedes Werkzeug deklariert Stufe 1 (lesen) bis 5 (extern/irreversibel). Stufe 1–2
  automatisch; Stufe 3–4 nur im freigegebenen Arbeitsordner und mit Bestätigung in der GUI (sofern
  nicht für die Sitzung freigegeben); Stufe 5 immer mit Bestätigung. Vor dem Überschreiben wird eine
  Sicherungskopie angelegt.
* **Begründung:** Anforderungen aus Abschnitt 12 des Master-Prompts.
* **Status:** umgesetzt (Standard: Stufe 1–2 automatisch, `auto_approve_level` in den Einstellungen).

## D-006 Speicherregeln für Erinnerungen

* **Entscheidung:** Dauerhaft gespeichert wird nur (a) was der Nutzer ausdrücklich speichern lässt
  („merke dir“, „speichere“) oder (b) was er bestätigt. Jede Erinnerung hat Quelle, Zeitstempel,
  Status (bestätigt / vorläufig / veraltet), Vertrauen. Widersprüche zu bestehenden Einträgen
  werden erkannt und als Rückfrage gemeldet statt überschrieben.
* **Begründung:** Verhindert Gedächtnisverschmutzung (früher: Platzhaltertexte als „Wissen“).
* **Status:** umgesetzt; bei Widerspruch wird die alte Angabe nach Bestätigung „veraltet“ (nicht gelöscht).

## D-007 Nicht ausführen: Harmonizer-/Selbstmodifikationsskripte

* **Entscheidung:** `cudi_perfect_harmonizer.py`, `cudi_system_harmonizer.py`, `cleanup_workspace.py`
  werden nicht mehr verwendet; Selbstverbesserung erfolgt nur über Vorschlag → Test → Freigabe.
* **Begründung:** Diese Skripte haben bereits Fehlerbehandlung entfernt (KI-10, KI-12).
* **Status:** angenommen für die Arbeitsweise; Archivierung der Dateien wartet auf Zustimmung.

## D-008 Event-Bus-Worker im eigenen Thread

* **Entscheidung:** `CUDIEventBus.start_sync()` startet einen Daemon-Thread mit eigenem asyncio-Loop.
* **Begründung:** Behebt KI-01, ohne die Schnittstelle (`start_sync`, `emit`, `subscribe`) zu ändern.
* **Verworfen:** Event-Bus deaktivieren (verliert Telemetrie-Ereignisse); qasync-Integration in den
  Qt-Loop (zusätzliche Abhängigkeit).
* **Status:** umgesetzt und getestet (2026-10-26).

## D-009 Chat der Oberfläche über den neuen Kern (Freigabe E-1)

* **Entscheidung:** `send_message` leitet jede Chat-Nachricht an den Orchestrator. Die alte
  Verarbeitung bleibt im Code und springt nur ein, wenn der Kern nicht geladen werden kann.
* **Begründung:** Nutzerauftrag vom 2026-10-26: „mach, dass es genau so funktioniert, wie ich es
  gesagt habe“ – der alte Weg erzeugte Vorlagendateien statt Antworten.
* **Status:** umgesetzt. Alte Methoden nicht entfernt (Aufräumen nur nach Zustimmung, Vorschlag V8).

## D-010 Standard-Modellreihenfolge: lokal zuerst; Claude-Standardmodell claude-opus-5-5

* **Entscheidung:** ollama → anthropic → openai. Claude wird über die offizielle `anthropic`-SDK mit
  `claude-opus-5-5`, `effort=medium` und serverseitigem Ersatzmodell (`fallbacks="default"`) angesprochen.
* **Begründung:** Lokale Verarbeitung schützt Daten und kostet nichts; Claude Opus 5.5 ist das
  aktuelle Standardmodell. Jede Antwort zeigt Anbieter/Modell und ob lokal oder extern verarbeitet wurde.
* **Verworfen:** OpenAI-kompatible Zwischenschichten für Claude (nicht empfohlen).

## D-011 Ohne Sprachmodell: ehrlich eingeschränkt statt Textbausteine

* **Entscheidung:** Ist kein Modell erreichbar, beantwortet CUDI Begrüßung, Fähigkeitsfragen,
  Gedächtnis- und Dokumentfragen regelbasiert und sagt bei allem anderen klar, dass ein Modell fehlt
  und wie man es einrichtet.
* **Begründung:** Master-Prompt: „keine Oberfläche, die Funktionen nur simuliert“.

## D-012 Dokumentauszüge an externe Modelle: standardmäßig erlaubt, abschaltbar

* **Entscheidung:** Passende Auszüge importierter Dokumente gehen auch an externe Modelle mit
  (sonst funktioniert „Frag mein Dokument“ mit Claude/OpenAI nicht). Abschaltbar über
  `share_documents_with_external_models: false` in `config/settings.json`.
* **Begründung:** Nur die zur Frage passenden Abschnitte werden gesendet, und nur wenn der Nutzer
  einen externen Anbieter selbst eingerichtet hat. Lokale Modelle sind immer bevorzugt.
* **Status:** umgesetzt; Test `test_external_model_does_not_get_documents_when_disabled`.

## D-013 Regeln für eindeutige Anliegen, Sprachmodell für den Rest

* **Entscheidung:** „Merke dir“, „vergiss“, Feedback, Vorlieben, Ja/Nein und /Befehle werden
  deterministisch verarbeitet; alles andere entscheidet das Sprachmodell mit Werkzeugen.
* **Begründung:** Speichern/Löschen muss verlässlich und nachvollziehbar sein – unabhängig davon,
  welches Modell gerade läuft. Freie Sprache versteht ein Modell besser als Schlüsselwortlisten.

## D-014 Vom Nutzer im Dialog gewählte Dateien gelten als freigegeben

* **Entscheidung:** Wählt der Nutzer im Menü „Dokument importieren…“ eine Datei, ist das die Freigabe
  zum Lesen dieser Datei. Schlägt dagegen das Modell vor, eine Datei außerhalb der freigegebenen
  Ordner zu lesen, wird nachgefragt (Stufe 3).
* **Begründung:** Schutz vor manipulierten Anweisungen in Dokumenten, ohne den Nutzer zu gängeln.
