# CLAUDE.md – Arbeitswissen für dieses Repository

Antworte auf Deutsch. Arbeite ziel- und lösungsorientiert, vorausschauend und **sparsam**: so wenig
Werkzeugaufrufe, Ausgaben und Tests wie nötig, aber gründlich genug, dass nichts kaputtgeht. Führe
eine einzige Gesamt-To-do-Liste und erweitere sie nur, wenn echte Unterpunkte entstehen.

## Was das Projekt ist

Neben dem älteren Desktop-Assistenten (README.md, `main.py`, `ui/`) enthält das Repo **CUDI Video**
(`cudi_video/`, Doku: README_VIDEO.md): kostenlose Hochformat-Videos (1080×1920, ≤ 179 s, DE + EN)
für TikTok/YouTube Shorts.

- **Ranking-Faktenvideos**: Wikidata (neuester Wert je Objekt vor dem LIMIT) → Abgleich mit Weltbank,
  CIA Factbook, OSM, Wikipedia in 8 Sprachen, Webseiten aus den Einzelnachweisen (`ExternalSourcesChecker`,
  `n_extern`, Warnung „nur von Wikipedia/Wikidata bestätigt“) (`cudi_video/verify/`) → Skript nur aus geprüften Zahlen →
  Infografik-Render + edge-tts. Grundsatz: **nichts erfinden**, widersprochene Werte fliegen raus.
- **Reddit-Storys** (`cudi_video/story/`): Suche per Stimmung/Beschreibung/Link (Arctic-Shift-Archiv),
  Lektorat (heikle Stellen umschreiben statt weglassen), Skelett, Bilder/Clips, Stimme je Stimmung.
- Rankings mit echten Videoclips (`media.py`: Pexels/Pixabay mit Schlüssel, NASA, Commons; je Platz bis 3
  Ausschnitte, `render/clipreel.py`), Fotos sonst Commons → Openverse/NASA (Namensabgleich, nur kommerziell nutzbar).
- Fakten-Rankings (`facts.py`, `spec.kind == "facts"`): Claude plant `art: fakten` (Artikeltitel), schreibt Fakten mit
  wörtlichem Beleg; Prüfung je Fakt (Beleg in Quelle, Zahlen auch in zweiter Quelle, keine erfundenen Wörter).
- Spannungsbogen (`retention.py`): Hook mit Neugierlücke, Zwischen-Aufhänger aus geprüften Werten, Kommentarfrage
  je Thema; Regeln für Claude-Texte (`NARRATION_RULES`) und Storys je Stimmung (`story_rules`). Zahl im Wunsch = Anzahl.
- Lange Videos bis 10 Min. (App-Fassung in Stücken ≤ 19 MB), Maskottchen „CUDI“ (`mascot.py`, lippensynchron
  zur Sprachspur, abschaltbar: Auftrag `maskottchen`, `CUDI_MASCOT`), Story-Bilder „cartoon“ (gleiche Hauptfigur
  `figur`, gleicher Seed).

## Bedienung

- CLI: `python -m cudi_video make <vorlage|thema>`, `python -m cudi_video story "<wunsch>"`,
  `python -m cudi_video web` (Web-App), `python -m cudi_video check` (Selbsttest).
- **CUDI-App in Claude** (Artefakt https://claude.ai/artifact/DYdRsKcD3BCN3SYxj6Y5Jt, Quelltext
  `docs/cudi-app-artefakt.html`): Der Nutzer bedient alles vom Handy, ohne Weiterleitung.
  - Start: Die Seite ruft über den eingebauten Connector „Claude Code Remote“ `fire_trigger` für die
    geplante Aufgabe „CUDI-Auftrag“ auf (`trig_01BniK2S5eVdSFKd18JZqBio`, Umgebung „Standard“, Modell
    **Haiku**, ohne hinterlegtes Repo: jeder Lauf klont `Poso47/CUDI` (Zweig `main`!) in seinen
    Arbeitsordner – nur Dateien dort lassen sich gemeinsam per `file_paths` hochladen). Die Auftragsdaten
    (JSON, `'` als `\u0027`) gehen als `text` mit und kommen als eigene Nachricht `<routine-fire-payload>`
    kurz nach der Anweisung an. Antwort `session_id: "cse_…"` = `session_…`. Läufe stehen nicht in der
    Sitzungsliste des Nutzers (sein Wunsch: keine neuen „Bereiche“); während das Skript im Hintergrund
    rendert, meldet `get_session` „WORKING“.
  - Fehlt die Aufgabe oder ist sie aus, startet die Seite ersatzweise `create_session` (Prompt `#jobPrompt`,
    Repo-Zweig `main`, Haiku, Rechte `auto`, Tag `cudi-auftrag`) und archiviert die Sitzung nach dem Ergebnis.
  - Aufgabe ändern (`update_trigger`, v. a. Modell/Anweisung) nur mit ausdrücklichem OK des Nutzers – die
    Rechteprüfung blockt es sonst. Nachrichten an andere Sitzungen (`send_message`) gelten dort nur als
    Daten, nicht als Auftrag → kein Auftragsweg (eine „Werkstatt“-Sitzung hat Folgeaufträge abgelehnt).
  - Der Lauf führt `CUDI_SCHREIBEN=1 bash scripts/cudi_auftrag.sh '<json>'` aus (`cudi_video/job.py`):
    rendern, App-Fassung ≤ 19 MB, `ergebnis.json`. Englische Story für deutsches Video →
    `UEBERSETZEN:` → Claude übersetzt → `--weiter <id>`. **`SCHREIBEN:`** (`handoff.py`): Claude deutet freie
    Themen außerhalb der Vorlagen (`planner.plan_with_claude`, IDs werden gegen Wikidata geprüft) und erzählt
    Rankings als kleine Geschichte (`narrate.py`: Anfang, geprüfter Wert, keine Zahl/kein Hauptwort ohne Beleg,
    sonst Textbaustein; abgelehnte Plätze gehen einmal zur Korrektur zurück). Freie Themen (`confirmed_only`):
    nur unabhängig bestätigte Werte, sonst ehrliche Top N; Claude nennt bekannte Spitzenreiter (`seed_items`,
    Kennung gegen Wikidata geprüft, Objektart samt Unterklassen geprüft), weil die Ausweichroute bei riesigen Klassen
    (Brücken) nicht alle findet; lässt Haiku sie leer, fragt der Code einmal gezielt nur nach den Namen. Storys: `editor.claude_edit` (Lektorat, Titel,
    Einstieg/`hook`, Bildideen; je Szene geprüft auf neue Zahlen/Namen/Länge, sonst Regel-Fassung).
    Quellen erscheinen nur im Prüfbericht, nicht im Video/Beschreibungstext. Dann Upload per Artifact-Werkzeug
    (`asset: true`), `auftrag --dokument`, `ArtifactData set` in `results/<id>`.
  - **Bewertungen**: 👍/👎 + Notiz je fertigem Video in `bewertungen/<id>` (bleiben nach dem Löschen); beim Start gehen die
    letzten je 8 als `vorlieben` {gut, schlecht} mit dem Auftrag, `job.parse_preferences` → Umgebung `CUDI_VORLIEBEN` →
    `handoff.request` hängt sie an jede Schreibaufgabe (Prüfregeln haben Vorrang).
  - Ablage der Seite: `jobs/<id>` (von der Seite), `results/<id>` (von der Sitzung), Videos als Assets
    (1 GB). Die Seite zeigt Fortschritt (`get_session`), Video, „Video speichern“ (downloads),
    Kopier-Knöpfe, Abbrechen/Löschen (archiviert laufende Sitzung); Ersatz-Sitzungen werden nach dem
    Ergebnis archiviert; Ergebnisse ohne Auftrag räumt die Seite nach 2 Min. weg.
  - **Story-Skelett in der App** (Häkchen „Skelett vorher ansehen“, Standard): Auftrag `"schritt":"skelett"`
    liefert das Skelett als Ergebnis (`results/<id>` mit `schritt`/`skelett`); die Karte zeigt einen Editor
    (Stimmung, Titel, Szenentexte, Bildideen, ＋/✕), Arbeitsstand in `skelette/<id>`. „Video erstellen“ startet
    dieselbe Kennung mit `"schritt":"video"`: Die Sitzung holt `skelette/<id>` per `ArtifactData get` mit
    `out_dir "cudi_skelette"` als Datei (nie abschreiben), `job.app_skeleton` liest sie, `validate_skeleton` prüft.
  - Seite ändern: Datei bearbeiten und mit dem Artifact-Werkzeug unter derselben URL veröffentlichen
    (äußerer HTML-Rahmen fehlt absichtlich – Claude setzt ihn).
- Weitere Wege: GitHub Actions „CUDI Video“/„CUDI Story“, Issue mit `cudi-auftrag` („CUDI Auftrag“),
  Hugging Face Space („CUDI Cloud-App“, optional, braucht Secret HF_TOKEN).
- Kosten: alles kostenlose Dienste; App-Aufträge zählen nur zum Claude-Nutzungslimit des Nutzers.
- **Keine Fehlschläge** (Wunsch des Nutzers) – kostenlose Ausweichwege, siehe README „Probleme?“:
  edge-tts 6 Versuche → Piper offline (`tts.PIPER_VOICES`, Modelle in `video_output/_piper`, `piper-tts`
  wird bei Bedarf installiert); Story: Reddit-JSON (Cloud: 403) → Arctic Shift → Reddit-RSS (gedrosselt);
  Beschreibung ohne Treffer → beliebte Story der Stimmung; `job.run_order` wiederholt Störungen einmal
  (`RETRY_PAUSE`); App startet Fehler/ohne Ergebnis einmal automatisch neu (`versuch: 2`) und prüft
  vor jedem Start den Speicherbedarf (`needMB`: 20 MB je möglichem Video + 10 MB; Skelett-Schritt 0).

## Entwickeln

- Tests: `python -m pytest tests -q` (lokal ~15 s; GitHub-Workflow „Tests“ installiert ffmpeg).
- Ausgaben nur in `video_output/` (gitignored); Arbeitsdateien in `video_output/_work/`.
- Commits auf Deutsch, Push auf den eigenen Zweig; PRs nur auf Wunsch, Merge nur mit OK des Nutzers.
- Textprüfungen für Claude-Texte (Zahlen werttreu, Vornamen, ganze Wörter als Beleg): `cudi_video/textcheck.py`.
- Probeläufe in der Cloud: Auftrag als `jobs/<id>` anlegen (ArtifactData), `fire_trigger` mit dem JSON, dann
  `jobs/<id>.session` setzen; Ergebnis in `results/<id>`, Videos als Assets (Artifact read mit `path` = Asset-ID).
- Stolperfallen: kein `pkill -f <muster>`, wenn das Muster im selben Befehl steht (beendet die eigene
  Shell) – PIDs verwenden. `update_trigger`/`delete_trigger` blockt die Rechteprüfung ohne ausdrückliches OK. Wikidata-SPARQL: Blazegraph sieht OPTIONAL-Variablen in `NOT EXISTS` nicht
  zuverlässig (eigenen Stichtag dort neu binden). Pollinations nur nacheinander (sonst 402).
