# Videos direkt zu YouTube Shorts und TikTok hochladen – Einrichtung

Einmal einrichten, danach: `python -m cudi_video hochladen <video.mp4 | auftrag-id> --ziel youtube|tiktok|beide`.

> **Wichtig: Schlüssel, Secrets und Tokens NIE in den Chat schreiben, nie ins Repo einchecken, nie in Screenshots zeigen.**
> CUDI liest sie ausschließlich aus Umgebungsvariablen (oder der lokalen, gitignorierten Datei unter `video_output/_secrets/`)
> und schwärzt sie in allen Ausgaben. Wenn doch einmal ein Schlüssel irgendwo gelandet ist: im jeweiligen Portal sofort
> löschen/neu erzeugen.

Zuerst immer den Trockenlauf: `python -m cudi_video hochladen video.mp4 --ziel beide --probe` zeigt Titel, Beschreibung,
Tags, Sichtbarkeit und Stückelung – ohne Netz und ohne etwas zu senden.

Umgebungsvariablen setzen (Windows PowerShell, dauerhaft): `setx CUDI_YT_CLIENT_ID "…"` und Terminal neu öffnen;
Linux/macOS: in `~/.profile` oder einer `.env`-Datei (steht in `.gitignore`).

## YouTube Shorts

1. **Google Cloud Projekt anlegen:** <https://console.cloud.google.com/> → „Projekt erstellen“ (Name z. B. „CUDI Upload“).
2. **YouTube Data API aktivieren:** „APIs & Dienste“ → „Bibliothek“ → „YouTube Data API v3“ → „Aktivieren“.
3. **OAuth-Zustimmungsbildschirm:** „APIs & Dienste“ → „OAuth-Zustimmungsbildschirm“ → Typ „Extern“, App-Name „CUDI“, deine
   E-Mail. Unter „Testnutzer“ dein eigenes Google-Konto eintragen (der Kanal, auf den hochgeladen wird). Scope
   `…/auth/youtube.upload` hinzufügen.
4. **OAuth-Client erstellen:** „Anmeldedaten“ → „Anmeldedaten erstellen“ → „OAuth-Client-ID“ → Anwendungstyp **„Desktop-App“**.
   Client-ID und Client-Secret als Umgebungsvariablen setzen: `CUDI_YT_CLIENT_ID`, `CUDI_YT_CLIENT_SECRET`.
5. **Einmaliger Login am eigenen PC:** `python -m cudi_video youtube-login`. Der Browser öffnet sich, Google-Konto wählen und
   zustimmen („nicht überprüfte App“ → „Erweitert“ → „weiter“, das ist deine eigene App). Der Refresh-Token wird in
   `video_output/_secrets/youtube_refresh_token.txt` gespeichert (nicht angezeigt, nicht im Repo). Für Server/Cloud den
   Dateiinhalt als `CUDI_YT_REFRESH_TOKEN` hinterlegen.
6. **Testen:** `python -m cudi_video hochladen video.mp4 --ziel youtube` (Standard: **privat**; `--sichtbarkeit ungelistet|oeffentlich`).

Gut zu wissen:
- **Quota:** Ein Upload kostet ca. 1600 Einheiten, kostenlos sind 10 000 pro Tag (≈ 6 Videos/Tag).
- **Privat-Sperre:** Videos aus einem nicht geprüften API-Projekt (Stand der Google-Regeln) werden von YouTube zunächst auf
  „privat“ gesetzt, auch wenn „öffentlich“ gewählt ist. Dann das Video einmal in YouTube Studio auf öffentlich stellen oder
  beim Google-Support eine „API-Audit“-Prüfung beantragen.
- Der Testmodus des Zustimmungsbildschirms lässt Refresh-Tokens nach 7 Tagen ablaufen. Für Dauerbetrieb den Bildschirm auf
  „In Produktion“ stellen (für den Upload-Scope reicht das ohne Prüfung für eigene Nutzung) und `youtube-login` einmal wiederholen.
- Shorts: Hochformat ≤ 3 Minuten; CUDI hängt `#shorts` an die Beschreibung.

## TikTok

Ohne eigene Domain: CUDI bringt eine kostenlose Rücksprung-Seite mit (GitHub Pages aus `docs/`):
`https://poso47.github.io/CUDI/tiktok/` – dazu Nutzungsbedingungen (`…/tiktok/nutzungsbedingungen.html`) und
Datenschutz (`…/tiktok/datenschutz.html`). Einmalig im Repo auf GitHub: **Settings → Pages → Source „Deploy from a
branch“ → Branch `main`, Ordner `/docs` → Save** (nach 1–2 Minuten erreichbar).

1. <https://developers.tiktok.com/> → „Manage apps“ → deine App → oben **„Sandbox“** → „Create Sandbox“ (testen ohne Prüfung).
2. In der Sandbox **„Add products“**: **Login Kit** und **Content Posting API**; unter „Scopes“ **`video.upload`**.
3. **Login Kit → Redirect URI (Desktop):** `http://localhost:8723/callback/` (TikTok verlangt bei Desktop localhost:Port).
   Bei App-Angaben: Nutzungsbedingungen- und Datenschutz-Adresse von oben. (Nur für eine Web-App: Redirect
   `https://poso47.github.io/CUDI/tiktok/` und `CUDI_TIKTOK_REDIRECT_URI` auf diese Adresse setzen.)
4. **„Target users“ → „Add account“** → mit deinem TikTok-Konto anmelden.
5. **Client key/secret** als `CUDI_TIKTOK_CLIENT_KEY` und `CUDI_TIKTOK_CLIENT_SECRET` setzen (PC und Cloud-Umgebung).
6. **Token holen (am PC):** `python -m cudi_video tiktok-login` → Browser öffnet sich, zustimmen → CUDI fängt den
   Code selbst ab (PKCE, nichts zu kopieren). Der Refresh-Token (ca. 1 Jahr) liegt dann in
   `video_output/_secrets/tiktok_refresh_token.txt`; für die Cloud den Inhalt als `CUDI_TIKTOK_REFRESH_TOKEN` hinterlegen.
7. **Testen:** `python -m cudi_video hochladen video.mp4 --ziel tiktok` – das Video landet als **Entwurf in der TikTok-App**.

Gut zu wissen:
- **Direct Post** (`--tiktok-modus direkt`) veröffentlicht ohne App-Schritt, erfordert aber die **App-Prüfung** durch TikTok.
  Bis dahin sind nur Beiträge mit Sichtbarkeit „nur ich“ (`--sichtbarkeit privat`) erlaubt. Bis zur Freigabe den
  Standardweg (Inbox) nutzen.
- Videos werden in Stücken (5–64 MB; große Dateien in 32-MB-Stücken) übertragen, kurze Störungen wiederholt CUDI automatisch.
- Die KI-Kennzeichnung (`is_aigc`) setzt CUDI bei Direct Post automatisch, da Stimme und Bilder KI-gestützt sind.

## Über Aufträge (Backend)

Im Auftrag (`job.py`) gibt es das optionale Feld `"hochladen": {"ziel": "youtube|tiktok|beide", "sichtbarkeit": "privat"}`.
Standard ist aus. Fehler beim Hochladen brechen den Auftrag nie ab; sie stehen im Ergebnis unter `hochgeladen`.
