# CUDI Video – Ranking-Faktenvideos für TikTok & YouTube Shorts

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
| Wikipedia EN, DE, FR, ES, RU, AR, ZH, JA | acht Sprachgemeinschaften | liest den Wert samt Einheit aus dem Text – kann bestätigen **oder widersprechen** |
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

**B) Unterwegs, kostenlos in der Cloud – Hugging Face Spaces:**
1. Auf huggingface.co einen neuen *Space* anlegen, SDK „Docker“, Sichtbarkeit „Private“.
2. Die Dateien `Dockerfile`, `.dockerignore`, `cudi_video/` und `presets/` hochladen (oder das Repo verbinden).
3. Unter *Settings → Variables and secrets* das Secret `CUDI_VIDEO_TOKEN` setzen (**wichtig**, sonst kann jeder rendern).
4. Space-Adresse am Handy öffnen, unter „Systemtest“ prüfen und als App zum Startbildschirm hinzufügen.

Hinweis: Der kostenlose Space hat 2 CPU-Kerne (ein Video dauert dann einige Minuten), schläft nach
Inaktivität ein und speichert Videos nicht dauerhaft – fertige Videos also direkt herunterladen.

**C) Per GitHub Actions:** In der GitHub-App → *Actions* → „CUDI Video“ → *Run workflow*, Vorlage wählen.
Nach ein paar Minuten liegt das Ergebnis als ZIP unter dem Lauf (*Artifacts*). (Der Workflow muss
dafür im Haupt-Branch liegen.)

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
`min_value`, `extras` (Zusatzinfos), `compare` (Vergleichsobjekt), `image_prop` (`P41` = Flaggen),
`icon`.

Eigene Hintergrundmusik: MP3 in `video_assets/music/` legen (nur lizenzfreie Musik). Tipp für
TikTok: ohne Musik exportieren und in der App einen aktuellen Sound hinzufügen – das hilft der Reichweite.

## Vor dem Hochladen (Plattformregeln)

* Prüfbericht lesen, Warnungen prüfen.
* Bei TikTok und YouTube die Kennzeichnung für KI-/synthetische Inhalte setzen, wo verlangt
  (KI-Stimme). Der Hinweis steht bereits in der Beschreibung.
* YouTube verlangt für die Monetarisierung eigenständige Inhalte: lieber abwechslungsreiche Themen
  als viele fast gleiche Videos.

## Probleme?

`CUDI_VIDEO_TEST.bat` bzw. `python -m cudi_video check` ausführen. Der Selbsttest prüft ffmpeg,
Schriften, Pakete, die KI-Stimme und jede Datenquelle einzeln und nennt bei Fehlern die Lösung.
Fällt eine optionale Quelle aus (Wikipedia, Commons, Weltbank …), entsteht trotzdem ein Video –
nur mit weniger Bestätigungen bzw. Grafik statt Foto.

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
