# CLAUDE.md – Arbeitswissen für dieses Repository

Antworte auf Deutsch. Arbeite ziel- und lösungsorientiert, vorausschauend und **sparsam**: so wenig
Werkzeugaufrufe, Ausgaben und Tests wie nötig, aber gründlich genug, dass nichts kaputtgeht. Führe
eine einzige Gesamt-To-do-Liste und erweitere sie nur, wenn echte Unterpunkte entstehen.

## Was das Projekt ist

Neben dem älteren Desktop-Assistenten (README.md, `main.py`, `ui/`) enthält das Repo **CUDI Video**
(`cudi_video/`, Doku: README_VIDEO.md): kostenlose Hochformat-Videos (1080×1920, ≤ 179 s, DE + EN)
für TikTok/YouTube Shorts.

- **Ranking-Faktenvideos**: Wikidata (neuester Wert je Objekt vor dem LIMIT) → Abgleich mit Weltbank,
  CIA Factbook, OSM, Wikipedia in 8 Sprachen (`cudi_video/verify/`) → Skript nur aus geprüften Zahlen →
  Infografik-Render + edge-tts. Grundsatz: **nichts erfinden**, widersprochene Werte fliegen raus.
- **Reddit-Storys** (`cudi_video/story/`): Suche per Stimmung/Beschreibung/Link (Arctic-Shift-Archiv),
  Lektorat (heikle Stellen umschreiben statt weglassen), Skelett, Bilder/Clips, Stimme je Stimmung.
- Später geplant: Story-Skelett in der App anpassen, längere Videos, Cartoon-Figuren.

## Bedienung

- CLI: `python -m cudi_video make <vorlage|thema>`, `python -m cudi_video story "<wunsch>"`,
  `python -m cudi_video web` (Web-App), `python -m cudi_video check` (Selbsttest).
- **CUDI-App in Claude** (Artefakt https://claude.ai/artifact/DYdRsKcD3BCN3SYxj6Y5Jt, Quelltext
  `docs/cudi-app-artefakt.html`): Der Nutzer bedient alles vom Handy, ohne Weiterleitung.
  - Start: Die Seite ruft über den eingebauten Connector „Claude Code Remote“ `create_session` auf
    (Umgebung `env_01UiNEwj42QRf8mr6x3CNjHj` „Standard“, Repo-Zweig `main`, Modell **Haiku**, Rechte
    `auto`, Tag `cudi-auftrag`). Die Arbeitsanweisung steht im Block `#jobPrompt` der Seite.
  - Die Auftrags-Sitzung führt `bash scripts/cudi_auftrag.sh '<json>'` aus (`cudi_video/job.py`):
    rendern, App-Fassung ≤ 19 MB, `ergebnis.json`. Englische Story für deutsches Video →
    `UEBERSETZEN:` → Claude übersetzt → `--weiter <id>`. Dann Upload per Artifact-Werkzeug
    (`asset: true`), `auftrag --dokument`, `ArtifactData set` in `results/<id>`.
  - Ablage der Seite: `jobs/<id>` (von der Seite), `results/<id>` (von der Sitzung), Videos als Assets
    (1 GB). Die Seite zeigt Fortschritt (`get_session`), Video, „Video speichern“ (downloads),
    Kopier-Knöpfe, Löschen; fertige Sitzungen werden archiviert.
  - Seite ändern: Datei bearbeiten und mit dem Artifact-Werkzeug unter derselben URL veröffentlichen
    (äußerer HTML-Rahmen fehlt absichtlich – Claude setzt ihn).
- Weitere Wege: GitHub Actions „CUDI Video“/„CUDI Story“, Issue mit `cudi-auftrag` („CUDI Auftrag“),
  Hugging Face Space („CUDI Cloud-App“, optional, braucht Secret HF_TOKEN).
- Kosten: alles kostenlose Dienste; App-Aufträge zählen nur zum Claude-Nutzungslimit des Nutzers.

## Entwickeln

- Tests: `python -m pytest tests -q` (lokal ~15 s; GitHub-Workflow „Tests“ installiert ffmpeg).
- Ausgaben nur in `video_output/` (gitignored); Arbeitsdateien in `video_output/_work/`.
- Commits auf Deutsch, Push auf den eigenen Zweig; PRs nur auf Wunsch, Merge nur mit OK des Nutzers.
- Stolperfallen: kein `pkill -f <muster>`, wenn das Muster im selben Befehl steht (beendet die eigene
  Shell) – PIDs verwenden. Wikidata-SPARQL: Blazegraph sieht OPTIONAL-Variablen in `NOT EXISTS` nicht
  zuverlässig (eigenen Stichtag dort neu binden). Pollinations nur nacheinander (sonst 402).
