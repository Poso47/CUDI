# Implementierungsplan

Jeder Schritt endet mit einem überprüfbaren Ergebnis. Grundlage: `project_status.md`,
`architecture.md`, `decisions.md`, `known_issues.md`.

## Erledigt

| Phase | Ergebnis | Nachweis |
|---|---|---|
| 1 Bestandsaufnahme | Ist-Zustand, Fehlerursachen | `project_status.md` §6, `known_issues.md` |
| 2 Zielarchitektur | Architektur, Zuordnung, Entscheidungen | `architecture.md`, `decisions.md` |
| 3 Gemeinsamer Kern | Start (`main.py`), Einstellungen, Logging, Fehlerbehandlung, Model Manager, Intent-Erkennung, Orchestrator, Werkzeugregistrierung, Berechtigungen, einheitliche Speicherzugriffe | `tests/` (55 grün) |
| 4 Digitales Gehirn | Arbeits-, Langzeit-, Projektgedächtnis, Wissen/Dokumente, Suche, Fundstellen, Feedback, Verlaufsprotokoll, kontrollierte Aktualisierung, Sicherung | Tests A–K |
| 6 Oberfläche | Neues Hauptfenster mit allen Bereichen aus Abschnitt 14 (inkl. Einstellungen), Freigabe-Dialog, ehrliche Statusanzeige; alte Oberfläche als `--alt` | `tests/test_ui.py`, Bildschirmfotos |
| 7 Diagnose (Teil) | `/status`, `python main.py --diagnose` | Test G |

## Offene Entscheidungen des Nutzers

| ID | Frage | Stand |
|---|---|---|
| E-1 | Chat über den neuen Kern statt alter Logik? | ✅ freigegeben am 2026-10-26 („so wie ich es gesagt habe“) |
| F-1 | Welches Sprachmodell? | offen – Standard: lokal (Ollama) zuerst, dann Claude, dann OpenAI; Einrichtung siehe `user_guide.md` |
| F-2 | Gibt es das „Digitale Gehirn“ als separates Projekt? | offen – im Repository nicht vorhanden |
| F-3 | Altes Wissen (40 Einträge) übernehmen? | als Befehl `/altwissen` bereit (übernimmt nur nach Freigabe, Status „vorläufig“) |

## Verbesserungsvorschläge (warten auf deine Freigabe)

Reihenfolge = meine Empfehlung. Jeder Vorschlag wird erst nach „Ja“ umgesetzt.

| Nr. | Vorschlag | Nutzen | Aufwand | Hinweise |
|---|---|---|---|---|
| V1 | **Sprachsteuerung** („Hey CUDI“, Spracheingabe, Sprachausgabe) | echtes Jarvis-Gefühl, freihändig | mittel | offline möglich (z. B. Vosk/Whisper lokal + Piper/pyttsx3); Mikrofon nur nach Aktivierung |
| V2 | **Websuche mit Quellen** (Recherche-Werkzeug) | aktuelle Informationen, Fakten prüfen | klein–mittel | sendet Suchbegriffe an einen externen Dienst → Stufe 5 oder Einstellung „erlaubt“ |
| V3 | **Code ausführen & Tests starten** (abgesichert, nur im Arbeitsordner, mit Freigabe) | Coding-Kollege, der Ergebnisse selbst prüft | mittel | Zeitlimit, kein Netzwerk, Ausgabe wird angezeigt |
| V4 | **Tagesstart-Briefing** beim Öffnen (offene Aufgaben, Projektstand, nächste Schritte) | proaktiv wie Jarvis | klein | nutzt vorhandenes Projektgedächtnis |
| V5 | **Antworten erscheinen Wort für Wort** (Streaming) | wirkt schneller und natürlicher | klein–mittel | |
| V6 | **Semantische Suche** (lokale Embeddings über Ollama) | findet Wissen auch bei anderen Formulierungen | mittel | optional, gleiche Datenbank |
| V7 | **Agenten-Rollen** Research/Document/Coding/Planning/Quality mit Qualitätsprüfung vor der Ausgabe | bessere Ergebnisse bei großen Aufgaben | mittel | baut auf V2/V3 auf |
| V8 | **Altlasten aufräumen**: alte Knöpfe auf den neuen Kern umstellen oder als „nicht verfügbar“ markieren; alte Vorlagen-/Selbstheilungslogik und Harmonizer-Skripte in ein Archiv verschieben | Oberfläche zeigt nur noch Echtes (KI-16), GUI-Datei wird übersichtlich | mittel | **entfernt bestehende Funktionen → braucht deine Zustimmung** |
| V9 | **E-Mail & Kalender** (Outlook/Google) | Termine, Mails vorbereiten | mittel–groß | Senden nur nach Einzelfreigabe (Stufe 5) |
| V10 | ~~Einstellungsfenster~~ – **erledigt** als Bereich „⚙️ Einstellungen“ im neuen Hauptfenster | | | |
| V11 | **Kreativ-/Videostudio** (Phase 8: Skript → Storyboard → Timeline → Render-Anbieter) | Produktionsworkflows | groß | erst nach V1–V7 |
| V12 | **Verschlüsselte Synchronisierung** zwischen deinen Geräten | gleiches Gehirn überall | groß | eigenes Sicherheitskonzept nötig |

## Nächster sinnvoller Schritt

1. Ein Sprachmodell anschließen (F-1) – erst dann kann CUDI frei antworten und Werkzeuge selbst wählen.
   Empfehlung: Ollama lokal (kostenlos, Daten bleiben auf dem Rechner) oder Claude (beste Qualität).
2. Danach V4 (Briefing) und V5 (Streaming) als schnelle Gewinne, dann V1 (Sprache).
