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
- **Regie & Psychologie** (`regie.py`, nach dem Erzählen/vor `wahrheit`+Vertonung in `pipeline.run` und `story/editor.build_skeleton`): Basis-Checkliste (`firma/wissen.BASIS`) + gelernte Regeln mit Quelle (`firma_daten/wissen.json`, Wissens-Sammler `firma/wissen.py`, wöchentlich, Gemini, `firma-wissen.yml`) → Score je Kriterium vorher/nachher; EINE Schreibaufgabe `regie` (3 Hook-Kandidaten ohne Spoiler, natürlichere Abschnitte, Schluss); jede Änderung durch `pruefe_aenderung` + `wahrheit.Pruefer` (neuer Befund oder sinkender Score → alter Text bleibt); ohne Modell nur Bewertung; Ergebnis `regie.json`/`ergebnis.json["regie"]`/Prüfbericht „Regie & Psychologie“. `tts.naturalize`: Atempausen + leichte Tempo-/Tonhöhen-Variation je Video (aus: `CUDI_NATUERLICH=0`).
- Bildprüfung (`bildcheck.py`, CLIP ViT-B-32 CPU, Cache `video_output/_models`, 3 Bilder je Kandidat, ≥ 2/3 mit p ≥ 0.5; Ausfall → Tag-Abgleich;
  Ranking-Clips nur sortiert via `media.rank_by_image`; Tests setzen `CUDI_BILDPRUEFUNG=0`). Bildpassung (`facts.find_visuals`, `media.motif_matches`): Fakt-Feld `motiv` + `suche`-Liste; Treffer nur, wenn alle Kernwörter des
  Motivs in Beschreibung/Tags stehen (Clip → Foto → Commons → „Stimmungsbild“, im Prüfbericht vermerkt). Aha-Regel
  (`themen.AHA_RULES`, Fakt-Feld `aha_<sprache>`, geprüft in `facts.checked_aha`): Outro „Heute gelernt: …“ (Platz 1; Rankings: Spitzenwert).
- Verpackung (`render/cover.py`, `metadata.py`): Cover 1080×1920 (Titelwort, Spitzenwert, bestes Bild, Look des Formats, Safe-Zone) auch als erstes Frame (0,2 s; `CUDI_COVER_FRAME=0` aus); 3 Titelvarianten ≤ 60 Zeichen je Sprache (Aufgabe `titel` über `handoff`, geprüft: Zahl/Clickbait/Länge, sonst Regel-Varianten, beste per `title_score`) im Ergebnis (`titel_varianten`, Kopier-Knöpfe); 3–5 Hashtags je Plattform (#shorts YouTube, #fyp TikTok); Längenziel `LENGTH_GOALS` nur als Hinweis im Prüfbericht.
- **Experimente/Lernen** (`experimente.py`, `firma/lernen.py`, Doku `docs/lernen-einrichten.md`): je Video eine Variante je Stellschraube
  (Format, Design, Bewegung, Musik, Maskottchen; Hook/Länge vorbereitet, `KNOBS[..]["aktiv"]`), Bandit (Thompson, ≥ 20 % Erkundung) aus
  `firma_daten/lernen.json`; feste Wünsche im Auftrag gehen vor; ohne Daten = alte md5-Wahl. `varianten` in `ergebnis.json`/Ergebnis-Dokument;
  App-Bewertungen senden `vorlieben.varianten_gut/_schlecht` (zählen doppelt, Env `CUDI_VORLIEBEN_VARIANTEN`). Lern-Analyst (täglich, Workflow
  `firma-lernen.yml`) liest YouTube (`youtube.readonly` oder `CUDI_YT_API_KEY`) und TikTok (`video.list`; `youtube-login --lesen`, `tiktok-login --lesen`),
  Zuordnung über `firma_daten/uploads.json` (nur Notbetrieb-Job „liste“ schreibt; Claude-Läufe committen nie).
- **Reportage** (`reportage/`, Auftrag `art: "reportage"` mit `thema`, `links`, `sprache`; Tab „Reportage“ der App): sachlich, nur Aussagen mit wörtlichem Beleg
  aus ≥ 2 unabhängigen Betreibern (news.json, Wikipedia, Links), Aufgabe `reportage` (`handoff`) + Regelweg, Zahlen/Namen/Clickbait/Drama/Spekulation geprüft,
  Buchlook ohne Musik/Maskottchen, Quellen + Stand am Ende; zu wenig Quellen = ehrlicher Abbruch. Ideen mit `bereich: reportage` tragen einen Auftrag.
  Weitere Formate als Plan: `docs/content-formate.md`.
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
    **3D-Büro** (Standardansicht, Umschalter „3D / Liste“, Liste = Ersatz/Barrierefreiheit): three.js r128 von cdnjs, lazy geladen; je Auftrag eine Figur am Tisch (Farbe nach Rolle), Projektleiter in der Mitte; Zustände arbeitet (Tippen, Balken aus Laufzeit)/fertig/Fehler-hängt/frei; Ziehen dreht, Antippen öffnet Karte mit `restartJob`/`removeJob`/Videos-Tab/`startJob`; max. 30 fps, nur bei sichtbarem Tab; ohne WebGL/three.js automatisch Liste; Demo `?demo=1`/`?demo=frei`.
  - Ansehen ohne Cloud: Seite mit `?demo=1` (Aufträge laufen) bzw. `?demo=frei` öffnen – Beispieldaten nur dann.
  - Seite ändern: Datei bearbeiten und mit dem Artifact-Werkzeug unter derselben URL veröffentlichen
    (äußerer HTML-Rahmen fehlt absichtlich – Claude setzt ihn).
- **Notbetrieb** (Claude-Limit erreicht; Doku `docs/notbetrieb-einrichten.md`): Standardweg = **GitHub-Issue** (Hugging Face verlangt für Docker-Spaces PRO/402): Banner „Notbetrieb öffnen“ der App-Seite öffnet `issues/new` mit Marker `cudi-auftrag` und App-Auftrag als JSON-Block (`nbIssueLink`, URL ≤ 6000 Zeichen, nur Ranking/Story im ganzen Lauf); `auftrag.yml`/`auftrag.py` (`extract_json`, `build_json_order` → `job.parse_order`, Kennung `gh<Nr>`) startet `notbetrieb.yml` → `.github/scripts/notbetrieb.py` (`run`: `job.run_order(via_claude=False)`, Hochladen direkt, `freigabe:false`; `melden`: Kommentar mit Texten/`upload_note`/Prüfbericht-Kurzform + Artefakt-Link, Erfolg schließt das Issue). Secrets `CUDI_LLM_*` (+ optional Pexels/Pixabay/YT/TikTok). Repo öffentlich → Issues/Artefakt-Links sichtbar. `handoff.request` fragt ohne `CUDI_SCHREIBEN` ein freies LLM (`CUDI_LLM_*`, Gemini; `handoff.active()`/`llm_mode()`, Fehler → None → Textbausteine). Optional/alt: Web-App-Space (`cloud-app.yml` nur manuell, überspringt ohne `HF_TOKEN`/bei 402; `POST /api/auftrag`); steht `config/notbetrieb.url`, öffnet der Banner diese Adresse statt GitHub (`?demo=limit` zeigt den GitHub-Weg).
- Upload (`cudi_video/upload/`: `youtube.py` resumable videos.insert, `tiktok.py` Inbox/Direct Post, `cli.py`): `hochladen … --probe`, `youtube-login`;
  Zugang nur über Umgebungsvariablen (`CUDI_YT_*`, `CUDI_TIKTOK_*`, nie ausgeben: `upload.redact`), Auftragsfeld `hochladen` (Standard aus), Doku `docs/upload-einrichten.md`.
- Betonung (`tts.py`, Tabelle `SPEECH_PROFILES` + `MOOD_STYLE`): Abschnitte werden in Teile mit eigenem Tempo/Tonhöhe/Lautstärke und
  Spannungspausen zusammengesetzt (`assemble_parts`, Wortzeiten wandern mit; Grundtempo `+0%`). Profil nach Videoart
  (`speech_profile(spec.kind)`): ranking (Pausen vor Platz/Zahl), fakten (Frage, Pause vor dem Aha, ruhiger Erklärteil), erklaer (ruhig,
  gleichmäßig), Story je Stimmung (`plan_story_parts`: Pause vor Wendung/Pointe). `CUDI_SPEECH_PROFILE=ranking|fakten|erklaer|aus` überschreibt.
- Endkontrolle (`qa.py`, nach dem Render in `render_video`/Erklär-Render, für Story/Clip in `job._summary`): blackdetect, freezedetect (nur Ranking/Fakten), ebur128 (−14 LUFS ±1, TP ≤ −1), Dauer, 1080×1920, Sync, Safe-Zones über Layout-Konstanten; Lautheit wird einmal per zweistufigem `loudnorm` korrigiert, Befunde nur als Hinweise (`ergebnis.json` Feld `qa`, `review.md` „Endkontrolle“, nie Abbruch).
- **Wahrheit** (`wahrheit.py`, Nutzerwunsch: nie lügen, auch nicht durch Formulierung): `Pruefer` prüft Sprechtext/Hook/Untertitel/Titel/Cover/Beschreibung gegen die Daten (Regelkatalog `REGELN`, optional Gegenlesen `wahrheit_pruefung`), korrigiert automatisch (ergänzen/ersetzen/streichen); Endabnahme `pipeline.render_checked` (Wahrheit UND qa, eine Reparaturrunde, sonst `abnahme.ok=false` → `job._summary` liefert nicht aus, `ok:false` „Nicht ausgeliefert, weil …"); Abschnitt „Wahrheits-Prüfung" in review.md.
- Musik für Ranking/Fakten/Erklär (`render/audio.py`: Stil je Videoart/Format/Thema aus `story/music.py`, selbst erzeugt, Ducking unter der Stimme, Akzent-Ton je Platz-Enthüllung; Datei in `assets/music` hat Vorrang; abschaltbar `CUDI_MUSIK=0`).
- **Clip-Engine** (`cudi_video/clip/`, CLI `python -m cudi_video clip <datei|url>`, Doku README_VIDEO.md): Podcast-/Streamer-Clips
  1080×1920 (faster-whisper → Höhepunkt/Hook nach Regeln, optional Claude-Auswahl `clip_hook` über `handoff` → Pausenschnitt →
  Sprecher-Zuschnitt mit YuNet/Haar → ASS-Untertitel). App-Auftrag `art: "clip"` (`job._clip`): Pflichtfeld `bestaetigt_erlaubnis`,
  nur http(s)-Links, Texte/Prüfbericht in `clip/texte.py`; YouTube sperrt Cloud-IPs oft (`ClipError.wiederholbar`, Hinweis „später/PC“).
- Weitere Wege: GitHub Actions „CUDI Video“/„CUDI Story“, Issue mit `cudi-auftrag` („CUDI Auftrag“),
  Hugging Face Space („CUDI Cloud-App“, optional, braucht Secret HF_TOKEN).
- **Firma-Mitarbeiter (GitHub)** (`cudi_video/firma/`, Workflows `.github/workflows/firma-*.yml`, cron + manuell, kein Claude-Verbrauch;
  Ergebnisse als JSON in `firma_daten/` (nicht `data/`, das ist gitignored), Bot-Commit `[skip ci]` über `scripts/firma_commit.sh`
  nur bei Änderung, alle Läufe nacheinander via `concurrency: firma-daten`): **Trend-Scout** (`trends.py`, alle 3 h: YouTube mostPopular
  DE/US mit `CUDI_YT_API_KEY` oder OAuth `CUDI_YT_*` – sonst nur Hinweis, Google-Trends-RSS, Wikipedia-Top, Reddit RSS/Arctic Shift →
  `trends.json`), **News-Reporter** (`news.py`, alle 3 h: Tagesschau/DW/BBC/NPR-RSS, GDELT, Wikipedia Current events → `news.json`; „bestätigt“
  erst bei ≥ 2 unabhängigen Betreibern, nur Titel/Kurzzeile/Link), **Ideen-Entwickler** (`ideen.py`, täglich: Gemini über `CUDI_LLM_*`, nur
  Themen mit Beleg in Trends/News, Ranking vorgeprüft per Vorlage/`planner.plan`/Wikidata-Probe, Ausgabe im App-Auftragsformat; ohne Secrets
  regelbasiert → `ideen.json`), **Putzmann** (`putzen.py`, täglich: Artefakte > 7 T., Läufe > 30 T. löschen, erledigte `cudi-auftrag`-Issues > 14 T.
  sperren, `firma_daten/` ausdünnen → `putzen.json`; Probelauf `CUDI_PUTZEN_TROCKEN=1`). `status.json` = letzter Lauf/Dauer/Ergebnis/nächste Planung je Mitarbeiter
  (Grundlage fürs 3D-Büro). Jede Quelle einzeln abgesichert (Ausfall = Hinweis). Lokal: `python -m cudi_video.firma <trends|news|ideen|putzen>`,
  Ausgabeordner per `CUDI_FIRMA_DATEN` umlenkbar; Tests `tests/test_firma.py`.
  **Onkel-Büro** (Firma-Tab, 3D): alle Figuren sind freundliche Onkels (Bärte, Takke/Kufi/Kappe, Weste in Rollenfarbe, Teeglas am Tisch; Teppich-Canvas,
  Arkade, Laternen, Pflanzen); je GitHub-Mitarbeiter eine Station (Trend-Wand, News-Pult, Ideen-Tafel, Bücherregal, Lern-Diagramm, Waage; Putz-Onkel läuft mit
  Besen), Chips + Liste als Touch-/Ersatzansicht; Karte zeigt Top-3-Trends/bestätigte News/Ideen mit „Starten“ (`startJob`)/Wissensregeln/Putzbericht.
  Datenweg ohne Claude-Verbrauch: `firma_commit.sh` ruft `python -m cudi_video.firma export` → `docs/firma/firma.json` (`firma/export.py`, nur bei Änderung);
  die Seite liest erst die Datenbank `firma/stand`, dann Pages-Fetch `poso47.github.io/CUDI/firma/firma.json`. **Artefakt-CSP sperrt `fetch` zu
  fremden Hosts** (nur Dateien neben der Seite) → Pages-Weg läuft in Claude vermutlich nicht; verlässlich ist `firma/stand`: bei jedem Auftrags-Lauf
  `ArtifactData set` (collection `firma`, doc_id `stand`, file_path `docs/firma/firma.json` – siehe Zusatzzeile in der Aufgabe, nur mit OK des Nutzers).
  Demo: `?demo=1`.
- Kosten: alles kostenlose Dienste; App-Aufträge zählen nur zum Claude-Nutzungslimit des Nutzers.
- **Keine Fehlschläge** (Wunsch des Nutzers) – kostenlose Ausweichwege, siehe README „Probleme?“:
  edge-tts 6 Versuche → Piper offline (`tts.PIPER_VOICES`, Modelle in `video_output/_piper`, `piper-tts`
  wird bei Bedarf installiert); Story: Reddit-JSON (Cloud: 403) → Arctic Shift → Reddit-RSS (gedrosselt);
  Beschreibung ohne Treffer → beliebte Story der Stimmung; `job.run_order` wiederholt Störungen einmal
  (`RETRY_PAUSE`); App startet Fehler/ohne Ergebnis einmal automatisch neu (`versuch: 2`) und prüft
  vor jedem Start den Speicherbedarf (`needMB`: 20 MB je möglichem Video + 10 MB; Skelett-Schritt 0).

## Kommunikation (Wunsch des Nutzers: immer als klarer Prompt)

- Jeden Nutzerwunsch zuerst in einen **Auftrags-Prompt** übersetzen und dem Nutzer kurz zeigen („So habe ich dich
  verstanden“). Vorlage mit ZIEL, WARUM, GRUNDSÄTZE, KONTEXT, AUFGABE, NICHT TUN, ABNAHME und BERICHT steht in
  `docs/kommunikation.md`. Agenten bekommen immer den vollständigen Prompt und liefern einen Bericht nach der
  Vorlage (ERGEBNIS, GEÄNDERT, GEPRÜFT, OFFEN, NÄCHSTER SCHRITT). Ergänzungen heißen „Ergänzung vom Projektleiter“.
- **Lernen:** Erledigte Arbeit wird als Skill gespeichert (`.claude/skills/`, z. B. `firma-mitarbeiter`, `pruefen-und-mergen`,
  `app-artefakt`, `cloud-probelauf`, `ausweg-finden`). Agenten-Berichte enden mit SKILL. Gibt es einen passenden Skill, macht die
  Hauptsitzung die Arbeit selbst statt einen Agenten zu starten.
- **Lösungsorientiert:** Scheitert ein Weg, wird nicht aufgegeben. Erst Ursache lesen, dann reparieren, dann einen anderen kostenlosen
  Weg suchen, dann kleiner schneiden, erst dann fragen (Skill `ausweg-finden`). Die Regeln bleiben dabei bestehen.
- Agenten arbeiten immer in einem eigenen Worktree (`isolation: "worktree"`), nie im Hauptordner.

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
- Commits auf Deutsch, Push auf den eigenen Zweig. **Merge: Der Nutzer hat dauerhaft erlaubt, fertige und in der Hauptsitzung geprüfte Pakete selbst per PR zu mergen** (ganze Suite grün); danach kurz berichten.
- Textprüfungen für Claude-Texte (Zahlen werttreu, Vornamen, ganze Wörter als Beleg): `cudi_video/textcheck.py`.
- Probeläufe in der Cloud: Auftrag als `jobs/<id>` anlegen (ArtifactData), `fire_trigger` mit dem JSON, dann
  `jobs/<id>.session` setzen; Ergebnis in `results/<id>`, Videos als Assets (Artifact read mit `path` = Asset-ID).
- Stolperfallen: kein `pkill -f <muster>`, wenn das Muster im selben Befehl steht (beendet die eigene
  Shell) – PIDs verwenden. `update_trigger`/`delete_trigger` blockt die Rechteprüfung ohne ausdrückliches OK. Wikidata-SPARQL: Blazegraph sieht OPTIONAL-Variablen in `NOT EXISTS` nicht
  zuverlässig (eigenen Stichtag dort neu binden). Pollinations nur nacheinander (sonst 402).
