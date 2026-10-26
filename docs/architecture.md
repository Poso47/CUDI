# Architektur CUDI + Digitales Gehirn

Dieses Dokument beschreibt (A) die **Altarchitektur** vor dem Umbau, (B) die **neue Architektur**
(seit 2026-10-26 umgesetzt: Kern, Gedächtnis, Modelle, Werkzeuge, Chat-Anbindung). Abschnitt C ordnet jede vorhandene
Komponente ihrem Zielmodul zu.

---

## A. Altarchitektur (vor dem Umbau; der Code existiert weiterhin)

```
                ┌─────────────────────────────────────────────────────────────┐
 Nutzer ──────▶ │ cudi_supreme_gui.py  (PySide6, 1 Klasse, 220 Methoden)      │
                │                                                             │
                │ send_message()                                              │
                │   └─ no_questions_mode (Standard: an)                       │
                │        └─ cudi_conversation_handler.py  (Schlüsselwörter)   │
                │             ├─ Smalltalk → feste Textbausteine              │
                │             ├─ Frage     → process_user_input()             │
                │             │                ├─ _route_intent_robust        │
                │             │                ├─ _force_real_action_fallback │
                │             │                │    └─ IMMER Vorlagendatei    │
                │             │                ├─ _check_and_learn_if_needed  │
                │             │                │    └─ config/knowledge_base  │
                │             │                └─ Thread: CudiBrain           │
                │             └─ Aktion    → process_user_input_no_questions_ │
                │                            original() → Vorlagendateien     │
                │                                                             │
                │ AdvancedCommunicationEngine (OpenAI/Anthropic/Ollama)       │
                │   └─ im Standardweg praktisch nie erreicht                  │
                └───────┬───────────────────────┬─────────────────────────────┘
                        │                       │
            ┌───────────▼─────────┐   ┌─────────▼──────────┐   ┌──────────────────┐
            │ cudi_brain.py       │   │ cudi_event_bus.py  │   │ cudi_telemetry.py│
            │ (kein LLM)          │   │ cudi_component_    │   │ cudi_logs/*.json │
            │ cudi_brain_memory.db│   │   bridge.py        │   └──────────────────┘
            │ cudi_learning.db    │   └────────────────────┘
            └─────────────────────┘
```

Wesentliche Eigenschaften:

* **Monolith:** Oberfläche, Intent-Erkennung, Aktionen, Lernen, Selbstheilung und Dateierzeugung
  liegen in einer einzigen Klasse.
* **Kein gemeinsamer Datenpfad:** GUI-Lernen schreibt in `config/knowledge_base.json`, das Gehirn in
  zwei SQLite-Dateien, der Router in `cudi_generated/`. Niemand liest die Daten des anderen.
* **Kein Sprachmodell im Standardweg:** Antworten stammen aus Textbausteinen.
* **Keine Berechtigungsprüfung** für Aktionen; Erfolg wird teils gemeldet, ohne dass etwas passiert ist.

---

## B. Neue Architektur (umgesetzt)

Stand: Kern, Digitales Gehirn, Modelle, Werkzeuge, Diagnose und die Chat-Anbindung der Oberfläche
sind implementiert und getestet (siehe `project_status.md`). Agenten-Rollen, Sprachsteuerung,
Websuche und Kreativstudio sind noch offen.

Grundsatz: Die PySide6-Oberfläche bleibt (keine Framework-Migration). Die Logik wird aus der GUI in
ein **GUI-unabhängiges Python-Paket `cudi/`** verlagert, das ohne Oberfläche testbar ist. Die GUI
ruft nur noch eine einzige Schnittstelle auf: `Orchestrator.handle(message) -> Result`.

```
Nutzer → GUI (ui/) → core.Orchestrator
                        │
                        ├─ 1. IntentRouter      (LLM-gestützt + Regel-Fallback)
                        ├─ 2. ContextBuilder    ← brain/: Arbeits-, Langzeit-, Projektgedächtnis, Wissen
                        ├─ 3. Planung           (einfache Schrittfolge; später PlanningAgent)
                        ├─ 4. Auswahl           → models.ModelManager / tools.ToolRegistry / agents
                        ├─ 5. PermissionManager (Stufe 1–5, Bestätigung über GUI)
                        ├─ 6. Ausführung        (echtes Werkzeug, echtes Ergebnis oder ehrlicher Fehler)
                        ├─ 7. Qualitätsprüfung  (Ergebnis vorhanden? Werkzeug erfolgreich?)
                        └─ 8. Speicherung       → brain/ (nur nach Regeln; Quelle + Zeitstempel)
```

### Paketstruktur (tatsächlich vorhanden)

```
main.py                         Start: Fenster | --cli | --diagnose
cudi/
├── config/settings.py          Einstellungen (Standard → config/settings.json → .env/Umgebung)
├── config/logging_config.py    logs/cudi.log
├── core/application.py         baut alles zusammen (eine DB, ein Orchestrator); get_app()
├── core/orchestrator.py        Ablaufsteuerung, Werkzeugschleife, Freigaben, Qualitätsprüfung
├── core/intent_router.py       eindeutige Anliegen (Befehle, merken, Feedback, ja/nein), DE/EN
├── core/permissions.py         Stufen 1–5, Sitzungsfreigaben
├── core/persona.py             System-Prompt (Jarvis-artiger Kollege)
├── core/results.py             Result/Action – einheitliche Rückgabe an GUI/CLI
├── brain/database.py           SQLite + Schema-Version + FTS5 + Sicherung/Wiederherstellung
├── brain/memory.py             Langzeitgedächtnis (Status, Quelle, Duplikate, Widersprüche)
├── brain/conversation.py       Gesprächsverlauf (DB) + Arbeitsgedächtnis (RAM)
├── brain/projects.py           Projektgedächtnis + Aufgaben
├── brain/knowledge.py          Dokumentimport (PDF/DOCX/TXT/MD/JSON/CSV) + Suche mit Fundstellen
├── brain/episodes.py           Verlaufsprotokoll, Feedback, Modellaufrufe, Fehler-Hinweise
├── brain/context_builder.py    Kontext pro Anfrage
├── models/base.py              Schnittstelle ModelProvider, ModelResponse, ToolCall
├── models/model_manager.py     Reihenfolge, Ausweichen, Protokoll, Einrichtungshinweis
├── models/ollama_provider.py   lokal
├── models/anthropic_provider.py Claude (offizielle SDK)
├── models/openai_provider.py   OpenAI (HTTP)
├── tools/registry.py           Werkzeugregistrierung, Validierung, Protokoll
├── tools/file_tools.py         list_files, read_file, write_file
├── tools/memory_tools.py       remember, search_memory, replace_memory, forget_memory
├── tools/project_tools.py      Projekte, Einträge, Aufgaben
├── tools/document_tools.py     import_document, import_folder, search_documents, list_documents
├── tools/system_tools.py       Diagnose, Sicherung, Wiederherstellung, Export, Altbestand
├── diagnostics/health.py       Selbstdiagnose
└── cli.py                      Terminal-Chat
ui/brain_dialog.py              Fenster „Digitales Gehirn“ (echte Daten)
cudi_supreme_gui.py             bestehende Oberfläche; Chat → Orchestrator
tests/                          49 Tests (Abnahmetests A–K u. a.), ohne GUI/Netzwerk lauffähig
```

Laufzeitordner (nicht versioniert): `data/` (Datenbank, Sicherungen, Exporte), `workspace/`
(hier schreibt CUDI Dateien), `import/` (Dokumente zum Einlesen), `logs/`.

### Neues Werkzeug hinzufügen

1. In einer Datei unter `cudi/tools/` eine Funktion schreiben, die `ToolOutput(ok, inhalt, summary)` liefert.
2. Mit `registry.register(Tool(name, beschreibung, parameter_schema, Level.X, funktion))` registrieren.
3. Die Datei in `cudi/core/application.py` in der Liste der Werkzeugmodule ergänzen.
4. Einen Test in `tests/` schreiben. Das Sprachmodell kennt das Werkzeug danach automatisch.

Agenten (Research, Document, Coding, Planning, Quality, Creative) werden zunächst **nicht** als eigene
Module angelegt, sondern entstehen in Phase 5 als Rollen (System-Prompt + erlaubte Werkzeuge) über
dem Orchestrator, sobald Werkzeuge und Modelle stabil sind.

### Kommunikationsregeln

* Abhängigkeiten zeigen nur nach innen: `ui → core → (brain, models, tools)`; `brain`, `models` und
  `tools` kennen weder `core` noch `ui` → keine zyklischen Importe.
* Die GUI führt lange Aufrufe in einem Worker-Thread aus und erhält Ergebnisse über Qt-Signale.
* Der vorhandene `cudi_event_bus` bleibt der Weg für Status-/Fortschrittsereignisse an die GUI.
* Dokumentinhalte und Webinhalte werden als **Daten** in den Prompt eingefügt (klar markiert),
  nie als Systemanweisung.
* Externe Modellanbieter erhalten nur Daten, wenn der Anbieter in den Einstellungen aktiviert ist;
  jede Antwort trägt die Herkunft (lokal/extern, Modellname).

---

## C. Zuordnung bestehender Komponenten → Zielmodul

Stand 2026-10-26: Umgesetzt sind die Zeilen für Chat/Intent/Aktionen (Orchestrator), Kommunikations-Engine
(Model Manager), `cudi_brain.py`-Gedächtnis (neues Gedächtnis), Wissensspeicher (eine DB + `/altwissen`),
Selbstheilung (Diagnose). Archivieren alter Dateien und das Umstellen der alten Knöpfe sind noch offen
(Vorschlag V8, nur nach Zustimmung).

| Bestehend | Ziel | Vorgehen |
|---|---|---|
| `cudi_supreme_gui.py` (Layout, Chat, Theme) | `ui/` | **behalten**, Logik schrittweise auslagern; Chat ruft Orchestrator |
| `CUDISupremeMainWindow`-Intent-/Aktionsmethoden | `core/intent_router.py`, `tools/` | ersetzen (nach Zustimmung, siehe Plan) |
| `AdvancedCommunicationEngine` | `models/model_manager.py` + `providers.py` | überführen, Modellnamen konfigurierbar |
| `cudi_conversation_handler.py`, `cudi_direct_action.py` | `core/intent_router.py` | ersetzen; alte Dateien archivieren erst nach Zustimmung |
| `cudi_command_router.py` (`/file`, `/learn` …) | `core/intent_router.py` (Slash-Befehle) + `tools/` | Befehlssyntax übernehmen, Ausführung über echte Werkzeuge |
| `cudi_brain.py` `LongTermMemory`/`WorkingMemory` | `brain/memory.py`, `brain/working_memory.py` | Schema-Ideen übernehmen, neu implementieren |
| `cudi_brain.py` `SystemInterface` | `core/permissions.py`, `tools/file_tools.py` | Idee übernehmen |
| `cudi_brain.py` Emotion/Metakognition | – | vorerst unverändert lassen, nicht im neuen Pfad |
| `cudi_brain_memory.db`, `cudi_learning.db` | `cudi_brain.db` | leer → keine Migration nötig, Dateien bleiben erhalten |
| `config/knowledge_base.json` (Laufzeit) | `brain/knowledge.py` | Import-Migration (Quelle „alt, unbestätigt“) |
| Backup `cudi_autonomous_knowledge.db` (40 Einträge) | `brain/knowledge.py` | optionaler Import nach Rückfrage (Status „unbestätigt“) |
| `cudi_event_bus.py`, `cudi_telemetry.py` | bleiben | behalten |
| `cudi_component_bridge.py` | – | nicht mehr nötig, sobald Orchestrator existiert |
| Selbstheilung in der GUI, `cudi_self_healing_addon.py` (PyQt5) | `diagnostics/health.py` | ersetzen durch ehrliche Diagnose |
| `cudi_unified_cloud_system.py` (simuliert) | später eigenes Sync-Modul | deaktiviert lassen, in GUI als „nicht verfügbar“ zeigen |
| `simple_plugin_manager*.py`, `plugins/` | `plugins/` + `tools/registry.py` | Plugins als Werkzeuge registrierbar machen |
| `cudi_perfect_harmonizer.py`, `cudi_system_harmonizer.py`, `cleanup_workspace.py` | – | **nicht mehr ausführen** (schreiben Quellcode um / verschieben Dateien); archivieren nach Zustimmung |
| Mehrere Starter | ein `main.py` | bestehende Starter bleiben, verweisen später auf `main.py` |
