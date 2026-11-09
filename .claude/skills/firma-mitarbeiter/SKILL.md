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

## Lokal testen / Quellen prüfen
- `cp firma_daten/*.json video_output/_work/firma/ && CUDI_FIRMA_DATEN=video_output/_work/firma python -m cudi_video.firma <name>` – `firma_daten/` nie lokal committen.
- RSS prüfen: `curl -sL -m 15 -A 'CUDI-Firma/1.0' -o /dev/null -w '%{http_code} %{size_download}' <url>` (404 mit großer Antwort = Fehlerseite). Nicht nutzbar (Stand 11/2026): TRT World, ORF-RSS (RDF, 0 Einträge), Antara, Jakarta Post, News24, ABC Paraguay.
- GDELT: höchstens 1 Abruf je 5 s, oft 429 → immer einzeln absichern; `artlist` hat keinen Ton (`mode=tonechart` nötig).
- Wikidata: `wbsearchentities` + `wbgetentities`, 1,5 s Pause, ≤ 5 neue Namen je Lauf, negative Treffer cachen. abgeordnetenwatch v2 geht ohne Schlüssel (`last_name`), noch nicht eingebaut.
- Sprachübergreifender Abgleich nur über Eigennamen/Zahlen (≥ 2 gemeinsame).
- Sprachmodell-Texte: `textcheck.numbers`, `invented_people`, keine Links, keine Interna (`briefing.INTERNA`); Firma-Interna nie ins Sprachmodell geben.
- Nie `git checkout -- .` im Hauptordner (verwirft ungesicherte Arbeit eines Agenten).
- Meldungen gruppieren: zusätzlich zur Wortähnlichkeit **gemeinsamer Eigenname nötig** (`news.names`) – sonst landen „sentenced … years in prison“ aus Kenia/Tansania/Hongkong in einer Gruppe.
- Workflows, die Daten anderer Mitarbeiter lesen (Ideen, Briefing): vor dem Lauf `git pull --ff-only` – der Checkout ist sonst der Stand beim Auslösen.
- Wikidata-Verbindungen ohne Enddatum nie als „aktuell“ darstellen: „kein Enddatum eingetragen – ob noch aktuell, ist offen“.

## Eigentümer/Unabhängigkeit
- `cudi_video/eigentuemer.py`: `eigentuemer(domain)`, `unabhaengig(a, b)`, `pruefe(a, b)` (mit Grund), `gruppiere(items)`. „Bestätigt“ = ≥ 2 **Gruppen**, nicht ≥ 2 Betreiber (gleicher Eigentümer/Geldgeber, Agentur, Staat, Domain zählt einmal; Ketten über `konzerne` in der Tabelle).
- Tabelle `cudi_video/data/medien_eigentuemer.json`: nur Belegtes mit Link; leere Eigentümerliste = „unbekannt“ (Lücke, nie raten). Neue Feeds in `news.FEEDS`/`welt.FEEDS` brauchen einen Eintrag (Test `test_tabelle_belegt_und_deckt_feeds`; der Feed-Host zählt, z. B. `bbci.co.uk`). `.gitignore` ignoriert `data/` – Ausnahme `!cudi_video/data/` steht drin.
- Wikidata nur über `query.wikidata.org/sparql` (VALUES mit URL-Varianten für P856); die `w/api.php` drosselt schnell (429). P856-Treffer sind oft falsche Objekte (bbc.co.uk → „London Sounds Eastern“): Tabelle hat Vorrang, Wikidata nur Ersatz mit Vermerk „laut Wikidata“; > 3 Treffer = mehrdeutig = unbekannt. Prüfliste neu: `eigentuemer.abgleich_tabelle(schreiben=True)` (~2 Min., Netz).
- Tests setzen `CUDI_EIGENTUEMER_WIKIDATA=0` (kein Netz). Python-Heredocs mit vielen Sonderzeichen blockt die Worktree-Prüfung: Skript als Datei schreiben und ausführen.
## Clip-Scout / Messung (Stand 11/2026)
- `clipscout.py` (6 h) + `messung.py` (täglich); Daten `clip_creators.json` (Nutzer), `clip_radar.json`, `clip_erlaubnis.json`, `messung.json`. Doku `docs/clip-team.md`.
- Regeln: Erlaubnis nur mit wörtlichem Zitat+Link+Datum (`decide`); Sperre gewinnt; Kampagne/schwacher Hinweis = „unklar“; leere Creator-Liste = ehrlich leer mit Hinweis, nie Creator erfinden.
- Workflows brauchen `pip install yt-dlp` und `git pull --ff-only`. Live geprüft: YouTube-@Handle-Auflösung (Kanalseite), Feed, contentrewards-Liste (robots.txt erlaubt `/c/discover`).
- Tests ohne Netz: `tests/test_clipteam.py` (Atom-Feed als Fixture).
