# Verbesserungsplan CUDI Video (Audit, nur Analyse)

Stand: Stichproben-Audit per grep/Ausschnitten (nicht jede Datei vollständig gelesen). Alles unten ist mit kostenlosen
Mitteln umsetzbar (ffmpeg, numpy, Pillow, vorhandene Dienste). Aufwand: S < 0,5 Tag, M ~ 1 Tag, L > 1 Tag.

## Kurzfazit

Die Pipeline ist inhaltlich stark (Mehrquellen-Prüfung, Aha-Regel, Betonungsprofile, wortweise Untertitel,
Formate, Notbetrieb). Die größten Lücken liegen **nicht** in der Recherche, sondern bei (1) fehlender automatischer
Endkontrolle, (2) fehlender Musik/Sound-Gestaltung bei Ranking-/Faktenvideos, (3) Stil-Lernen, das nur als Text an
Claude geht, (4) schwacher Plattform-Verpackung (Titel/Cover/Hashtags) und (5) fehlender Freigabe vor Upload.

Belegt im Code:
- Ranking-/Fakten-Ton (`render/video.py:164-228`): Musik nur, wenn der Nutzer selbst `video_assets/music/*.mp3|wav`
  ablegt – Ordner existiert nicht, also **keine Musik**. Die Story-Pipeline hat dagegen selbst erzeugte Stimmungsmusik
  (`story/music.py`) mit Sidechain-Ducking und `loudnorm` (`story/render.py:382-384`) – wird bei Rankings nicht genutzt.
  Ducking im Ranking-Pfad ist ein grober Schwellwert (0.35/1.0), keine Dynamik.
- Lautheit: `loudnorm I=-14` einpassig (`video.py:280`), kein Messen/Prüfen danach.
- Endkontrolle: außer Dauer (`job.py:246`) keine Prüfung (kein Schwarzbild-, Lautstärke-, Safe-Zone-, Sync-Test).
- Vorlieben (`job.parse_preferences`, `handoff.PREFS_NOTE`): nur Freitext an Claude für Schreibaufgaben; `pick_style`
  (`render/theme.py:116`) ist reiner md5-Zufall je Video-ID und kennt Bewertungen nicht.
- Metadaten (`metadata.py:34-67`): Titel = Spec-Titel + „🏆“, Beschreibung = Liste + Hinweise, Hashtags = Basis + Thema;
  keine Titelvarianten, kein Hook im Titel, kein Kapitel-/Keyword-Aufbau. Cover = Standbild bei 2,2 s (`video.py:285`),
  kein gestaltetes Thumbnail.
- Upload (`job.py:556`): Auftragsfeld `hochladen` lädt direkt hoch, keine Vorschau-/Freigabestufe (Skelett-Freigabe gibt es
  nur für Storys).

## Tabelle aller Punkte

| # | Bereich | Lücke / Verbesserung | Nutzen | Aufwand | Kostenlos wie | Neuer Zwischenschritt |
|---|---|---|---|---|---|---|
| 1 | QS | Endkontrolle `qa.py`: ffprobe (Dauer ≤ 179 s, 1080×1920, Audio vorhanden), `blackdetect`/`freezedetect`, `ebur128` (Ziel −14 ± 1 LUFS, TP ≤ −1), Stille am Anfang/Ende, Ergebnis in `ergebnis.json` + Prüfbericht | hoch | M | ffmpeg-Filter (`blackdetect`, `freezedetect`, `ebur128`, `silencedetect`) | nach Render, vor Auslieferung/Upload |
| 2 | QS | Safe-Zone-Test: Render-Rahmen mit Maske (TikTok/Shorts-UI: oben ~130 px, unten ~480 px, rechts ~140 px) prüfen, ob Text/Untertitel-Pixel dort liegen; Test auf Konstanten (`SUB_Y=1385`, Titelblöcke in `formats.py`) | hoch | M | Pillow/numpy auf Stichprobenframes (`render_frame`) | Teil von #1, Frames bei 10 Zeitpunkten |
| 3 | QS | Untertitel-Sync-Test: Wortzeiten aus TTS gegen SRT/Frames vergleichen (Abweichung > 0,25 s melden); Piper-Notbetrieb hat evtl. grobere Zeiten | mittel | S | vorhandene `words`-Zeitstempel | Teil von #1 |
| 4 | QS | Automatische Korrektur bei Befund: Lautheit zweipassig nachziehen (`loudnorm` mit gemessenen Werten), bei Schwarzbild Szene neu rendern, einmal | mittel | M | ffmpeg `loudnorm` 2-Pass | nach #1, 1 Wiederholung |
| 5 | Audio | Musik für Ranking-/Fakten-/Erklärvideos: `story/music.py` (selbst erzeugt, lizenzfrei) wiederverwenden, Stil nach Videoart/Format (`ranking`→pulse/beat, `fakten`→pad, `erklaer`→warm) | hoch | S | vorhandener Generator | in `build_audio` Musikspur ersetzen/ergänzen |
| 6 | Audio | Ducking mit `sidechaincompress` wie in Story (statt Schwellwert 0.35) und Musik per `loudnorm I=-30` vorab; ein gemeinsamer Audio-Mixer für alle Videoarten | mittel | M | ffmpeg | `audio_mix()` gemeinsam in `render/audio.py` |
| 7 | Audio | Sound-Design: Akzent bei Platzwechsel/Zahl-Reveal („Tick“/Riser vor Platz 1), derzeit nur einheitliches `_whoosh` | mittel | S | numpy-Synthese (wie `_whoosh`) | in `build_audio` Ereignisliste |
| 8 | Audio | Lautheit der Stimme vor dem Mix angleichen (je Segment RMS-Normierung), Pausen-Rauschen/Klicks an Teilgrenzen (`assemble_parts`) prüfen | mittel | S | numpy | in `tts.assemble_parts` |
| 9 | Audio | Stimmauswahl pro Videoart/Stimmung testen (A/B der edge-tts-Stimmen), Standard je Sprache dokumentieren; Piper-Notstimme klingt deutlich schlechter – Hinweis im Prüfbericht | niedrig | S | edge-tts / Piper | – |
| 10 | Design | Schnitt-Tempo: Szenenlänge folgt der Sprechlänge; bei langen Plätzen (> 8 s) kein visueller Reiz-Wechsel außer Zoom. Regel „alle 2–3 s neue Bewegung“: zweiter Bildausschnitt/Pop-in-Text/Zahlzähler | hoch | M | vorhandene `clipreel`/Zoom-Bausteine | Prüfung „max. Standzeit“ in `build_jobs` |
| 11 | Design | Hook-Bild: erste 1,5 s mit großem Frage-/Zahlentext und sofortiger Bewegung (heute Intro je Format); Sprecher beginnt ohne Vorlauf (`lead`) – Vorlauf kürzen, wenn Hook-Satz da | hoch | S | vorhandene Formate | Parameter `lead` im Hook = 0–0,15 s |
| 12 | Design | Loop-Ende: letzter Frame/Satz führt zum Anfang (Fragesatz, Bildähnlichkeit), erhöht Wiedersehen bei Shorts | mittel | M | Pillow/ffmpeg | Outro-Variante `loop` |
| 13 | Design | Untertitel: Safe-Zone-Prüfung (siehe #2), Kontrast gegen helle Fotos (Schatten/Hintergrundbox je Bild automatisch prüfen: mittlere Helligkeit unter dem Untertitel) | mittel | S | Pillow | in `render_frame`-Test |
| 14 | Bild | Bildprüfung CLIP: Schwellenwert/Prompts stichprobenartig kalibrieren (Auswertungsskript über `video_output/*/prüfbericht`), Bildqualität (Auflösung ≥ 1080 px kurze Kante, Unschärfe via Laplace-Varianz, Wasserzeichen-Heuristik) ergänzen | mittel | M | Pillow/numpy (Laplace), CLIP vorhanden | in `bildcheck.judge` Zusatzprüfung |
| 15 | Bild | Doppelte Bilder im selben Video (pHash) vermeiden | niedrig | S | `imagehash` oder eigener dHash (numpy) | in `find_visuals` |
| 16 | Stil | Stil-Lernen echt machen: Bewertungen speichern zusätzlich `stil` {name, format, motion, art, dauer} (die Seite kennt das Ergebnis) → einfacher Bandit (Gewichte je Format/Palette/Motion aus 👍/👎, Epsilon 20 % Erkundung) statt md5-Zufall | hoch | M | reines Python, Daten in `bewertungen/<id>` (Artifact-DB), per `vorlieben.stil_gewichte` im Auftrag | `pick_style(..., weights)`; neues Feld in `parse_preferences` |
| 17 | Stil | Vorlieben-Text kürzen/verdichten: statt letzter 8 Rohnotizen eine verdichtete Regel-Liste (Häufigkeit gleicher Stichwörter), sonst verbraucht jede Schreibaufgabe Tokens und Haiku folgt wenig | mittel | S | Python (Zählung) | in `job.parse_preferences` |
| 18 | Stil | Rückmeldung je Aspekt (Hook / Stimme / Bilder / Tempo) in der App statt nur 👍/👎 + Notiz, damit das Lernen zielgenau ist | mittel | M | App-HTML | UI + Feld `aspekte` |
| 19 | Fakten | Quellenstärke im Prüfbericht gewichten (n_extern vorhanden): Rankings mit nur Wikipedia/Wikidata-Bestätigung kennzeichnen und bei freien Themen standardmäßig nicht als „bestätigt“ ausgeben (Warnung gibt es, Verhalten prüfen) | mittel | S | vorhandene Prüfer | Schwelle in `confirmed_only` |
| 20 | Fakten | Aktualitätsprüfung: Stichtag/„Stand“-Jahr im Video nennen und älteste Datenquelle melden (Weltbank oft 2–3 Jahre alt) | mittel | S | Wikidata-Zeitqualifikatoren | Feld in Prüfbericht |
| 21 | Fakten | Themenvorschläge aus Trends: Wikipedia „Most read“ + Google-Trends-freie Alternative (Wikimedia Pageviews API) als Ideenquelle für die Firma-Vorschläge | mittel | M | Wikimedia REST (kostenlos, ohne Schlüssel) | neuer Schritt „Ideen“ vor Planer |
| 22 | Skript | Wiederholungs-Check: n-Gramm-Überlappung zwischen Szenen (gleiche Satzanfänge, „Und jetzt…“-Ketten) und Füllwörter; bei Treffer einmal zur Korrektur | mittel | S | Python (`textcheck.py` erweitern) | nach Schreibaufgabe, vor Render |
| 23 | Skript | Sprachrhythmus: Satzlängen-Varianz (kurz–kurz–lang), Maximalsatzlänge für TTS (> 22 Wörter teilen), Zahlen sprechbar (Tausenderpunkt/„Komma“) prüfen | mittel | S | Python | in `textcheck`/vor TTS |
| 24 | Skript | Hook-Varianten: 3 Hook-Kandidaten erzeugen und per Regel (Zahl/Frage/Konflikt, Länge ≤ 12 Wörter, kein Spoiler) bewerten; heute `retention.hook` wählt eine Vorlage per Zufall | hoch | M | Regelbewertung + 1 Claude-Aufruf mit 3 Varianten in derselben Schreibaufgabe | in `narrate`/`retention` |
| 25 | Skript | Retention-Marker: nach ~60 % „Zwischen-Aufhänger“ vorhanden (`bridges`); Prüfung, dass Platz 1 nicht vor dem Ende genannt wird (Spoiler im Hook) | niedrig | S | Python-Test | Teil von #22 |
| 26 | Plattform | Titel: 3 Varianten (Zahl + Neugierlücke, ≤ 60 Zeichen für Shorts-Anzeige), Emoji nicht pauschal „🏆“; Titel aus Hook ableiten | hoch | S | Regeln + Claude-Feld `titel_varianten` | `metadata.build_metadata` |
| 27 | Plattform | Beschreibung: erste Zeile = Keyword-Satz + Kommentarfrage (aus `retention`), Liste danach; Kapitel nicht nötig bei Shorts. Hashtags: 3–5 statt Dauerliste, #Shorts je Plattform | mittel | S | Regeln | `metadata.py` |
| 28 | Plattform | Thumbnail/Cover: gestaltetes Cover (großer Titel/Zahl, Kontrast, Gesicht/Motiv zentriert) statt Frame bei 2,2 s; mehrere Kandidaten, Auswahl nach Schärfe/Kontrast | hoch | M | Pillow + vorhandene Formate | `cover.py`, nach Render |
| 29 | Plattform | Beste Länge: Shorts-Retention fällt ab > 45–60 s; Standard-Ziel je Videoart (Ranking 30–45 s, Fakten 25–40 s) und Warnung im Bericht bei Überlänge, Top N danach wählen | mittel | S | Konfiguration | `pipeline.MAX_SECONDS` neben `ZIEL_SEKUNDEN` |
| 30 | Plattform | Postingzeiten/Serie: Seitenreihe („Teil 2“-Vorschlag, Playlist-Name) pro Thema | niedrig | S | Text | Metadaten |
| 31 | App | Freigabe vor Upload: Video erst als Entwurf (YouTube „privat“ / TikTok Inbox) hochladen oder Upload-Knopf nach Ansicht; derzeit lädt `hochladen` im Lauf direkt hoch | hoch | M | vorhandene Upload-Module (`privat` ist bereits Sichtbarkeit) | Zwei-Schritt-Auftrag `"schritt":"upload"` analog Skelett |
| 32 | App | Skelett-/Skript-Freigabe auch für Rankings und Fakten (heute nur Storys): Texte je Platz editierbar vor dem Render | hoch | L | vorhandenes Skelett-Muster (`skelette/<id>`) | `schritt: skript` |
| 33 | App | Video nachträglich bearbeiten (nur neu rendern, ohne neue Recherche): Szenentext/Format/Palette/Musik ändern, `research`+`script` als Arbeitsdatei in `results/<id>` behalten und mit neuen Optionen neu rendern | hoch | L | vorhandene Zwischenergebnisse (JSON) | Auftrag `"schritt":"neu_rendern"` |
| 34 | App | Zwei Varianten zum Vergleichen (z. B. 2 Formate/Hooks) – Bewertung liefert Lerndaten für #16 | mittel | M | Render ×2, Limit beachten | Auftragsfeld `varianten` |
| 35 | App | Qualitätsbericht (#1) in der Karte anzeigen (Ampel: Lautheit, Länge, Safe-Zone) | mittel | S | App-HTML | Feld `qa` in `ergebnis.json` |
| 36 | Zuverl. | Tests: es gibt 20 Testdateien (CI „Tests“), aber keine Tests für Render-Ergebnis (Pixel/Audio) außer `test_video.py`; Golden-Tests: ein 5-s-Testvideo, Kontrollwerte (LUFS, Safe-Zone, Dauer) | mittel | M | pytest + ffmpeg (CI hat ffmpeg) | Test nutzt `qa.py` aus #1 |
| 37 | Zuverl. | Netz-Ausfälle: gespeicherter Antwort-Cache für Wikidata/Wikipedia (Dateicache mit TTL) für Wiederholungsläufe und Tests; reduziert Sperren (429) | mittel | M | `requests` + JSON-Cache in `video_output/_cache` | in `net.py` |
| 38 | Zuverl. | Fortschritt/Wiederaufnahme: `_work`-Zwischenstände (TTS, Szenenvideos) bei Neustart (`versuch: 2`) wiederverwenden statt neu rechnen | mittel | M | Dateiexistenz + Hash der Eingaben | in `pipeline`/`render_video` |
| 39 | Zuverl. | Telemetrie lokal: je Lauf Dauer/Ausfälle/Ausweichwege in `ergebnis.json`, Zusammenfassung im Firma-Tab (welche Quelle fällt am häufigsten aus) | niedrig | S | JSON | Feld `lauf` |

## Priorisierte Umsetzung in Paketen

Reihenfolge nach Nutzen/Aufwand; höchstens 2 Agenten gleichzeitig (Paket A und B sind dateifremd, parallel möglich).

### Paket A – Endkontrolle (Punkte 1, 2, 3, 4, 35-Datenseite, 36)
- Dateien: neu `cudi_video/qa.py`, Einbindung in `cudi_video/pipeline.py` (nach Render) und `cudi_video/job.py`
  (`ergebnis.json`-Feld `qa`), `tests/test_qa.py`, Prüfbericht `metadata.build_review`.
- Abnahme: Testvideo mit absichtlich schwarzem Abschnitt, falscher Lautheit und Text in der Safe-Zone-Maske wird
  erkannt; Normalvideo besteht (−14 ± 1 LUFS, TP ≤ −1, Dauer ≤ 179 s); Sync-Abweichung > 0,25 s wird gemeldet;
  Befund erscheint im Prüfbericht; Lautheit wird einmal automatisch korrigiert; ganze Suite grün.
- Modell: **sonnet** (Filter-Auswertung und Safe-Zone-Geometrie), Tests/Doku danach **haiku**.

### Paket B – Musik und Sound-Design (Punkte 5, 6, 7, 8)
- Dateien: `cudi_video/render/video.py` (`build_audio`), neu `cudi_video/render/audio.py` (gemeinsamer Mixer),
  `cudi_video/story/music.py` (Wiederverwendung, Stil je Videoart), `cudi_video/story/render.py` (auf Mixer umstellen),
  `cudi_video/erklaer/render.py`, Schalter `CUDI_MUSIK=aus`, Auftragsfeld optional.
- Abnahme: Ranking-/Fakten-/Erklärvideo hat leise Musik (−30 LUFS vor Mix), beim Sprechen hörbar abgesenkt,
  Endlautheit −14 LUFS (mit Paket A messbar); Hörprobe 20 s; bestehende Tests grün; Musik abschaltbar.
- Modell: **sonnet**.

### Paket C – Plattform-Verpackung (Punkte 26, 27, 28, 29)
- Dateien: `cudi_video/metadata.py`, neu `cudi_video/render/cover.py`, `cudi_video/render/video.py` (Cover-Aufruf),
  `cudi_video/story/render.py` (Cover), `cudi_video/retention.py` (Kommentarfrage), `cudi_video/pipeline.py` (Längenziel).
- Abnahme: je Video 3 Titelvarianten (≤ 60 Zeichen) + gewählter Titel, 3–5 Hashtags, Cover mit Titel/Zahl lesbar auf
  Handygröße (Bilderbogen), Warnung bei Länge > Ziel; Tests für Metadaten angepasst.
- Modell: **sonnet** (Cover-Gestaltung), Metadaten-Regeln **haiku**.

### Paket D – Skriptqualität (Punkte 22, 23, 24, 25)
- Dateien: `cudi_video/textcheck.py`, `cudi_video/retention.py`, `cudi_video/narrate.py`, `cudi_video/facts.py`,
  `cudi_video/handoff.py` (Hook-Varianten im selben Aufruf), `tests/test_brain.py`.
- Abnahme: Wiederholungs-/Satzlängen-Prüfung greift mit Testtexten; Hook wird aus 3 Kandidaten per Regel gewählt,
  kein Spoiler von Platz 1; kein zusätzlicher Claude-Aufruf (Limit sparen); Tests grün.
- Modell: **sonnet** (Regeln/Prompt), Tests **haiku**.

### Paket E – Lernender Stil (Punkte 16, 17, 18)
- Dateien: `cudi_video/render/theme.py` (`pick_style` mit Gewichten), `cudi_video/job.py` (`parse_preferences`,
  `stil_gewichte`), `docs/cudi-app-artefakt.html` (Bewertung speichert `stil`, Aspekte, Gewichte beim Start),
  `cudi_video/handoff.py`, `tests/test_job.py`.
- Abnahme: Nach Testbewertungen (👎 für „zahl“, 👍 für „magazin“) wird „magazin“ nachweislich häufiger gewählt,
  mindestens 20 % Erkundung bleibt; Standard (keine Daten) verhält sich wie bisher (md5 je ID); Vorlieben-Text ≤ 600 Zeichen.
- Modell: **sonnet** (App + Logik).

### Paket F – Freigabe, Upload, Nachbearbeitung (Punkte 31, 33, 32, 34)
- Dateien: `cudi_video/job.py` (`schritt: upload|neu_rendern`), `cudi_video/upload/*`, `docs/cudi-app-artefakt.html`,
  `cudi_video/pipeline.py` (Zwischenstände speichern), Doku `docs/upload-einrichten.md`.
- Abnahme: Upload nur nach Knopf „Veröffentlichen“ (Standard Entwurf/privat); Neu-Rendern mit anderem Format/Text ohne
  neue Recherche in < 50 % der Zeit; Fehler erscheinen als Hinweis, nicht als Abbruch (Wunsch „keine Fehlschläge“).
- Modell: **sonnet** (Ablauf und App); Doku **haiku**. Größtes Paket – erst nach A.

### Paket G – Dramaturgie und Bildqualität (Punkte 10, 11, 12, 13, 14, 15)
- Dateien: `cudi_video/render/formats.py`, `scenes.py`, `video.py` (`build_jobs`), `cudi_video/bildcheck.py`, `media.py`.
- Abnahme: Keine Standzeit ohne Bewegung > 3 s (Test über Frame-Differenz), Hook-Beginn ≤ 0,15 s Vorlauf, Bilder
  unter 1080 px/unscharf werden aussortiert; Bilderbogen zeigt keine Doppelbilder.
- Modell: **sonnet**.

### Paket H – Recherche-Feinschliff und Robustheit (Punkte 19, 20, 21, 37, 38, 39, 9, 30)
- Dateien: `cudi_video/verify/checkers.py`, `cudi_video/planner.py`, `cudi_video/net.py`, `cudi_video/pipeline.py`,
  `cudi_video/job.py`, `docs/cudi-app-artefakt.html` (Firma-Tab).
- Abnahme: Datei-Cache mit TTL reduziert Netzaufrufe im zweiten Lauf messbar; Wiederholung nutzt Zwischenstände;
  „Stand“-Jahr im Bericht; Trend-Ideen als Vorschläge sichtbar.
- Modell: **haiku** für 37/39/30/9, **sonnet** für 19/20/21/38.

Empfohlene Reihenfolge: A → B (parallel) → C → D → E → G → F → H.
Hinweis: Punkte 16/31–34 ändern die App (`docs/cudi-app-artefakt.html`) und verlangen Neuveröffentlichung unter derselben URL.
