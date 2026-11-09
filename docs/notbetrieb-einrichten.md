# Notbetrieb einrichten (wenn dein Claude-Nutzungslimit erreicht ist)

Claude bleibt der Motor der CUDI-App. Der Notbetrieb ist nur eine Stütze: Ist das Limit erreicht, zeigt die
App-Seite den Banner **„Claude-Limit erreicht – Notbetrieb nutzen“**. Der Knopf **„Notbetrieb öffnen“** öffnet
GitHub mit einem vorausgefüllten Issue; du tippst dort nur **„Submit new issue“**. GitHub Actions rendert das Video
(das Repository `Poso47/CUDI` ist öffentlich, deshalb kostenlos), ein **freies Sprachmodell** schreibt die Texte –
mit derselben Anleitung und denselben Prüfregeln wie bei Claude (Zahlen nur mit Beleg, keine erfundenen Wörter,
Textbausteine als Ausweichweg). Hugging Face wird nicht mehr gebraucht (Docker-Spaces verlangen dort ein PRO-Abo).

## 1. Gemini-API-Schlüssel (kostenlos)

1. [aistudio.google.com](https://aistudio.google.com) mit einem Google-Konto öffnen → **Get API key** →
   **Create API key**.
2. Schlüssel kopieren. Die kostenlose Stufe hat Mengenlimits (Stand 2026, können sich ändern); für ein paar
   Videos pro Tag reicht sie.

## 2. Secrets auf GitHub eintragen

GitHub → Repository `Poso47/CUDI` → **Settings → Secrets and variables → Actions → New repository secret**.
Je Eintrag Name und Wert genau so:

| Secret | Wert |
|---|---|
| `CUDI_LLM_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `CUDI_LLM_API_KEY` | der Gemini-Schlüssel aus Schritt 1 |
| `CUDI_LLM_MODEL` | `gemini-2.5-flash` (der Name, den auch `README_VIDEO.md` nennt; bei Änderungen bei Google den aktuellen kostenlosen Flash-Namen aus AI Studio nehmen) |

**Ausweichanbieter (optional, kostenlos):** Meldet Gemini das Limit (HTTP 429), wartet der Lauf kurz, versucht es noch
einmal und nimmt dann den nächsten Anbieter. Trage dafür bis zu zwei weitere Sätze Secrets ein (nur Anleitung, keine
Schlüssel im Repository):

| Secret | Beispiel Groq (Schlüssel auf console.groq.com) | Beispiel OpenRouter (openrouter.ai, Modelle mit `:free`) |
|---|---|---|
| `CUDI_LLM2_BASE_URL` | `https://api.groq.com/openai/v1` | `https://openrouter.ai/api/v1` |
| `CUDI_LLM2_API_KEY` | dein Groq-Schlüssel | dein OpenRouter-Schlüssel |
| `CUDI_LLM2_MODEL` | `llama-3.3-70b-versatile` | ein Modell mit `:free` am Ende |

Ein dritter Anbieter geht genauso mit `CUDI_LLM3_*`. Modellnamen und Limits ändern sich – den aktuellen kostenlosen
Namen beim Anbieter nachsehen. Fällt die ganze Kette aus, gelten die Regelwege und Textbausteine (nie ein Abbruch);
nur **Fakten-Videos** brauchen zwingend ein Sprachmodell und enden sonst ehrlich mit einer Meldung.

Optional, je nachdem was du nutzt (nur gesetzte Secrets wirken, nichts davon erscheint in Ausgaben):

- Echte Videoclips: `CUDI_PEXELS_API_KEY`, `CUDI_PIXABAY_API_KEY`
- Hochladen zu YouTube: `CUDI_YT_CLIENT_ID`, `CUDI_YT_CLIENT_SECRET`, `CUDI_YT_REFRESH_TOKEN`
- Hochladen zu TikTok: `CUDI_TIKTOK_CLIENT_KEY`, `CUDI_TIKTOK_CLIENT_SECRET`, `CUDI_TIKTOK_REFRESH_TOKEN`

Den Zugang zu YouTube und TikTok richtest du nach `docs/upload-einrichten.md` ein. Hochladen ist
standardmäßig **aus**; es passiert nur, wenn der Auftrag es wünscht.

Ein Hugging-Face-Token und `CUDI_VIDEO_TOKEN` sind **nicht** nötig. Der alte Weg über den Space (Workflow
„CUDI Cloud-App“) bleibt als Option, läuft aber nur noch von Hand und überspringt sich freundlich ohne `HF_TOKEN`
oder bei „402 PRO nötig“.

## 3. Ablauf vom Handy

Voraussetzung: Du bist in der GitHub-App oder im Browser bei GitHub angemeldet (als Besitzer des Repositorys).

1. In der CUDI-App erscheint bei erreichtem Limit der Banner. Tippe **„Notbetrieb öffnen“**.
2. GitHub öffnet „New issue“ mit Titel `CUDI-Auftrag (Notbetrieb): …` und dem Auftrag als JSON-Block
   (Kennung `cudi-auftrag`). Tippe **„Submit new issue“**.
3. Der Ablauf „CUDI Auftrag“ prüft den Auftrag (nur Besitzer/Mitarbeitende) und startet „CUDI Notbetrieb“. Das
   Issue bekommt sofort den Kommentar „Auftrag angenommen“.
4. Nach 10 bis 30 Minuten steht im Issue der Ergebniskommentar: Titel, Dauer, YouTube-Titel/Beschreibung/Hashtags,
   TikTok-Text, Upload-Ergebnis (Link oder Fehler), Hinweise und der Prüfbericht in Kurzform – dazu der Link zum
   **Artefakt** mit den Videos (14 Tage, Download nur mit GitHub-Anmeldung; am Handy ggf. im Browser öffnen).
   Bei Erfolg wird das Issue geschlossen, bei einem Fehler bleibt es offen und der Kommentar nennt den Grund.

Den Auftrag kannst du auch von Hand schreiben: Issue mit der Zeile `cudi-auftrag` und einem Codeblock
```` ```json ```` mit z. B. `{"art":"ranking","thema":"die größten Wüsten","plaetze":10,"sprachen":["de","en"]}`
oder `{"art":"story","stimmung":"creepy","sprache":"de"}`. Erlaubt sind dieselben Felder wie in der App
(`job.parse_order`: Vorlage/Thema, Plätze, Sprachen, Format, Länge, Stimmung, Bilder, `hochladen` …).

## Hochladen im Notbetrieb

Es gibt im Notbetrieb keinen „Veröffentlichen“-Knopf in der App. Steht im Auftrag `hochladen`
(`{"ziel":"youtube","sichtbarkeit":"privat"}`), lädt der Lauf deshalb **direkt hoch** (`freigabe` wird auf `false`
gesetzt). Willst du erst prüfen: `hochladen` weglassen und das Video aus dem Artefakt selbst hochladen. Das Ergebnis
(Link oder Fehler) steht im Kommentar.

## Was im Notbetrieb anders ist

- Alle Arten gehen in einem Zug: Ranking, **Fakten** (`{"art":"fakten","thema":"Haie","plaetze":5,"sprache":"de"}`),
  Story, Reportage, Satire und Clip (die Erlaubnisprüfung des Creators läuft im Lauf; YouTube sperrt Cloud-IPs oft,
  dann steht der Grund im Kommentar). Format-Wahl und Hochladen gehen wie in der App-Seite.
- Story-Zwischenschritte: „skelett“ und „video“ werden zu „direkt Video“. „Bearbeiten“ und „Veröffentlichen“ nach
  Freigabe gibt es nur in der App mit Claude.
- Der Ergebniskommentar nennt je Video Titel-Varianten, YouTube-/TikTok-Text, Upload-Ergebnis, Hinweise,
  Endkontrolle und den Prüfbericht (Kurzform) samt Artefakt-Link.
- Das Sprachmodell ersetzt Claude nur beim Schreiben (Thema deuten, Fakten, Erzähltext, Story-Lektorat). Die
  Prüfungen im Code bleiben unverändert; fällt die Modell-Kette aus oder liefert Ungültiges, gelten die Textbausteine.
- Eigene Web-App statt GitHub: Wer weiter einen Space oder PC-Server betreibt, trägt seine Adresse im Tab
  „Volle App“ → „Notbetrieb“ ein; sie wird dann statt des GitHub-Issues geöffnet (`config/notbetrieb`).
- Bekannte Stolperstellen und Behebungen: `docs/notbetrieb-fehlerliste.md`.

## Datenschutz

Das Repository ist **öffentlich**: Issues, Aufträge, Kommentare und die Links zu Artefakten sind für alle sichtbar
(den Artefakt-Download selbst sieht nur, wer bei GitHub angemeldet ist und Zugriff hat). Keine privaten Wünsche in den
Auftrag schreiben. Zugangsdaten stehen nur in GitHub-Secrets, nie im Repository und nie in Ausgaben; Aufträge von
Fremden (nicht Besitzer/Mitarbeitende) werden abgelehnt.
