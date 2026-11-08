---
name: neue-videoart
description: Neue Videoart (wie Reportage, Satire, Erklärvideo) in CUDI Video anlegen, ohne render/* anzufassen – Auftragsweg, Prüfungen, eigener Look, Ideen-Bereich, Tests.
---
# Neue Videoart anlegen

1. Unterpaket `cudi_video/<art>/` mit `__init__.py` (Regeln, Prüfungen, Quellen, `run`) und `render.py` (eigene Szenenklassen + `render_part`); vorhandene Bausteine importieren: `erklaer.render.build_audio`, `render/cover.stamp_first_frame`, `reportage.pruefe_satz`/`seite_quelle`, `wahrheit.Pruefer`.
2. Texte: Schreibaufgabe `<art>` über `handoff` (Claude in der App, Gemini im Notbetrieb) + Regel-Fassung ohne Modell; jeder Modelltext durch die Prüfregeln, sonst Regel-Fassung, sonst ehrlicher Abbruch.
3. Auftrag: `job.parse_order` (`art: "<art>"`) → `_<art>`-Runner im Dispatch von `job.py` → Abnahme-Dict in `files["abnahme"]`.
4. Stimme: Profil in `tts.SPEECH_PROFILES`; Musikstil über vorhandene Parameter.
5. Ideen: Bereich in `firma/ideen.py` (AREAS, Prompt, `finish`), heikle Themen → Reportage.
6. Tests ohne Netz + ein Probelauf; Bilderbogen-Standbilder zeigen bei Wort-für-Wort-Einblendung Teilsätze – das ist kein Abschneiden.
7. Doku: README_VIDEO.md-Abschnitt, CLAUDE.md eine Zeile; App-Tab über Agent `app-gestalter`.
Bekannt: edge-tts fällt in der Cloud manchmal aus → Piper-Ausweichweg; Notbetrieb-Modell (Gemini) liefert bei vielen Läufen 429.
