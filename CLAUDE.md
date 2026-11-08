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
  wörtlichem Beleg; Prüfung je Fakt (Beleg in Quelle, Zahlen auch in zweiter Quelle, keine erfundenen Wörter –
  deutsche Alltagswörter per `textcheck.everyday_word`), abgelehnte Fakten einmal zur Korrektur (`fakten_korrektur`).
- Themen-Wissensstruktur (`themen.py`, `spec.focus`): Planer liefert Themenkern/Aspekte/nicht gemeint; alle Schreib-
  aufgaben erzählen Aufhänger → Kernaussage → Erklärung → Bedeutung für dich; Fakten brauchen Aspekt, Mindestlänge, `belege`.
- Formate (`render/formats.py`: karte, vollbild, kreis, magazin, polaroid, zahl, manuskript – eigener Bildaufbau, Übergang,
  Intro, Abschluss) je Video; Farben (`theme.STYLES`) nach Thema (`palette_options`: Titelwörter/Icon); `pick_style`
  fest je Video-ID, `apply_style` in `make_scene` (jeder Render-Prozess); Auftrag `format`.
- **Manuskript/Erklärvideo**: Format `manuskript` (Buchlook, eigenes Design, Schriften EB Garamond/Amiri/Inter in
  `video_assets/fonts`, Bausteine `render/manuskript.py`, Linien-Grafiken `render/linien.py`; bringt immer Design
  „manuskript“ mit, keine Maskottchen). Videoart `cudi_video/erklaer/` (Szenen-Skript JSON, `python -m cudi_video erklaer
  <skript.json>`, Beispiel `examples/erklaer_goldener_schnitt.json`, Szenentyp `erklaer` im Format).
- Spannungsbogen (`retention.py`): Hook mit Neugierlücke, Zwischen-Aufhänger aus geprüften Werten, Kommentarfrage
  je Thema; Regeln für Claude-Texte (`NARRATION_RULES`) und Storys je Stimmung (`story_rules`). Zahl im Wunsch = Anzahl.
- Bildprüfung (`bildcheck.py`, CLIP ViT-B-32 CPU, Cache `video_output/_models`, 3 Bilder je Kandidat, ≥ 2/3 mit p ≥ 0.5; Ausfall → Tag-Abgleich;
  Ranking-Clips nur sortiert via `media.rank_by_image`; Tests setzen `CUDI_BILDPRUEFUNG=0`). Bildpassung (`facts.find_visuals`, `media.motif_matches`): Fakt-Feld `motiv` + `suche`-Liste; Treffer nur, wenn alle Kernwörter des
  Motivs in Beschreibung/Tags stehen (Clip → Foto → Commons → „Stimmungsbild“, im Prüfbericht vermerkt). Aha-Regel
  (`themen.AHA_RULES`, Fakt-Feld `aha_<sprache>`, geprüft in `facts.checked_aha`): Outro „Heute gelernt: …“ (Platz 1; Rankings: Spitzenwert).
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
  - **Bewertungen**: 👍/👎 wählen, Notiz optional, „Bestätigen“ → `bewertungen/<id>` (bleiben nach dem Löschen); 👍 behält
    das Video, 👎 löscht es samt Auftrag (`removeJob`); beim Start gehen die
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
  - **Bearbeiten/Freigabe** (`cudi_video/bearbeiten.py`, README_VIDEO.md): fertige Ranking-/Story-Karte → „Bearbeiten“ → `schritt:"bearbeiten"` (Datei `bearbeitungen/<id>` per `out_dir "cudi_bearbeitungen"`, rendert nur neu, Texte per `check_text` geprüft); `hochladen` bereitet nur vor (`freigabe` Standard true), „Veröffentlichen“ = `schritt:"hochladen"` (`cudi_hochladen`, kein Rendern). Geplante Aufgabe braucht dafür eine Zusatzzeile in Schritt 1 (nur mit OK des Nutzers ändern).
  - **Firma-Tab** (Leitstand, rein im Browser aus `jobs`/`results`/`bewertungen`, kein Claude-Aufruf): Aufträge als „Mitarbeiter“
    (Rolle nach Art: Rechercheur & Autor, Faktenprüfer = freies Thema, Story-Autor, Clipper); „Projektleiter“: hängt (> 40 Min. ohne
    Ergebnis oder `ohne`), halbe Arbeit (Ergebnis ohne Video/mit Fehler), „Neu starten“ = `restartJob` (gleiche Logik wie die Karte),
    bei freien Mitarbeitern 3 Vorschläge (Bewertung, neue Vorlage, Fakten-Idee) über `startJob`; Banner in jedem Tab.
  - Ansehen ohne Cloud: Seite mit `?demo=1` (Aufträge laufen) bzw. `?demo=frei` öffnen – Beispieldaten nur dann.
  - Seite ändern: Datei bearbeiten und mit dem Artifact-Werkzeug unter derselben URL veröffentlichen
    (äußerer HTML-Rahmen fehlt absichtlich – Claude setzt ihn).
- **Notbetrieb** (Claude-Limit erreicht; Doku `docs/notbetrieb-einrichten.md`): `handoff.request` fragt ohne `CUDI_SCHREIBEN` ein freies LLM (`CUDI_LLM_*`, Gemini; `handoff.active()`/`llm_mode()`, Antwort in `schreiben_<aufgabe>.json`, Fehler → None → Textbausteine); Web-App-Space nimmt App-Aufträge per `POST /api/auftrag` (`job.run_order(via_claude=False)`), Formular per URL vorbefüllbar; App-Seite zeigt Banner bei Limit-Fehlern (`config/notbetrieb` = Space-Adresse, `?demo=limit`).
- Upload (`cudi_video/upload/`: `youtube.py` resumable videos.insert, `tiktok.py` Inbox/Direct Post, `cli.py`): `hochladen … --probe`, `youtube-login`;
  Zugang nur über Umgebungsvariablen (`CUDI_YT_*`, `CUDI_TIKTOK_*`, nie ausgeben: `upload.redact`), Auftragsfeld `hochladen` (Standard aus), Doku `docs/upload-einrichten.md`.
- Betonung (`tts.py`, Tabelle `SPEECH_PROFILES` + `MOOD_STYLE`): Abschnitte werden in Teile mit eigenem Tempo/Tonhöhe/Lautstärke und
  Spannungspausen zusammengesetzt (`assemble_parts`, Wortzeiten wandern mit; Grundtempo `+0%`). Profil nach Videoart
  (`speech_profile(spec.kind)`): ranking (Pausen vor Platz/Zahl), fakten (Frage, Pause vor dem Aha, ruhiger Erklärteil), erklaer (ruhig,
  gleichmäßig), Story je Stimmung (`plan_story_parts`: Pause vor Wendung/Pointe). `CUDI_SPEECH_PROFILE=ranking|fakten|erklaer|aus` überschreibt.
- **Clip-Engine** (`cudi_video/clip/`, CLI `python -m cudi_video clip <datei|url>`, Doku README_VIDEO.md): Podcast-/Streamer-Clips
  1080×1920 (faster-whisper → Höhepunkt/Hook nach Regeln, optional Claude-Auswahl `clip_hook` über `handoff` → Pausenschnitt →
  Sprecher-Zuschnitt mit YuNet/Haar → ASS-Untertitel). App-Auftrag `art: "clip"` (`job._clip`): Pflichtfeld `bestaetigt_erlaubnis`,
  nur http(s)-Links, Texte/Prüfbericht in `clip/texte.py`; YouTube sperrt Cloud-IPs oft (`ClipError.wiederholbar`, Hinweis „später/PC“).
- Weitere Wege: GitHub Actions „CUDI Video“/„CUDI Story“, Issue mit `cudi-auftrag` („CUDI Auftrag“),
  Hugging Face Space („CUDI Cloud-App“, optional, braucht Secret HF_TOKEN).
- Kosten: alles kostenlose Dienste; App-Aufträge zählen nur zum Claude-Nutzungslimit des Nutzers.
- **Keine Fehlschläge** (Wunsch des Nutzers) – kostenlose Ausweichwege, siehe README „Probleme?“:
  edge-tts 6 Versuche → Piper offline (`tts.PIPER_VOICES`, Modelle in `video_output/_piper`, `piper-tts`
  wird bei Bedarf installiert); Story: Reddit-JSON (Cloud: 403) → Arctic Shift → Reddit-RSS (gedrosselt);
  Beschreibung ohne Treffer → beliebte Story der Stimmung; `job.run_order` wiederholt Störungen einmal
  (`RETRY_PAUSE`); App startet Fehler/ohne Ergebnis einmal automatisch neu (`versuch: 2`) und prüft
  vor jedem Start den Speicherbedarf (`needMB`: 20 MB je möglichem Video + 10 MB; Skelett-Schritt 0).

## Sparsam mit dem Nutzungslimit (Wunsch des Nutzers: gleiche Qualität, weniger Verbrauch)

- Rollen: Hauptsitzung = Projektleiter (plant, prüft Ergebnisse selbst, merged nur mit OK). Arbeit an Agenten geben:
  einfache/mechanische Aufgaben (Doku, Merges, Tests anpassen, kleine Fixes) → Modell **haiku**; Neuentwicklung mit Design-/
  Logikanteil → **sonnet**; opus nur in der Hauptsitzung für Abnahme und Entscheidungen.
- Höchstens **2 Agenten gleichzeitig** (4 parallel hatten das 5-Stunden-Limit gesprengt); weitere Aufgaben in eine Warteschlange.
- Agenten-Aufträge präzise (Dateien, Abnahmekriterien, Pfade) – spart Suchschritte; Bericht höchstens ~15 Zeilen, keine langen
  Ausgaben/Diffs zurückgeben; Bilderbögen klein (≤ 1600 px breit) und nur so viele, wie für die Abnahme nötig.
- Tests gezielt: während der Arbeit nur betroffene Testdateien, die ganze Suite einmal vor Commit/Merge.
- Abnahme in der Hauptsitzung: Bericht + ein Bilderbogen/Hörprobe; Code nur stichprobenartig (Diff-Statistik, Sicherheitsstellen).
- Keine wiederholten Läufe gegen gesperrte Dienste (Wikipedia 429 o. Ä.) – einmal Ausweichweg, sonst später.

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
