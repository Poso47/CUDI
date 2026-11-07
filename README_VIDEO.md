# CUDI Video – Ranking-Faktenvideos und Reddit-Storys für TikTok & YouTube Shorts

CUDI Video erstellt kostenlos animierte **Top-10-Faktenvideos** (Hochformat 1080×1920, höchstens
3 Minuten) auf **Deutsch und Englisch** – aus einer Vorlage oder einem frei eingetippten Thema wie
„die höchsten Wasserfälle Südamerikas“. Jeder Wert wird vorher mit unabhängigen Quellen aus
verschiedenen Ländern abgeglichen.

Pro Video entstehen:

| Datei | Wozu |
|---|---|
| `<id>_de.mp4` / `<id>_en.mp4` | fertiges Video (Lautheit auf ca. −14 LUFS normalisiert) |
| `<id>_de_beschreibung.txt` | YouTube: Titel + Beschreibung mit Ranking, Bildnachweisen, Lizenz- und KI-Hinweis, Hashtags (Quellen nur im Prüfbericht) |
| `<id>_de_tiktok.txt` | TikTok: kurzer Text mit KI-Hinweis und Hashtags |
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

**In der CUDI-App** deutet Claude auch Themen außerhalb dieser Liste („die längsten Brücken Deutschlands“):
Klasse, Zahl-Eigenschaft und Region werden gegen Wikidata geprüft, dann läuft der normale Quellen-Abgleich.
Dort erzählt Claude das Ranking außerdem als kleine Geschichte – jeder Text wird geprüft (geprüfter Wert,
keine Zahl und kein Hauptwort ohne Beleg), sonst gilt der Textbaustein.

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

## Fakten-Rankings – jedes Thema ist rankbar

Lässt sich ein Wunsch nicht mit einer Zahl sortieren („5 coole Fakten über das Unterbewusstsein“, „Gründe,
warum …“, „Mythen über …“), wird er zum **Fakten-Ranking** im gewohnten Aussehen (`cudi_video/facts.py`):

1. Claude wählt 1–3 passende Fachartikel je Sprache, der Code lädt deren Text.
2. Claude schreibt daraus die Fakten – je Fakt mit einem **wörtlich kopierten Beleg-Satz** und einer Bildsuche.
3. Der Code prüft jeden Fakt: Beleg steht so in der Quelle, jede Zahl im Text steht im Beleg **und in einer
   zweiten Quelle**, keine erfundenen Namen/Hauptwörter, keine Wertungen, Länge passt. Deutsche Alltagswörter
   („Gehirn“, „Wünsche“ – auch zu einem englischen Beleg) erlaubt eine Häufigkeitsliste
   (`cudi_video/wortlisten/`, 50 000 Wörter, FrequencyWords von Hermit Dave, CC BY-SA 4.0) – auch gebeugt und zusammengesetzt („Faustregel“); Wörter, die es genauso im Englischen
   gibt (Eigennamen wie „Harvard“), bleiben belegpflichtig. Abgelehnte Fakten gehen **einmal mit Grund zur
   Korrektur** an Claude zurück; wer dann noch durchfällt, fliegt raus (Claude liefert drei Fakten mehr als
   nötig); weniger als bestellt → ehrliche Top N.
4. Karten zeigen die Kernaussage statt Zahl und Balken, dazu Stockclips/-fotos zur Bildsuche; Spannungsbogen,
   Maskottchen, Prüfbericht (mit Beleg und Quelle je Platz) wie bei Zahlen-Rankings.

## Themen-Wissensstruktur (alle Videos)

Jedes Video dreht sich um den **Themenkern** (`cudi_video/themen.py`): Beim Deuten des Wunsches legt Claude die
eigentliche Zuschauerfrage fest („Wie steuert mein Unterbewusstsein, was ich tue und fühle?“), 3–6 **Aspekte**
und was **nicht gemeint** ist (z. B. Begriffsgeschichte, Biografien). Fakten-Rankings laden je Aspekt einen
spezifischen Fachartikel (Priming, Gewohnheit, Intuition …) statt nur des Oberbegriffs. Jede Schreibaufgabe
(Fakten, Ranking-Erzählung, Story-Lektorat) erzählt nach derselben **Wissensstruktur**: Aufhänger → Kernaussage →
Erklärung (wie/warum) → Bedeutung für dich. Die Prüfung verwirft Fakten ohne Aspekt aus dem Themenkern und zu
knappe Texte (Korrekturrunde); weitere wörtliche Belege („belege“) stützen die Erklärung. Der Prüfbericht zeigt
Themenkern, Aspekt und alle Belege je Platz.

## Formate und Farben – jedes Video sieht anders aus

Ranking- und Fakten-Videos wechseln das ganze **Format** (`cudi_video/render/formats.py`) – Bildaufbau, Formen,
Zooms, Übergänge, Intro und Abschluss:

**Schriften je Format** (`theme.FORMAT_FONTS`, Dateien in `video_assets/fonts/`): vollbild und zahl Anton, kreis Poppins
(ExtraBold/Bold), magazin Playfair Display Black, polaroid Archivo Black + Rang in Handschrift (Caveat Bold), karte Inter.
Untertitel nutzen die fette Format-Schrift. Alle SIL Open Font License 1.1 (`*-OFL.txt` daneben); fehlt eine Datei,
gilt still die bisherige Schrift.

| Format | Platz | Übergang / Zoom | Intro | Abschluss |
|---|---|---|---|---|
| Karte | Bildkarte oben, Text darunter, Abzeichen an der Ecke | 4 Bewegungsprofile (`MOTIONS`) | Titel + „?“-Karte | Liste |
| Vollbild | Clip/Foto über den ganzen Bildschirm, Text auf Schatten | Punch-in-Zoom | Kino-Vorspann mit Letterbox | Liste |
| Kreis | Bild im Kreis, Fortschrittsring = Wert, Rang-Blase | Iris-Blende, Kreis springt auf | „?“ im drehenden Ring | Siegerpodest |
| Magazin | Bild oben mit schräger Kante, riesige Umriss-Ziffer, Farbbalken | Wischbalken, Ziffer zoomt heran | Riesen-„05“ + Titel mit Balken | Liste |
| Polaroid | Sofortbild mit Klebestreifen, Stapel dahinter | Kamerablitz, Bild fällt und dreht sich | fallender Bilderstapel | Siegerpodest |
| Riesenzahl | Clip läuft IN der Platz-Ziffer | Ziffer zoomt aus dem Bild heran | riesige Zahl im Farbverlauf | Siegerpodest |

Die **Farben** (`render/theme.py`, `STYLES`: Neon, Natur, Kino, Doku, Ozean, Pop, Minimal – mit Hintergrund,
Untertitel-Stil und Effekt wie Filmkorn, Lichtpunkten, Lichtstrahlen) passen sich dem **Thema** an
(Themenwörter im Titel, sonst Vorlagen-Icon; z. B. Meer → Ozean/Natur, Geschichte → Doku/Kino/Minimal).
Format, Farben und Bewegung werden je Video fest aus der Video-ID gewählt; in der App lässt sich das Format im
Feld „Format“ festlegen (Auftrag `format`).

## Themen-Wissensstruktur (alle Videos)

Jedes Video dreht sich um den **Themenkern** (`cudi_video/themen.py`): Beim Deuten des Wunsches legt Claude die
eigentliche Zuschauerfrage fest („Wie steuert mein Unterbewusstsein, was ich tue und fühle?“), 3–6 **Aspekte**
und was **nicht gemeint** ist (z. B. Begriffsgeschichte, Biografien). Fakten-Rankings laden je Aspekt einen
spezifischen Fachartikel (Priming, Gewohnheit, Intuition …) statt nur des Oberbegriffs. Jede Schreibaufgabe
(Fakten, Ranking-Erzählung, Story-Lektorat) erzählt nach derselben **Wissensstruktur**: Aufhänger → Kernaussage →
Erklärung (wie/warum) → Bedeutung für dich. Die Prüfung verwirft Fakten ohne Aspekt aus dem Themenkern und zu
knappe Texte (Korrekturrunde); weitere wörtliche Belege („belege“) stützen die Erklärung. Der Prüfbericht zeigt
Themenkern, Aspekt und alle Belege je Platz.

## Designs – jedes Video sieht anders aus

Ranking- und Fakten-Videos haben **7 Designs** (`cudi_video/render/theme.py`, `STYLES`): Neon, Natur, Kino, Doku,
Ozean, Pop, Minimal. Jedes bringt eigene Farben, Hintergrund (Lichtflecken, unscharfes Vollbild-Foto des Platzes
oder schlicht), Untertitel-Stil (farbiger Kasten, Umriss oder Farbe), Effekt (Lichtpartikel, Lichtstrahlen,
Filmkorn) und Layout mit – **Kino** und **Natur** zeigen Clip/Foto im **Vollbild**, Text unten auf Schatten. Dazu
kommt unabhängig eines von 4 **Bewegungsprofilen** (`MOTIONS`: gleiten, aufsteigen, zoom, schwung – wie Karte,
Titel, Rang-Abzeichen und Abschlussliste hereinkommen, wohin das Foto schwenkt). Ohne Wahl passt das Design zum
Thema (`STYLE_FIT`, z. B. Berge → Natur/Kino/Doku/Minimal) und wechselt je Video (fest aus der Video-ID); in der
App lässt es sich im Feld „Design“ wählen (Auftrag `design`).

## Bild passt zum Fakt und Aha-Effekt

- **Bildpassung:** Claude liefert je Fakt `motiv` (das konkrete sichtbare Objekt, englisch, z. B. „shark teeth“) und `suche`
  (2–3 Alternativen). Ein Treffer zählt nur, wenn ALLE Kernwörter des Motivs in seiner Beschreibung stehen (Pexels-Adresse/alt,
  Pixabay-Tags, Commons-Titel; Singular/Plural egal). Reihenfolge: Clip → Foto → Commons-Bild → zuletzt „Stimmungsbild“
  (nur mit dem Hauptthema, im Prüfbericht: „Bild zeigt nicht genau den Fakt“). Der Prüfbericht nennt je Fakt Motiv und Passung.
- **Visuelle Prüfung (`bildcheck.py`):** Tags lügen („shark“ im Tag, im Bild nur Wasser). Darum vergleicht ein kostenloses
  CLIP-Modell (open_clip ViT-B-32, CPU, Cache `video_output/_models`) je Kandidat 3 Bilder (20/50/80 %) mit dem Motiv und
  Gegenproben (Ozean, Person, Text); es zählt, wenn das Motiv in ≥ 2 von 3 Bildern ≥ 50 % hat; der beste Kandidat gewinnt
  (Tags sind nur lockerer Vorfilter: Hauptwort). Ranking-Clips (`media.find_clips`) werden danach nur *sortiert*. Das Modell wird bei
  Bedarf nachinstalliert (torch CPU, ~250 MB); fällt es aus, bleibt es still beim strengen Tag-Abgleich. Aus: `CUDI_BILDPRUEFUNG=0`.
- **Aha-Effekt für alle Videos:** jeder Platz/jede Szene bringt etwas Überraschendes, das man vorher nicht wusste. Fakten haben
  `aha_<sprache>` (gleiche Prüfungen wie der Text); der Aha-Satz von Platz 1 wird als „Heute gelernt: …“ gesprochen,
  bei Zahlen-Rankings der Spitzenwert.

## Direkt hochladen (YouTube Shorts / TikTok)

`python -m cudi_video hochladen <video.mp4|auftrag-id> --ziel youtube|tiktok|beide [--sichtbarkeit privat] [--probe]` –
Zugangsdaten nur als Umgebungsvariablen, Einrichtung in `docs/upload-einrichten.md`. TikTok lädt standardmäßig in die Inbox (Entwurf).

## Spannungsbogen (Zuschauer bleiben dran)

Jedes Video folgt einem psychologisch aufgebauten Bogen (`cudi_video/retention.py`), passend zu Format und Thema –
mit ehrlicher Spannung statt Köder (alle Zahlen bleiben geprüft):

* **Aufhänger mit Neugierlücke** (Loewenstein 1994): Der Rekordwert wird genannt, aber nicht, wem er gehört
  („Stell dir vor: 828 Meter! Genau so viel schafft Platz eins …“); Varianten wechseln je Video.
* **Zwischen-Aufhänger**: am Anfang („Aber das ist erst der Anfang.“), vor den Top 3, etwa alle drei Plätze und vor
  der Auflösung – dort aus den geprüften Werten berechnet („Nur noch 149 Meter trennen Platz zwei von Platz eins.“).
  Beim Kürzen fallen sie zuerst weg (der Abstand zu Platz 1 bleibt am längsten).
* **Erzählte Texte**: Bild im Kopf zuerst, direkte Ansprache, kurze Sätze, Sinneseindrücke.
* **Schluss**: Höhepunkt, dann eine Kommentarfrage zum Thema („Welchen dieser Berge würdest du besteigen?“).
* **Storys**: Einstieg mitten im spannendsten Moment, jede Szene endet offen, Auflösung zuletzt – je Stimmung
  eigene Regeln (Grusel: Andeutungen; Humor: Pointe am Satzende; Drama: Gefühle zeigen statt benennen …).

**Eigene Themen in einfachen Sätzen** („mach was über Wüsten in Afrika“, „Top 7 längste Flüsse“): Eine Zahl im
Satz bestimmt die Anzahl der Plätze. Unbekannte Themen deutet Claude wie ein Redakteur – nicht messbare Wünsche
(„gefährlichste“, „schönste“) werden ehrlich in die nächstliegende messbare Zahl übersetzt; die Deutung steht
im Prüfbericht. Danach läuft der volle Quellen-Abgleich.

## Bilder und Videoclips in Rankings

Jeder Platz bekommt nach Möglichkeit **echte Videoclips**: bis zu 3 kurze Ausschnitte, die in der Bildkarte
nacheinander laufen. Bildnachweise stehen im Video und in der Beschreibung. Quellen in dieser Reihenfolge,
alle kostenlos:

1. **Pexels-Videos** und **Pixabay-Videos** (HD, kommerziell frei; brauchen einen kostenlosen Schlüssel)
2. **NASA Image and Video Library** (gemeinfrei, ohne Schlüssel)
3. **Wikimedia Commons-Videos** (freie Lizenz mit Urheber; aus Rechenzentren oft gedrosselt)

Ohne Clip zeigt die Karte das beste freie Foto mit Zoom: Wikidata-/Wikipedia-Foto von Commons; ist es
gesperrt, ohne Urheber oder kleiner als 1200 px, dann **Openverse** (Flickr u. a., nur Lizenzen mit
kommerzieller Nutzung und Bearbeitung) und **NASA**. Ein Bild oder Clip zählt nur, wenn die unterscheidenden
Wörter des Namens im Titel/den Schlagworten stehen (keine fremde Brücke unter falschem Namen); Karten, Logos
und Wappen werden aussortiert. Es zählt der spezifischste Name („Abraj Al Bait“ statt „The Clock Towers“); bei
nur einem unterscheidenden Wort muss zusätzlich die Art passen („Nile“ + „river“ – nicht „Lily of the Nile“) bzw.
der ganze Name als Wortfolge in einem Schlagwort stehen („Yellow River“ – keine gelbe Straßenbahn am Fluss).

**Freie Themen ohne Lücken:** Fehlt einem Platz die unabhängige Bestätigung, endet das Ranking davor (ehrliche
Top 4 statt einer Top 5, in der Platz 5 gar nicht der Fünfte ist). Liegt die Lücke ganz oben, werden nur
bestätigte Werte gezeigt und der Titel behauptet keine Vollständigkeit („5 der längsten …“).

## Quellen-Abgleich

| Quelle | Herkunft | prüft |
|---|---|---|
| Wikidata | weltweite Community | Ausgangswert |
| Weltbank | internationale Organisation | Fläche, Einwohner von Staaten |
| CIA World Factbook | US-Regierung | Fläche, Einwohner von Staaten |
| OpenStreetMap | weltweite Kartografie-Community | Gebäude- und Berghöhen |
| Wikipedia EN, DE, FR, ES, RU, AR, ZH, JA | acht Sprachgemeinschaften | liest den Wert samt Einheit aus der Einleitung, sonst aus der Infobox – kann bestätigen **oder widersprechen** |
| Webseiten aus den Einzelnachweisen | Fachdatenbanken (Skyscraper Center, Peakbagger …), Behörden, Lexika, Presse | Wikipedia ist nur das Verzeichnis: bis zu 6 verlinkte Seiten je Platz werden selbst geladen; zählt nur, wenn die Seite den Wert (± 0,2 %) nennt. Fehlt eine Quelle außerhalb Wikipedias, warnt der Prüfbericht. Abschalten: `CUDI_CHECK_WEB=0` |
| Google Fact Check Tools (optional) | Faktencheck-Redaktionen (Correctiv, AFP, Snopes …) | gibt es Faktenchecks zum Eintrag? |

Ergebnis je Platz (nur im Prüfbericht mit allen Werten und Links – die Quellen sind für uns, nicht fürs Publikum):

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
| `CUDI_VOICE_RATE=+0%` | Grundtempo (Standard normal; Betonung variiert es je Satzteil, siehe `tts.plan_parts`) |
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
wird gegen das Original geprüft. **In der CUDI-App lektoriert Claude kostenlos:** Erzählstil je Stimmung,
heikle Stellen umschrieben, ein packender **Einstieg** für die ersten Sekunden (im Skelett-Editor
änderbar), ein neugierig machender Titel und Bildideen je Szene. Jede Szene wird geprüft (keine neuen
Zahlen oder Namen, sinnvolle Länge) – sonst gilt für sie die Regel-Fassung.

**Maskottchen „CUDI“** (Häkchen in der App, Standard an; `CUDI_MASCOT=0` schaltet es ab): ein kleiner
Roboter unten mittig, der synchron zur Stimme den Mund bewegt, blinzelt und leicht wippt – in Rankings
und Storys, kostenlos mit Pillow gezeichnet (`cudi_video/mascot.py`).

**Cartoon** (Einstellung „Bilder: Cartoon“): KI-Bilder im Zeichentrick-Stil mit gleichem Seed, und überall,
wo eine Person vorkommt, dieselbe Hauptfigur (Aussehen aus dem Lektorat oder passend zur Erzählstimme,
im Skelett-Editor änderbar).

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
| `CUDI_PEXELS_API_KEY` / `CUDI_PIXABAY_API_KEY` | echte Videoclips statt KI-Bilder – in Storys **und** in Rankings (kostenlos: pexels.com/api, pixabay.com/api/docs) |
| `CUDI_RANKING_CLIPS=0` | Rankings ohne Videoclips (nur Fotos mit Zoom) |
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

## Clip-Engine (Podcast-/Streamer-Clips)

`python -m cudi_video clip <datei-oder-url> [--start s --ende s] [--sprache de] [--laenge 90]` erzeugt
`video_output/clips/<name>/clip.mp4` (1080×1920, 30 fps, ≤ 179 s) und `clip.json`. Ablauf: faster-whisper (Wörter mit Zeiten,
als JSON zwischengespeichert) → bestes 30–90-s-Fenster nach Regeln (Fragen, Konfliktwörter, Lautstärke, Tempo, Pointe) →
Hook (Cold Open + 0,15-s-Blitz, wenn er nicht am Anfang steht) → Pausen > 0,35 s heraus → Sprecher-Zuschnitt (Haar-Kaskade,
Bewegung im Mundbereich; braucht `opencv-python-headless` 4.x, in 5.x fehlen die Kaskaden → Bildmitte) → Untertitel
(Anton aus `video_assets/fonts`, 1–3 Wörter, Großbuchstaben, Schlüsselwort #FFD400). Code: `cudi_video/clip/`.
