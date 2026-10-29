# CUDI Video – Ranking-Faktenvideos für TikTok & YouTube Shorts

CUDI Video erstellt kostenlos animierte **Top-10-Faktenvideos** (Hochformat 1080×1920, bis 3 Minuten)
auf **Deutsch und Englisch**. Die Fakten kommen live aus Wikidata/Wikipedia, die Stimme ist eine
kostenlose KI-Stimme (edge-tts), die Animation ist eine Infografik mit Countdown, hochzählenden
Werten, Bildern und Karaoke-Untertiteln.

Pro Video entstehen:

| Datei | Wozu |
|---|---|
| `<id>_de.mp4` / `<id>_en.mp4` | fertiges Video |
| `<id>_de_beschreibung.txt` | Titel + Beschreibung mit Ranking, Quellen, Bildnachweisen, KI-Hinweis, Hashtags |
| `<id>_de_cover.jpg` | Vorschaubild |
| `<id>_de.srt` | Untertitel zum Hochladen (YouTube) |
| `review.md` | **Prüfbericht** – vor dem Hochladen lesen |

## Grundsatz: nichts erfinden

* **Zahlen nur aus Wikidata.** Pro Eintrag wird der neueste gültige Wert genommen (Stichtag `P585`),
  veraltete Werte (deprecated) werden ignoriert, der Stichtag wird im Video gezeigt („Stand 2014“).
* **Wikipedia-Sätze nur wörtlich** und nur, wenn sie keine eigenen Zahlen, Rangaussagen
  („elfthöchste“) oder zeitabhängigen Aussagen („derzeit“) enthalten – die könnten unseren Daten widersprechen.
* **Optionales Sprachmodell** darf nur umformulieren. Sein Text wird automatisch geprüft
  (jede Zahl muss in den Quelldaten stehen + zweiter Faktencheck) und sonst verworfen.
* **Prüfbericht** warnt z. B. bei Werten aus unterschiedlichen Jahren, Gleichständen oder fehlenden Bildern.
* **Bilder nur mit freier Lizenz** von Wikimedia Commons; Urheber und Lizenz stehen im Video und in der Beschreibung.

## Schnellstart am Windows-PC

1. Python 3.11+ installieren (python.org, Haken bei „Add to PATH“).
2. ffmpeg installieren: `winget install Gyan.FFmpeg`
3. `CUDI_VIDEO.bat` doppelklicken → Browser öffnet sich auf http://localhost:8000

Kommandozeile:

```bash
pip install -r cudi_video/requirements.txt
python -m cudi_video presets                         # Vorlagen anzeigen
python -m cudi_video make hoechste-gebaeude          # Video DE + EN
python -m cudi_video make hoechste-berge --langs de --count 5
python -m cudi_video make hoechste-gebaeude --nur-skript   # erst nur Skript + Prüfbericht
python -m cudi_video web                             # Web-Oberfläche
```

## Vom Handy nutzen

**A) Zu Hause (gleiches WLAN):** `CUDI_VIDEO.bat` am PC starten, am Handy `http://<IP-des-PCs>:8000`
öffnen (IP mit `ipconfig`). Vorher einen Zugangscode setzen: `set CUDI_VIDEO_TOKEN=meinCode`.

**B) Unterwegs, kostenlos in der Cloud – Hugging Face Spaces:**
1. Auf huggingface.co einen neuen *Space* anlegen, SDK „Docker“, Sichtbarkeit „Private“.
2. Die Dateien `Dockerfile`, `.dockerignore`, `cudi_video/` und `presets/` hochladen (oder das Repo verbinden).
3. Unter *Settings → Variables and secrets* das Secret `CUDI_VIDEO_TOKEN` setzen (**wichtig**, sonst kann jeder rendern).
4. Space-Adresse am Handy öffnen und als App zum Startbildschirm hinzufügen.

Hinweis: Der kostenlose Space hat 2 CPU-Kerne (ein Video dauert dann einige Minuten), schläft nach
Inaktivität ein und speichert Videos nicht dauerhaft – fertige Videos also direkt herunterladen.

**C) Per GitHub Actions:** In der GitHub-App → *Actions* → „CUDI Video“ → *Run workflow*, Vorlage wählen.
Nach ein paar Minuten liegt das Ergebnis als ZIP unter dem Lauf (*Artifacts*).

## Optional: Sprachmodell für flüssigere Texte und freie Themen

Ohne Sprachmodell funktioniert alles mit Vorlagen. Mit Modell klingen die Texte natürlicher und
im Tab „Freies Thema“ kann man z. B. „die größten Stadien der Welt“ eintippen. Kostenlose Optionen
(Limits der Anbieter können sich ändern):

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

Vorgaben liegen als YAML in `presets/`. Jede Zeile ist erklärt, z. B. `presets/hoechste-gebaeude.yaml`.
Ein Ranking ist immer: *alle Objekte einer Wikidata-Klasse, sortiert nach einer Zahl-Eigenschaft*.
`{count}` im Titel wird durch die Anzahl der Plätze ersetzt.

Wichtige Felder: `class` (z. B. `Q11303` Wolkenkratzer), `property` (z. B. `P2048` Höhe),
`require_props` (z. B. nur eröffnete Gebäude), `exclude_classes`, `country` (z. B. `Q183` nur Deutschland),
`min_value`, `extras` (Zusatzinfos wie Land, Jahr, Stockwerke).

Eigene Hintergrundmusik: MP3 in `video_assets/music/` legen (nur lizenzfreie Musik, z. B. YouTube Audio Library).
Sie wird automatisch leiser, während gesprochen wird.

## Vor dem Hochladen (Plattformregeln)

* `review.md` lesen, Warnungen prüfen.
* Bei TikTok und YouTube die Kennzeichnung für KI-/synthetische Inhalte setzen, wo verlangt
  (KI-Stimme). Der Hinweis steht bereits in der Beschreibung.
* Für die Monetarisierung verlangt YouTube eigenständige Inhalte: lieber abwechslungsreiche Themen
  als viele fast gleiche Videos.

## Aufbau

```
cudi_video/
  sources/wikidata.py   Ranking per SPARQL (neuester Wert je Objekt, Filter, Konsistenz-Check)
  enrich.py             Wikipedia-Einleitung, Commons-Bilder + Lizenz (optional)
  script.py             Sprechertext aus Daten, Faktenschutz, optionales Sprachmodell + Prüfung
  tts.py                KI-Stimme mit Wort-Zeitstempeln, Pausen-Straffung
  render/               Infografik-Szenen (Pillow) -> ffmpeg, Tonmischung, Untertitel
  metadata.py           Titel, Beschreibung, Hashtags, Prüfbericht
  pipeline.py           alle Stufen; Zwischenergebnisse als JSON
  web/                  Web-Oberfläche (PC + Handy)
presets/                fertige Vorgaben
```

## Nächste Ausbaustufen

* Mehr Datenquellen (Wikipedia-Tabellen, offizielle Statistiken) und Abgleich zweier Quellen
* Cartoon-/Figuren-Stil als zweites Design
* Längere Videos im Querformat (16:9) für YouTube
* Direkter Upload über die YouTube-API, Vorbereitung für die TikTok-API
