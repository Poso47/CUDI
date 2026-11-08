# Lernen: Experimente und Lern-Analyst einrichten

Ziel: mehrere Wege parallel laufen lassen und dort ausbauen, wo es besser funktioniert. Alles kostenlos, kein
Claude-Verbrauch.

## So funktioniert es

1. **Experimente** (`cudi_video/experimente.py`): Jedes Video bekommt je Stellschraube eine Variante – Format, Design
   (Farben), Bewegung, Musik-Stil, Maskottchen (an/aus). Gewählt wird per Bandit (Thompson Sampling) aus
   `firma_daten/lernen.json`; mindestens 20 % der Wahlen sind reine Erkundung. Feste Wünsche im Auftrag (Format, Design,
   Maskottchen) haben Vorrang. Die gewählten Varianten stehen in `ergebnis.json` (Feld `varianten`) und im Ergebnis-
   Dokument der App. Gleiches Video, gleiche Wahl (reproduzierbar). Ausschalten: `CUDI_EXPERIMENTE=0`.
   Hook-Typ und Längenziel sind vorbereitet (`KNOBS[..]["aktiv"]`), bis `retention.py` sie über `experimente.wunsch("hook")`
   liest.
2. **App-Bewertungen** 👍/👎 liegen in der Artefakt-Datenbank, die GitHub nicht lesen kann. Sie wirken deshalb direkt:
   Die App sendet mit jedem Auftrag `vorlieben.varianten_gut/_schlecht` (Varianten der zuletzt bewerteten Videos); jede
   Bewertung zählt wie zwei gemessene Videos. Es wird nichts committet.
3. **Lern-Analyst** (`cudi_video/firma/lernen.py`, Workflow „Firma · Lern-Analyst“, täglich): liest YouTube-/TikTok-Zahlen
   der hochgeladenen Videos und schreibt `firma_daten/lernen.json` (Gewichte, Gewinner, Begründung).
   - Zuordnung Video -> Varianten: `firma_daten/uploads.json`. Diese Liste schreibt **nur der Notbetrieb-Workflow** (Job
     „liste“ nach einem Upload), weil Claude-Läufe nicht committen dürfen. Uploads, die direkt aus der App (Claude-Lauf)
     oder per CLI am PC geschehen, fließen **nicht** in die Zahlen ein; für sie bleibt der Weg über die App-Bewertungen.
   - Ehrlich: Unter 8 gemessenen Videos bleibt es bei der Erkundung (`modus: "erkundung"`). Ein Gewinner braucht mindestens
     4 Videos je Variante und 10 Punkte Vorsprung in der Erfolgsquote. Erfolg = Reichweite je Tag (Aufrufe + 25 Likes +
     60 Kommentare + 80 Shares) im Vergleich zum Median derselben Plattform; Videos unter 2 Tagen zählen noch nicht.

## YouTube: Zahlen lesen

Der Upload-Scope `youtube.upload` reicht **nicht** zum Lesen (videos.list braucht `youtube.readonly` o. Ä.). Zwei Wege:

- **Nur öffentliche Videos:** einen API-Schlüssel (Google Cloud -> Anmeldedaten -> API-Schlüssel, YouTube Data API v3) als
  Secret `CUDI_YT_API_KEY` hinterlegen. Hochgeladene Videos sind anfangs oft **privat** (siehe `docs/upload-einrichten.md`)
  – dafür liefert der Schlüssel keine Zahlen.
- **Auch private/ungelistete Videos:** Token mit zusätzlichem Scope holen:
  1. Im OAuth-Zustimmungsbildschirm den Scope `…/auth/youtube.readonly` ergänzen.
  2. Am PC: `python -m cudi_video youtube-login --lesen` (fordert Upload **und** Lesen an).
  3. Den neuen Refresh-Token als Secret `CUDI_YT_REFRESH_TOKEN` ersetzen (nie in den Chat schreiben).

Ohne Lese-Zugang meldet der Analyst im Feld `hinweise`: „Scope youtube.readonly nötig …“ und bleibt bei der Erkundung.

## TikTok: Zahlen lesen

1. In der TikTok-Entwicklerseite (Sandbox/App) unter „Scopes“ **`video.list`** hinzufügen.
2. Am PC: `python -m cudi_video tiktok-login --lesen` (fordert `video.upload,video.list` an).
3. Den neuen Refresh-Token als Secret `CUDI_TIKTOK_REFRESH_TOKEN` ersetzen.

Hinweis: Uploads im Inbox-Modus sind Entwürfe ohne Video-Kennung. Der Analyst ordnet veröffentlichte Videos über den Text
(Beschreibung) zu; was sich nicht zuordnen lässt, zählt nicht.

## Prüfen

- `python -m cudi_video.firma lernen` (lokal, mit den gesetzten Variablen) schreibt `firma_daten/lernen.json`; im Feld
  `hinweise` steht, was fehlt.
- `lernen.json` und `uploads.json` enthalten keine Zugangsdaten, nur Kennungen, Zahlen und Variantennamen.
