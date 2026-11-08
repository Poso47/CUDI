# Notbetrieb einrichten (wenn dein Claude-Nutzungslimit erreicht ist)

Claude bleibt der Motor der CUDI-App. Der Notbetrieb ist nur eine Stütze: Ist das Limit erreicht, zeigt die
App-Seite den Banner **„Claude-Limit erreicht – Notbetrieb nutzen“**. Ein Tipp öffnet deine eigene Web-App
(Hugging Face Space) mit dem vorbefüllten Auftrag. Dort schreibt ein **kostenloses Sprachmodell (Google Gemini)**
die Texte – mit derselben Anleitung und denselben Prüfregeln wie bei Claude (Zahlen nur mit Beleg, keine
erfundenen Wörter, Textbausteine als Ausweichweg). Alles kostenlos, alles vom Handy einzurichten, einmalig.

## 1. Hugging-Face-Konto und Token

1. Auf [huggingface.co/join](https://huggingface.co/join) ein kostenloses Konto anlegen.
2. [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → **Create new token** → Typ **Write**
   (Schreibrecht) → Token kopieren (nur für Schritt 3, nie in einen Chat oder ins Repository schreiben).

## 2. Gemini-API-Schlüssel (kostenlos)

1. [aistudio.google.com](https://aistudio.google.com) mit einem Google-Konto öffnen → **Get API key** →
   **Create API key**.
2. Schlüssel kopieren. Die kostenlose Stufe hat Mengenlimits (Stand 2026, können sich ändern); für ein paar
   Videos pro Tag reicht sie.

## 3. Secrets auf GitHub eintragen

GitHub → Repository `Poso47/CUDI` → **Settings → Secrets and variables → Actions → New repository secret**.
Je Eintrag Name und Wert genau so:

| Secret | Wert |
|---|---|
| `HF_TOKEN` | der Hugging-Face-Token aus Schritt 1 |
| `CUDI_VIDEO_TOKEN` | dein selbst gewählter Zugangscode für die Web-App (ohne ihn bleibt die App gesperrt) |
| `CUDI_LLM_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `CUDI_LLM_API_KEY` | der Gemini-Schlüssel aus Schritt 2 |
| `CUDI_LLM_MODEL` | `gemini-2.5-flash` (der Name, den auch `README_VIDEO.md` nennt; bei Änderungen bei Google den aktuellen kostenlosen Flash-Namen aus AI Studio nehmen) |

Optional, je nachdem was du nutzt (nur gesetzte Secrets werden in den Space übernommen):

- Echte Videoclips: `CUDI_PEXELS_API_KEY`, `CUDI_PIXABAY_API_KEY`
- Hochladen zu YouTube: `CUDI_YT_CLIENT_ID`, `CUDI_YT_CLIENT_SECRET`, `CUDI_YT_REFRESH_TOKEN`
- Hochladen zu TikTok: `CUDI_TIKTOK_CLIENT_KEY`, `CUDI_TIKTOK_CLIENT_SECRET`, `CUDI_TIKTOK_REFRESH_TOKEN`

Den Zugang zu YouTube und TikTok richtest du nach `docs/upload-einrichten.md` ein. Hochladen ist
standardmäßig **aus**; in der Web-App wählst du es je Auftrag bewusst aus.

## 4. App bereitstellen

1. GitHub → **Actions → „CUDI Cloud-App“ → Run workflow**.
2. Nach 3 bis 5 Minuten nennt der Lauf die Adresse, etwa `https://<dein-name>-cudi-video.hf.space`.
3. Der Space ist standardmäßig **privat**: Am Handy einmal bei Hugging Face anmelden, dann den Zugangscode
   (`CUDI_VIDEO_TOKEN`) eingeben. (Die Variable `HF_SPACE_PRIVATE=false` würde ihn öffentlich machen – nicht nötig.)

## 5. Adresse in die CUDI-App eintragen

CUDI-App-Seite → Tab **„Volle App“** → Abschnitt **„Notbetrieb“** → Adresse einfügen → **Speichern**. Hast du bei
„Volle App“ schon dieselbe Adresse eingetragen, übernimmt der Knopf „Adresse von ‚Volle App‘ übernehmen“ sie.

Ab jetzt gilt: Meldet Claude beim Starten ein Limit (oder hängt ein Auftrag über 10 Minuten und die Sitzung ist
fehlgeschlagen), erscheint der Banner mit dem Knopf **„Notbetrieb öffnen“**. Er öffnet die Web-App in einem neuen Tab,
das Formular ist schon ausgefüllt:

- Ranking: `…/?art=ranking&vorlage=…&thema=…&plaetze=10&sprachen=de,en&format=karte`
- Story: `…/?art=story&wunsch=…&stimmung=creepy`

Dort nur noch auf **„Video erstellen“** (bzw. „Autopilot“) tippen.

## Was im Notbetrieb anders ist

- Rankings (Vorlage und freies Thema), Storys, Format-Wahl und Hochladen gehen wie in der App-Seite.
- Das Sprachmodell ersetzt Claude nur beim Schreiben (Thema deuten, Fakten, Erzähltext, Story-Lektorat). Die
  Prüfungen im Code bleiben unverändert; fällt das Modell aus oder liefert Ungültiges, gelten die Textbausteine.
- Clips (Podcast-/Streamer-Ausschnitte) laufen nur in der App-Seite.
- Der kostenlose Space ist langsamer (2 CPU-Kerne), schläft nach Inaktivität ein und speichert Videos nicht
  dauerhaft: fertige Videos direkt herunterladen.
- Zugangsdaten stehen nur in GitHub-Secrets bzw. den Space-Secrets, nie im Repository und nie in Ausgaben.
