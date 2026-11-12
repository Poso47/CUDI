# CUDI-App (Artefakt) und Cloud-Auftrag

Teil des Projekt-Gehirns (Übersicht: CLAUDE.md). Nur lesen, wenn die Aufgabe dieses Thema berührt.

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
  - **Aufbau (Überarbeitung, hell/dunkel per prefers-color-scheme, EB Garamond + Figtree)**: feste untere Tab-Leiste **Start · Videos · Firma · Briefing · Kommunikation**.
    Start = Kacheln Ranking, Fakten (Ranking mit freiem Thema, „Streng“ an), Story, Reportage, Satire (`art:"satire"`, `thema` oder `meldung` + `links`, `sprache`; Auswahl
    bestätigter Meldungen aus dem Export), Erklärvideo, Clip; je Formular ≤ 3 Pflichtfelder, Rest unter „Mehr Optionen“; Unterseiten (`#ranking` …) mit Zurück-Knopf, „Volle App und Notbetrieb“
    (`#app`) vom Start aus. Clip-Formular fest: `url` ODER `twitch_kanal` (+`zeitraum`), `clip_stil` (vollbild Standard|zuschnitt), `bestaetigt_erlaubnis` nur bei „unklar“, `hochladen` youtube/tiktok/instagram/alle; Karte zeigt Erlaubnis-Pille (erlaubt/gesperrt/unklar) aus dem Prüfbericht. Nur `erklaer` bleibt hinter `CFG.felder` ausgeblendet, bis `job.py` die Art kennt (Ansehen: `?felder=erklaer`).
    **Briefing**: `briefing` aus `firma/stand` (Karten `top` mit Quellen-Chips, `abschnitte` aufklappbar), fehlt es: ehrlich „Briefing noch nicht im Export“ + Link zum Issue-Label `briefing`.
    **Kommunikation**: Sammlung `kommunikation/<id>` (`wunsch`, `prompt`, `agent`, `status` geplant/läuft/fertig/blockiert, `bericht`, `zeit`), die Seite liest nur, geschrieben wird von der Hauptsitzung.
    Firma/3D-Büro: zusätzliche Stationen Welt-Blick, Morgen-Briefing, Clip-Scout, Messung nur bei vorhandenen Daten (`status.*`, `welt`, `briefing`, `clipteam`). Laufende Aufträge zeigen einen Fortschrittsbalken (Schätzung nach Laufzeit).
  - **Firma-Tab** (Leitstand, rein im Browser aus `jobs`/`results`/`bewertungen`, kein Claude-Aufruf): Aufträge als „Mitarbeiter“
    (Rolle nach Art: Rechercheur & Autor, Faktenprüfer = freies Thema, Story-Autor, Clipper); „Projektleiter“: hängt (> 40 Min. ohne
    Ergebnis oder `ohne`), halbe Arbeit (Ergebnis ohne Video/mit Fehler), „Neu starten“ = `restartJob` (gleiche Logik wie die Karte),
    bei freien Mitarbeitern 3 Vorschläge (Bewertung, neue Vorlage, Fakten-Idee) über `startJob`; Banner in jedem Tab.
    **3D-Büro** (Standardansicht, Umschalter „3D / Liste“, Liste = Ersatz/Barrierefreiheit): three.js r128 von cdnjs, lazy geladen; je Auftrag eine Figur am Tisch (Farbe nach Rolle), Projektleiter in der Mitte; Zustände arbeitet (Tippen, Balken aus Laufzeit)/fertig/Fehler-hängt/frei; Ziehen dreht, Antippen öffnet Karte mit `restartJob`/`removeJob`/Videos-Tab/`startJob`; max. 30 fps, nur bei sichtbarem Tab; ohne WebGL/three.js automatisch Liste; Demo `?demo=1`/`?demo=frei`.
  - **Firma-Ordnung** (Abteilungen, Tagesplan, Ampel): `DEPTS` (Leitung, Recherche & Nachrichten, Planung, Produktion, Clip-Team, Auswertung & Pflege) – jede Station trägt `dept`, `task` (ein Satz) und `sched` (UTC-Plan der Workflows, Quelle `.github/workflows/firma-*.yml`; Wahrheits-Prüfer ohne Plan). Kopfzeile `renderHead`: Ampel (Fehler/braucht dich/alles läuft, nur aus `firmaProblems`), „Als nächstes“ aus dem Plan, je Problem EIN Knopf (Neu starten bzw. Ansehen). Ansichten 3D/Liste/Tagesplan (`cudiFirmaAnsicht`); Abteilungs-Knöpfe und 3D-Schilder filtern/zoomen (`ui.dept`, `focusDept`); 3D-Layout `officeLayout` (Zonen mit Teppich+Schild, Produktion unten, Leitung in der Mitte); Tagesplan `renderPlan`: 0–24 Uhr in Ortszeit, Zustände nur aus `status.*` (letzter Lauf ok/Fehler; sonst „kein Lauf gemeldet“/„früher, nicht einzeln gespeichert“, nichts erfunden). Karte je Onkel einheitlich (`stationFacts`/`jobFacts`: Rolle · Abteilung · Aufgabe · letzter Lauf · nächster Lauf · Aktion).
  - Ansehen ohne Cloud: Seite mit `?demo=1` (Aufträge laufen) bzw. `?demo=frei` öffnen – Beispieldaten nur dann.
  - Seite ändern: Datei bearbeiten und mit dem Artifact-Werkzeug unter derselben URL veröffentlichen
    (äußerer HTML-Rahmen fehlt absichtlich – Claude setzt ihn).
- **Schaubild in der App**: Kachel + Unterseite `#schaubild` (`schaubildOrder`: thema, stationen, sprache, stil, seitenformat); Stil-Liste im `<select id="sbStil">` stammt aus `cudi_video/data/bildstile.json` – bei neuem Stil dort und hier eine Option ergänzen.
