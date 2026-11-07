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

Du hast bereits eine TikTok-Entwickler-App mit Landingpage (viralstudio, Nutzungsbedingungen und Datenschutz). Dafür:

1. <https://developers.tiktok.com/> → „Manage apps“ → deine App → „Add products“ → **Content Posting API** hinzufügen.
2. Unter „Scopes“ **`video.upload`** (Inbox/Entwurf) und **`video.publish`** (Direct Post) beantragen. Die Angaben der App
   (Landingpage, Nutzungsbedingungen-URL, Datenschutz-URL von viralstudio) müssen mit dem übereinstimmen, was TikTok bei der
   Prüfung sieht; im Demo-Video der Prüfung den Upload-Ablauf zeigen.
3. **Redirect-URI** unter „Login Kit“ eintragen (z. B. `https://<deine-viralstudio-domain>/callback` oder eine lokale
   Adresse wie `http://localhost:3000/callback`) und in der Entwickler-Konsole dein Konto als „Target user“ (Sandbox/Test) hinzufügen.
4. **Zugriffstoken holen** (OAuth, Scopes `video.upload,video.publish`): den Login von deiner App/Landingpage aus durchlaufen;
   der Code-Tausch liefert `access_token` (ca. 24 h gültig) und `refresh_token` (ca. 365 Tage). Zugangsdaten setzen:
   - einfach: `CUDI_TIKTOK_ACCESS_TOKEN`
   - dauerhaft: `CUDI_TIKTOK_CLIENT_KEY`, `CUDI_TIKTOK_CLIENT_SECRET`, `CUDI_TIKTOK_REFRESH_TOKEN` – CUDI erneuert den
     Zugriffstoken dann selbst, wenn er abgelaufen ist.
5. **Testen:** `python -m cudi_video hochladen video.mp4 --ziel tiktok` – das Video landet als **Entwurf in der TikTok-App**
   (Posteingang/Benachrichtigungen). Dort Text ergänzen und veröffentlichen.

Gut zu wissen:
- **Direct Post** (`--tiktok-modus direkt`) veröffentlicht ohne App-Schritt, erfordert aber die **App-Prüfung** durch TikTok.
  Bis dahin sind nur Beiträge mit Sichtbarkeit „nur ich“ (`--sichtbarkeit privat`) erlaubt. Bis zur Freigabe den
  Standardweg (Inbox) nutzen.
- Videos werden in Stücken (5–64 MB; große Dateien in 32-MB-Stücken) übertragen, kurze Störungen wiederholt CUDI automatisch.
- Die KI-Kennzeichnung (`is_aigc`) setzt CUDI bei Direct Post automatisch, da Stimme und Bilder KI-gestützt sind.

## Über Aufträge (Backend)

Im Auftrag (`job.py`) gibt es das optionale Feld `"hochladen": {"ziel": "youtube|tiktok|beide", "sichtbarkeit": "privat"}`.
Standard ist aus. Fehler beim Hochladen brechen den Auftrag nie ab; sie stehen im Ergebnis unter `hochgeladen`.
