---
name: firma-mitarbeiter
description: Neuen Firma-Mitarbeiter (GitHub-Workflow, kein Claude-Verbrauch) bauen oder einen bestehenden reparieren – Trend-Scout, News, Ideen, Welt-Blick, Briefing usw. Nutzen bei Arbeit an cudi_video/firma/ oder .github/workflows/firma-*.yml.
---
# Firma-Mitarbeiter bauen/reparieren

## Bauen (Checkliste)
1. Modul `cudi_video/firma/<name>.py` mit `run() -> dict`; jede Quelle einzeln in try/except, Ausfall = Eintrag in `hinweise`.
2. Ergebnis über `common.write_json("<name>.json", data)` (schreibt nur bei echter Änderung), am Ende `common.record_status("<name>", started, ok, zusammenfassung, hinweise)`.
3. Eintragen: `common.WORKERS` (Name, Takt in Stunden), `firma/__main__.py` (names), `firma/export.py` (kompakter Auszug für die App).
4. Workflow `.github/workflows/firma-<name>.yml` nach Vorlage `firma-news.yml`: `concurrency: {group: firma-daten, cancel-in-progress: false}`, `permissions: contents: write`, pip nur was gebraucht wird (Ranking-Vorprüfung braucht `pillow`), Speichern mit **`bash scripts/firma_commit.sh "<Anzeigename>"`** (immer mit `bash`, Datei ist nicht ausführbar gewesen).
5. Tests ohne Netz (monkeypatch) in `tests/test_firma.py`; Testdaten-Kandidaten brauchen alle Pflichtfelder (z. B. `warum`).
6. CLAUDE.md-Abschnitt „Firma-Mitarbeiter“ um eine Zeile ergänzen.

## Starten/prüfen
- Manuell: `actions_run_trigger run_workflow` (ref main). **Höchstens 2 Läufe gleichzeitig** in der Gruppe firma-daten – weitere wartende Läufe bricht GitHub ab („cancelled“).
- Läufe starten auf dem Stand beim Auslösen; `firma_commit.sh` sichert eigene Dateien, setzt auf origin/main und führt `status.json` zusammen – Konflikte sind damit erledigt.
- Fehler: `get_job_logs failed_only, tail_lines 40`. Bekannte Ursachen: `Permission denied` (ohne bash aufgerufen), `No module named …` (pip-Zeile), Rebase-Konflikt (alte firma_commit.sh).
- Ergebnis lesen: `git fetch origin main && git show origin/main:firma_daten/<name>.json`.

## Qualität
- Nachrichten: „bestätigt“ nur bei ≥ 2 unabhängigen Betreibern; Ähnlichkeit **paarweise** mit einzelnen Meldungen, nie mit wachsender Wortmenge der Gruppe.
- Ideen: keine Meta-Rankings (Klicks/Suchbegriffe), Nachrichten nie als Story → Reportage; alte Ideen über `still_valid` nachprüfen.
