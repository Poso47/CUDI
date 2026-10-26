# Architektur CUDI + Digitales Gehirn

Dieses Dokument beschreibt (A) die **Ist-Architektur**, wie sie im Code tatsächlich vorliegt, und
(B) die **Zielarchitektur**, auf die schrittweise migriert wird. Abschnitt C ordnet jede vorhandene
Komponente ihrem Zielmodul zu.

---

## A. Ist-Architektur (Stand 2026-10-26)

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

## B. Zielarchitektur

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

### Geplante Paketstruktur (nur Module mit konkretem Zweck)

```
cudi/
├── config/settings.py         Einheitliche Einstellungen (config/settings.json + Umgebungsvariablen)
├── config/logging_config.py   Ein Logging für alle Module (Datei + Konsole)
├── core/orchestrator.py       Zentrale Ablaufsteuerung (Schritte 1–8)
├── core/intent_router.py      Absicht + Parameter erkennen (DE/EN)
├── core/permissions.py        Berechtigungsstufen, Bestätigungen
├── core/results.py            Einheitliches Ergebnisobjekt (ok / Fehler / Rückfrage / Bestätigung nötig)
├── brain/database.py          EINE SQLite-Datenbank (cudi_brain.db) inkl. Schema-Version + Migrationen
├── brain/memory.py            Langzeit-, episodisches Gedächtnis; Status bestätigt/vorläufig/veraltet
├── brain/working_memory.py    Arbeitskontext der laufenden Unterhaltung
├── brain/projects.py          Projektgedächtnis (Ziele, Entscheidungen, offene Punkte, nächste Schritte)
├── brain/knowledge.py         Dokumente + Abschnitte, SQLite-FTS5-Volltextsuche, Fundstellen
├── brain/context_builder.py   Relevanten Kontext für eine Anfrage zusammenstellen
├── models/model_manager.py    Anbieter-unabhängige Schnittstelle, Ausweichstrategie, Laufzeit/Token
├── models/providers.py        Ollama (lokal), Anthropic, OpenAI – nur wenn konfiguriert
├── tools/registry.py          Werkzeugregistrierung (Name, Beschreibung, Parameter, Stufe, Prüfung)
├── tools/file_tools.py        Dateien lesen/auflisten/schreiben (nur im freigegebenen Arbeitsordner)
├── tools/document_tools.py    Import PDF/DOCX/TXT/MD/JSON/CSV
├── tools/memory_tools.py      Merken, Erinnern, Vergessen, Korrigieren
└── diagnostics/health.py      Selbstdiagnose (kritisch / Warnung / optional)
tests/                         pytest, ohne GUI lauffähig; Abnahmetests A–K
```

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
