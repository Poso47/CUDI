# CUDI Video – Ranking-Faktenvideos und Reddit-Storys für TikTok & YouTube Shorts

CUDI Video erstellt kostenlos animierte **Top-10-Faktenvideos** (Hochformat 1080×1920, höchstens
3 Minuten) auf **Deutsch und Englisch** – aus einer Vorlage oder einem frei eingetippten Thema wie
„die höchsten Wasserfälle Südamerikas“. Jeder Wert wird vorher mit unabhängigen Quellen aus
verschiedenen Ländern abgeglichen.

Pro Video entstehen:

| Datei | Wozu |
|---|---|
| `<id>_de.mp4` / `<id>_en.mp4` | fertiges Video (Lautheit auf ca. −14 LUFS normalisiert) |
| `<id>_de_beschreibung.txt` | YouTube: Titel + Beschreibung mit Ranking, Quellen-Links, Bildnachweisen, KI-Hinweis, Hashtags |
| `<id>_de_tiktok.txt` | TikTok: kurzer Text mit geprüften Quellen, Stand, KI-Hinweis, Hashtags |
| `<id>_de_cover.jpg` | Vorschaubild |
| `<id>_de.srt` | Untertitel zum Hochladen (YouTube) |
| `review.md` | **Prüfbericht** – vor dem Hochladen lesen (in der Web-Oberfläche als Seite) |

## Schnellstart am Windows-PC

1. Python 3.11+ installieren (python.org, Haken bei „Add to PATH“).
2. ffmpeg: installiert `CUDI_VIDEO.bat` beim ersten Start selbst (per winget), sonst
   `winget install Gyan.FFmpeg` (danach Fenster neu öffnen).
3. `CUDI_VIDEO_TEST.bat` doppelklicken – der Selbsttest zeigt, ob alles bereit ist.
4. `CUDI_VIDEO.bat` doppelklicken → Browser öffnet sich auf http://localhost:8000

Kommandozeile:

```bash
pip install -r cudi_video/requirements.txt
python -m cudi_video check                                  # Selbsttest
python -m cudi_video presets                                # Vorlagen anzeigen
python -m cudi_video make hoechste-gebaeude                 # Video DE + EN aus einer Vorlage
python -m cudi_video make "die tiefsten Seen der Welt"      # freies Thema
python -m cudi_video make "die höchsten Berge der Alpen" --langs de --count 5
python -m cudi_video make meiste-einwohner --nur-skript     # erst nur Skript + Prüfbericht
python -m cudi_video make meiste-einwohner --streng         # nur mit bestätigten Fakten
python -m cudi_video web                                    # Web-Oberfläche
```

## Themen

**Vorlagen** (`presets/`): größte Länder, meiste Einwohner, kleinste Länder, höchste Gebäude,
höchste Berge, größte Seen, tiefste Seen, größte Inseln, höchste Wasserfälle.

**Freie Themen** – ohne KI-Schlüssel, aber nur für Themen mit geprüfter Datenqualität:

| Thema | sortierbar nach | Regionen |
|---|---|---|
| Länder | Fläche (größte/kleinste), Einwohner | weltweit, Kontinent |
| Gebäude | Höhe | weltweit, Kontinent, Land |
| Berge | Höhe | weltweit, Kontinent, Land, Gebirge (Alpen, Himalaya, Anden, Rocky Mountains) |
| Seen | Fläche, Tiefe | weltweit, Kontinent, Land |
| Inseln | Fläche | weltweit, Kontinent, Land |
| Wasserfälle | Höhe | weltweit, Kontinent, Land |

Beispiele: „Top 5 der größten Seen Deutschlands“, „die bevölkerungsreichsten Länder Afrikas“,
„tallest buildings in the united states“. In der Web-Oberfläche erscheint beim Tippen sofort,
wie das Thema verstanden wurde. Unbekannte Themen werden abgelehnt statt geraten (z. B. Stadien
oder Vulkane: dort sind die Wikidata-Daten veraltet bzw. unvollständig). Mit einem eingerichteten
Sprachmodell (siehe unten) werden weitere Themen versucht.

## Grundsatz: nichts erfinden

* **Zahlen aus Wikidata, abgeglichen mit unabhängigen Quellen** (siehe unten). Pro Eintrag gilt der
  neueste Wert; bei Gebäuden die architektonische Höhe (nicht die Antennenspitze).
* **Vergleiche werden berechnet**, nicht geschätzt: „Das ist 48-mal so groß wie Deutschland“ – der
  Vergleichswert kommt ebenfalls live aus Wikidata und wird genauso abgeglichen.
* **Wikipedia-Sätze nur wörtlich** und nur ohne eigene Zahlen, Rangaussagen („elfthöchste“) oder
  zeitabhängige Aussagen („derzeit“) – die könnten unseren Daten widersprechen oder veralten.
* **Neutral:** wertende, politische oder konfliktbezogene Sätze werden nicht übernommen.
* **Was es nicht (mehr) gibt, fliegt raus:** nie gebaute, unvollendete, fiktive oder zerstörte
  Bauwerke, Urzeitseen und Objekte auf anderen Himmelskörpern.
* **Optionales Sprachmodell** darf nur umformulieren; jede Zahl muss in den Quelldaten stehen, ein
  zweiter Faktencheck prüft jede Aussage – sonst wird der Text verworfen.
* **Bilder nur mit freier Lizenz** (Wikimedia Commons), Urheber und Lizenz stehen im Video und in der
  Beschreibung. Länder zeigen Flaggen, ohne Bild gibt es eine Grafik mit Themen-Icon.

## Quellen-Abgleich

| Quelle | Herkunft | prüft |
|---|---|---|
| Wikidata | weltweite Community | Ausgangswert |
| Weltbank | internationale Organisation | Fläche, Einwohner von Staaten |
| CIA World Factbook | US-Regierung | Fläche, Einwohner von Staaten |
| OpenStreetMap | weltweite Kartografie-Community | Gebäude- und Berghöhen |
| Wikipedia EN, DE, FR, ES, RU, AR, ZH, JA | acht Sprachgemeinschaften | liest den Wert samt Einheit aus der Einleitung, sonst aus der Infobox – kann bestätigen **oder widersprechen** |
| Google Fact Check Tools (optional) | Faktencheck-Redaktionen (Correctiv, AFP, Snopes …) | gibt es Faktenchecks zum Eintrag? |

Ergebnis je Platz (Prüfbericht mit allen Werten und Links; im Video als Chip „✓ 4 Quellen“):

* **bestätigt** – mindestens eine unabhängige Quelle stimmt überein; einzelne Ausreißer werden bei
  klarer Mehrheit benannt, aber nicht übernommen (Beispiel: Weltbank meldete Kanada mit 15,6 Mio. km²).
* **korrigiert** – der Wikidata-Wert ist veraltet oder falsch, mehrere unabhängige Quellen stimmen
  überein → deren Wert gilt, das Ranking wird neu sortiert (Beispiele: Indien 1,44 Mrd. statt
  veralteter 1,33 Mrd. → Platz 1 vor China; Großbritannien 209.331 km² laut fünf Wikipedia-Sprachen).
* **widersprüchlich** – keine klare Mehrheit → Warnung; mit `--streng` entsteht dann kein Video.
* **nur eine Quelle** – keine unabhängige Vergleichsquelle gefunden (Hinweis im Prüfbericht).

Weitere Prüfsprachen: `set CUDI_CHECK_LANGS=en,de,fr,es,ru,ar,zh,ja,pt,hi`. Faktencheck-Suche:
kostenlosen Schlüssel für die „Fact Check Tools API“ (Google Cloud Console) als
`set CUDI_FACTCHECK_API_KEY=...` setzen.

## Vom Handy nutzen

**A) Zu Hause (gleiches WLAN):** `CUDI_VIDEO.bat` am PC starten – das Fenster zeigt die Adresse
fürs Handy an („Vom Handy im selben WLAN öffnen: http://192.168…:8000“). Vorher einen Zugangscode
setzen: `set CUDI_VIDEO_TOKEN=meinCode`.
Fragt die Windows-Firewall beim ersten Start nach Zugriff, „Zulassen“ (privates Netzwerk) wählen.

**B) Jederzeit und überall – als Cloud-App (kostenlos, Hugging Face Spaces):**
1. Kostenloses Konto auf huggingface.co → *Settings → Access Tokens* → Token mit **Write**-Recht anlegen.
2. Auf GitHub im Repository: *Settings → Secrets and variables → Actions* → Secrets `HF_TOKEN` (der Token)
   und `CUDI_VIDEO_TOKEN` (dein selbst gewählter Zugangscode) anlegen. Optional weitere Schlüssel
   (z. B. `CUDI_PEXELS_API_KEY`, `CUDI_LLM_API_KEY`) – sie werden in die App übernommen.
3. *Actions → „CUDI Cloud-App“ → Run workflow* (später automatisch bei jeder Änderung auf `main`).
4. Nach 3–5 Minuten läuft die App unter `https://<dein-name>-cudi-video.hf.space` (der Lauf zeigt die Adresse an).
   Der Space ist standardmäßig privat: am Handy einmal bei Hugging Face anmelden. Variable
   `HF_SPACE_PRIVATE=false` macht ihn öffentlich (die App bleibt durch den Zugangscode geschützt).
5. Die Adresse in der CUDI-App-Seite (Claude) unter „Volle App“ eintragen oder zum Startbildschirm hinzufügen.

Hinweis: Der kostenlose Space hat 2 CPU-Kerne (ein Video dauert dann einige Minuten), schläft nach
Inaktivität ein und speichert Videos nicht dauerhaft – fertige Videos also direkt herunterladen.

**C) Mit der CUDI-App-Seite in Claude (am bequemsten, alles in der App):** Die Seite
(Quelltext `docs/cudi-app-artefakt.html`) hat alle Optionen für Rankings und Storys. „… erstellen“
startet über den eingebauten Connector „Claude Code Remote“ einen Lauf der geplanten Aufgabe
„CUDI-Auftrag“ in der Claude-Cloud – solche Läufe erscheinen nicht als neue Sitzungen in deiner
Sitzungsliste (fehlt die Aufgabe, startet die App ersatzweise eine eigene Sitzung und archiviert sie
danach). Der Lauf führt `bash scripts/cudi_auftrag.sh '<auftrag>'` aus (`python -m cudi_video
auftrag`): prüft die Eingaben, rendert, erstellt eine App-Fassung ≤ 19 MB (1080×1920) und legt Video,
Titelbild, TikTok-/YouTube-Text, Hinweise und Prüfbericht in der Ablage der Seite ab. Unter „Videos“
siehst du den Fortschritt, schaust das Video an, speicherst es aufs Handy (Teilen-Menü) und kopierst
die Texte. Bei Storys zeigt die App zuerst das **Skelett** (Häkchen „Skelett vorher ansehen“): Titel,
Stimmung, jede Szene mit Text und Bildidee – ändern, Szenen löschen oder ergänzen, dann „Video
erstellen“. Ohne Häkchen entsteht das Video in einem Rutsch. Englische Storys für deutsche Videos übersetzt Claude im Auftrag selbst – ohne Schlüssel.
Jeder Auftrag läuft mit dem kleinsten Claude-Modell (Haiku) und zählt nur zu deinem Claude-Nutzungslimit – keine Zusatzkosten.

**D) Per GitHub (ohne Claude):** In der GitHub-App → *Actions* → „CUDI Video“ oder „CUDI Story“ →
*Run workflow* – oder ein Issue mit der Kennung `cudi-auftrag` anlegen (Ablauf „CUDI Auftrag“, das
Ergebnis kommt als Kommentar mit Download-Links). Die Abläufe müssen dafür auf `main` liegen.

## Einstellungen (Umgebungsvariablen)

| Variable | Wirkung |
|---|---|
| `CUDI_CHANNEL=@deinkanal` | Kanal-Name dezent oben im Video und im Abspann |
| `CUDI_VIDEO_TOKEN=…` | Zugangscode für die Web-Oberfläche |
| `CUDI_VOICE_DE`, `CUDI_VOICE_EN` | andere Stimme (Liste: `edge-tts --list-voices`) |
| `CUDI_VOICE_RATE=+8%` | Sprechtempo |
| `CUDI_CHECK_LANGS` | Wikipedia-Sprachen für den Abgleich |
| `CUDI_LLM_BASE_URL`, `CUDI_LLM_API_KEY`, `CUDI_LLM_MODEL` | optionales Sprachmodell |

### Optional: Sprachmodell

Ohne Sprachmodell funktioniert alles. Mit Modell klingen die Texte freier, und Themen außerhalb
der Tabelle oben werden versucht (mit geprüften Wikidata-IDs). Kostenlose Optionen (Limits der
Anbieter können sich ändern):

```bash
# Google Gemini (kostenloser API-Schlüssel über Google AI Studio)
set CUDI_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
set CUDI_LLM_API_KEY=...
set CUDI_LLM_MODEL=gemini-2.5-flash

# oder lokal und komplett offline mit Ollama
set CUDI_LLM_BASE_URL=http://localhost:11434/v1
set CUDI_LLM_MODEL=llama3.1
```

## Eigene Vorgaben

Vorgaben liegen als YAML in `presets/` (jede Zeile ist kommentiert). Ein Ranking ist immer:
*alle Objekte einer Wikidata-Klasse, sortiert nach einer Zahl-Eigenschaft*. `{count}` im Titel wird
durch die Anzahl der Plätze ersetzt.

Wichtige Felder: `class` / `extra_classes`, `property` (z. B. `P2048` Höhe), `order`,
`where` (z. B. `{"P30": "Q46"}` = Europa), `require_any`, `exclude_classes`, `exclude_props`,
`exclude_values` (z. B. `{"P30": ["Q51"]}` = nichts in der Antarktis), `min_value`, `extras`
(Zusatzinfos), `compare` (Vergleichsobjekt), `image_prop` (`P41` = Flaggen), `icon`, `hashtags`
(je Sprache: `{de: [...], en: [...]}`).

Eigene Hintergrundmusik: MP3 in `video_assets/music/` legen (nur lizenzfreie Musik). Tipp für
TikTok: ohne Musik exportieren und in der App einen aktuellen Sound hinzufügen – das hilft der Reichweite.

## Vor dem Hochladen (Plattformregeln)

* Prüfbericht lesen, Warnungen prüfen.
* Bei TikTok und YouTube die Kennzeichnung für KI-/synthetische Inhalte setzen, wo verlangt
  (KI-Stimme). Der Hinweis steht bereits in der Beschreibung.
* YouTube verlangt für die Monetarisierung eigenständige Inhalte: lieber abwechslungsreiche Themen
  als viele fast gleiche Videos.

## Reddit-Storys

Zweiter Modus neben den Rankings: aus Reddit-Storys werden fertig erzählte Videos – im Stil der
bekannten Story-Kanäle (Post-Karte am Anfang, große Wort-für-Wort-Untertitel, ein Bild oder Clip pro
Erzähl-Beat, leise Musik, lange Storys in Teilen mit Cliffhanger).

**So geht's (Web-Oberfläche → „📖 Reddit-Storys“):**

1. Stimmung antippen (👻 Gruselig, ⚡ Spannend, 😂 Lustig, 🔥 Drama, 😈 Rache, 💛 Herzerwärmend)
   oder beschreiben: „gruselige Story über einen Stalker im Wald“ – oder einen Reddit-Link einfügen.
2. **Storys finden** zeigt Vorschläge (Upvotes, Länge) – **Autopilot** macht direkt das fertige Video.
3. Das **Skelett** prüfen und anpassen: Lektorat-Notizen, Szenentexte, Suchbegriffe für Bilder/Clips,
   Stimmung. Dann **Video erstellen**.

Kommandozeile:

```bash
python -m cudi_video story "gruselige Story über einen Stalker im Wald"        # Autopilot
python -m cudi_video story --stimmung funny --suchen                           # nur Vorschläge
python -m cudi_video story https://www.reddit.com/r/tifu/comments/... --nur-skelett
python -m cudi_video story --ordner video_output/<ordner>                      # bearbeitetes Skelett rendern
```

**Erzählt je nach Stimmung:** Gruselig = tiefe Stimme, langsam, lange Pausen, dunkler Look mit
Filmkorn, dröhnende Klangfläche mit Herzschlag. Lustig = locker und schneller, knallige Farben,
gezupfte Musik. Drama, Rache, Spannung und Herzerwärmendes haben jeweils eigene Stimme, Musik und Look.
Die Musik erzeugt CUDI selbst – keine Lizenzfragen.

**Lektorat („Profi-Durchsicht“):** Edits, TL;DR und Meta-Sätze („sorry for formatting“) fliegen raus,
Abkürzungen (AITA, MIL, „(25F)“, „im“ → „I'm“) werden vorlesbar, die Story wird in Szenen und – wenn
nötig – Teile gegliedert. **Heikles wird umschrieben statt weggelassen** (Option „Heikles entschärfen“):
Kraftausdrücke und anzügliche oder belastende Stellen werden angedeutet statt ausgesprochen („we had
sex“ → „we got intimate“, „Sex hatten“ → „intim wurden“) – die Handlung bleibt gleich, und solche Storys
bleiben in der Auswahl. Nur von Reddit als NSFW markierte Posts werden nicht vorgeschlagen. Jede Änderung steht im Skelett und im Prüfbericht.
Inhaltlich wird nichts hinzugefügt; ein optionales Sprachmodell darf glätten und kürzen, seine Fassung
wird gegen das Original geprüft.

**Bilder und Clips** (Einstellung „Bilder“): *Videos bevorzugt* nutzt echte Stockvideos von Pexels
oder Pixabay (kostenloser Schlüssel nötig), sonst KI-Bilder mit Kamerafahrt, sonst frei lizenzierte
Fotos von Wikimedia Commons (mit Urheberangabe im Video). *Eigene Clips* nimmt Videos aus
`video_assets/backgrounds/` (z. B. eigene Gameplay-Aufnahmen; Unterordner je Stimmung möglich).

**Quellen:** Mit Reddit-Zugang live über die offizielle API, sonst das öffentliche Reddit, als
Ausweichweg das Archiv Arctic Shift (Upvotes dort nach ca. 36 Stunden aktuell). Deutsche
Drama-Storys kommen direkt aus r/BinIchDasArschloch, r/beziehungen und r/Ratschlag; andere
Stimmungen nutzen englische Storys und übersetzen sie (Sprachmodell, DeepL oder MyMemory).

| Variable (alle optional) | Wirkung |
|---|---|
| `CUDI_PEXELS_API_KEY` / `CUDI_PIXABAY_API_KEY` | echte Videoclips statt KI-Bilder (kostenlos: pexels.com/api, pixabay.com/api/docs) |
| `CUDI_REDDIT_CLIENT_ID` / `CUDI_REDDIT_CLIENT_SECRET` | Reddit live (reddit.com/prefs/apps → „script“-App) |
| `CUDI_POLLINATIONS_TOKEN` | KI-Bilder groß und ohne Logo (kostenloser Zugang: auth.pollinations.ai) |
| `CUDI_DEEPL_API_KEY` | Übersetzung englischer Storys für deutsche Videos (DeepL API Free) |
| `CUDI_STORY_MAX_SECONDS=179` | Höchstlänge je Teil |

**Rechte:** Die Storys gehören ihren Autoren. CUDI nennt Autor und Link im Video (Post-Karte) und in der
Beschreibung. **r/nosleep erlaubt Vertonungen nur mit Erlaubnis des Autors** – der Prüfbericht weist
darauf hin. Für monetarisierte Kanäle die Autoren am besten immer kurz anfragen. KI-Stimme und
KI-Bilder sind in der Beschreibung gekennzeichnet; bei YouTube/TikTok zusätzlich die Kennzeichnung für
KI-Inhalte setzen, wenn verlangt.

## Probleme?

`CUDI_VIDEO_TEST.bat` bzw. `python -m cudi_video check` ausführen. Der Selbsttest prüft ffmpeg,
Schriften, Pakete, die KI-Stimme und jede Datenquelle einzeln und nennt bei Fehlern die Lösung.
Fällt eine optionale Quelle aus (Wikipedia, Commons, Weltbank …), entsteht trotzdem ein Video –
nur mit weniger Bestätigungen bzw. Grafik statt Foto.

**Ausfallsicher – alles kostenlos:**

| Wenn … | dann … |
|---|---|
| der Microsoft-Sprachdienst (edge-tts) nicht antwortet | bis zu 6 Versuche (≈ 1 Minute), danach spricht die Offline-Stimme **Piper** das ganze Video (quelloffen, Modell einmalig von Hugging Face) – Hinweis im Ergebnis |
| das Reddit-Archiv ausfällt (Reddit selbst sperrt Cloud-Rechner) | Storys kommen über die öffentlichen **RSS-Feeds** von Reddit – auch für Links |
| eine Beschreibung keine Story findet | eine beliebte Story derselben Stimmung (Hinweis im Ergebnis) |
| eine vorübergehende Störung den Auftrag abbricht | der Auftrag wiederholt sich nach 60 s einmal selbst; scheitert der Lauf trotzdem oder endet ohne Ergebnis, startet die App ihn einmal automatisch neu („2. Versuch“) |
| die App-Ablage (1 GB) fast voll ist | die App startet nicht ins Leere, sondern bietet „Älteste Videos löschen und starten“ an |
| der Paketserver kurz gestört ist | Installation mit Pausen erneut |

## Aufbau

```
cudi_video/
  sources/wikidata.py   Ranking per SPARQL (neuester Wert je Objekt, Filter, Konsistenz-Check)
  verify/               Quellen-Abgleich (Weltbank, CIA Factbook, OSM, Wikipedia-Sprachen, Faktenchecks)
  topics.py             freie Themen ohne Sprachmodell (Stichwort-Planer)
  compare.py            belegte Vergleiche ("48-mal so groß wie Deutschland")
  enrich.py             Wikipedia-Einleitung, Commons-Bilder + Lizenz
  script.py             Sprechertext aus Daten, Faktenschutz, optionales Sprachmodell + Prüfung
  tts.py                KI-Stimme mit Wort-Zeitstempeln, Pausen-Straffung
  render/               Infografik-Szenen (Pillow) -> ffmpeg, Tonmischung, Untertitel, Icons
  metadata.py           Titel, Beschreibung, Hashtags, Prüfbericht
  story/                Reddit-Storys: Quelle, Stimmungen, Lektorat, Bilder/Clips, Musik, Render
  check.py              Selbsttest
  pipeline.py           alle Stufen; Zwischenergebnisse als JSON
  web/                  Web-Oberfläche (PC + Handy)
presets/                fertige Vorgaben
```

## Nächste Ausbaustufen

* Weitere Vergleichsquellen je Thema (z. B. UN-Statistik, Eurostat, nationale Statistikämter)
* Cartoon-/Figuren-Stil als zweites Design
* Längere Videos im Querformat (16:9) für YouTube
* Direkter Upload über die YouTube-API, Vorbereitung für die TikTok-API
