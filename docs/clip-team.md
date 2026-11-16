# Clip-Team: Clip-Scout und Messung

Zwei Firma-Mitarbeiter auf GitHub (kostenlos, kein Claude-Verbrauch). Sie liefern dem Clip-Team Material **mit belegter Erlaubnis**.

## Creator eintragen (optional) – `firma_daten/clip_creators.json`
Die Liste ist nur noch für **eigene Ergänzungen und die Sperrliste**; wer im Hype ist, findet der Clip-Scout selbst (siehe „Entdeckung“).
```json
{"creators": [
  {"name": "Beispiel-Creator", "youtube": ["@beispielkanal", "UCxxxxxxxxxxxxxxxxxxxxxx"], "twitch": ["beispiel"], "tiktok": ["@beispiel"],
   "telegram": ["beispielkanal"], "discord": ["https://discord.gg/abc123"],
   "belege": [{"url": "https://…", "zitat": "Wir suchen Clipper …", "datum": "2026-11-16", "quelle": "TikTok-Video"}],
   "hinweis": "Regeln/Belohnung des Creators", "gesperrt": false}
]}
```
- `youtube`: @Handle oder Kanal-ID (UC…), `twitch`: Login-Name. `gesperrt: true` schlägt immer jede Erlaubnis.
- `telegram`: öffentliche Kanäle (Vorschau t.me/s/…, ohne Konto lesbar; geschlossene Gruppen nicht). `discord`: Einladungslinks
  (Servername/Beschreibung öffentlich, Nachrichten nur mit Lese-Bot – `docs/discord-bot.md`). Telegram-/Discord-Links in den
  eigenen Videobeschreibungen des Creators findet der Scout selbst.
- `belege`: Aufrufe, die du gesehen hast (z. B. im Video gesprochen): Link, wörtliches Zitat, Datum. Ein eindeutiger Aufruf
  („Wir suchen Clipper“, „Clipper gesucht“ …) macht den Creator „erlaubt“; `hinweis` (Regeln/Belohnung) steht dann im Prüfbericht.
- Die Liste startet leer; es werden **keine** Creator erfunden. `gesperrt: true` gewinnt auch gegen entdeckte Creator (gleicher Name/Kanal).
- Datenschutz: Das Repo ist öffentlich. Nur öffentliche Kanalnamen eintragen, keine privaten Daten, keine Zugangsdaten.

## Entdeckung (`entdecke()` → `clip_entdeckt.json`)
Alle im Hype werden **beobachtet**, geclippt wird nur nach Stufe (unten). Je Eintrag: `name`, `plattform`, `kanal`, `grund`, `signal` (Aufrufe/h, Rang, Erwähnungen), `erste_sichtung`, `zuletzt`, `erlaubnis`, `signale`. Max. 50 neue je Lauf (höchste Signale zuerst), Kanäle ohne Sichtung seit 14 Tagen fliegen raus, je Lauf werden höchstens 60 Entdeckte geprüft. Jede Quelle einzeln abgesichert:
- Kampagnen (contentrewards, Kanäle in der Kampagnenbeschreibung) · Aufruf-Suche (YouTube-Titel „Clipper gesucht“, Beweis erst aus der Beschreibung) · YouTube-Trends aus `trends.json` (Kanal per oEmbed; braucht `CUDI_YT_API_KEY` im Trend-Scout) · Reddit r/LivestreamFail (Name in ≥ 2 Beitragstiteln, Kanal nur **vermutet** → nie „geduldet“) · Wikipedia-Top-Personen, deren Wikidata-Beruf zu Streamer/YouTuber/Influencer passt (YouTube-ID P2397, Twitch P5797).
- Twitch-Top-Liste: ohne Anmeldung gibt es keine öffentliche Quelle (steht als Hinweis im Lauf); Twitch-Kanäle kommen über Reddit, Wikidata, Kampagnen (≤ 10 yt-dlp-Clipabfragen je Lauf).

## Erlaubnis-Stufen (`clip_erlaubnis.json`, `status`)
1. **erlaubt** – eindeutiger Aufruf des Creators (Zitat + Link + Datum). Vorschläge automatisch.
2. **geduldet** – keine ausdrückliche Aussage, aber Duldungssignale aus ≥ 2 Arten (Reddit-Beiträge, öffentliche Twitch-Clips, Trends) oder eine Kampagne, UND kein Verbot gefunden. Vorschläge mit `erlaubnis: "geduldet"`, `signale`, `credit`; der Auftrag läuft nur mit `bestaetigt_erlaubnis: true` (Prüfbericht: „geduldet, vom Nutzer bestätigt (Signale …)“). **Credit-Pflicht** „Original: <Creator> – <Link>“. Duldung ist nie eine Erlaubnis.
3. **unklar** – keine Signale: nur im Briefing („im Hype, Erlaubnis offen“), keine Vorschläge.
4. **gesperrt** – Sperrliste oder ausdrückliches Verbot in einer Videobeschreibung („no clips“, „keine Clips“, „don't reupload“, „copyright strike“ …, im Zweifel gesperrt): nie, auch nicht mit Bestätigung. Kanalinfo-Seiten werden (noch) nicht gelesen.

## Clip-Scout (alle 6 h, `firma-clipscout.yml`)
- Trend-Radar: YouTube-Kanalfeeds (RSS, ohne Schlüssel) und öffentliche Twitch-Clips → `clip_radar.json` (Aufrufe/Stunde, Faktor gegenüber dem Kanal-Median).
- Aufruf-Finder: Beschreibungen mit „Clipper gesucht“, „clip me“ usw. (de/en).
- Kampagnen-Scout: öffentliche Liste contentrewards.com/c/discover (robots.txt wird geprüft, ein Abruf). Eine Kampagne allein erlaubt nichts – erst nach Beitritt und mit deren Regeln.
- Beweis-Sucher → `clip_erlaubnis.json`: Stufen siehe oben; Kampagne allein gilt als Duldung (Beitritt und Regeln der Kampagne nötig), nicht als Erlaubnis.
- `vorschlaege` im App-Auftragsformat (`art: "clip"`, `quelle`) nur für erlaubtes und geduldetes, aktuell überdurchschnittliches Material (erlaubt zuerst); `bestaetigt_erlaubnis` setzt erst du in der App.

## Messung (täglich, `firma-messung.yml`)
Öffentliche Aufrufe/Likes/Kommentare eigener Posts per yt-dlp (ohne Konto) → `messung.json` als Zeitreihe. Post-Links: `uploads.json` und `clip_radar.json` → `clip_posts` (Liste von Links oder `{"url": …}`, von dir oder der Clip-Pipeline). Der Lern-Analyst nutzt die Reihe, wenn YouTube-/TikTok-API fehlen.

## Sichtbar
Morgen-Briefing Abschnitt „6. Clip-Team“ (Top 10 im Hype mit Stufe als Pille-Text, „im Hype, Erlaubnis offen“ mit Link, erlaubte Neuzugänge), `docs/firma/firma.json` → `clipteam` (`entdeckt`, `im_hype` mit `erlaubnis`-Stufe, `geduldet`; für App/3D-Büro), Status in `status.json`.

## Clip-Autopilot (alle 6 h, `firma-clipautopilot.yml`) – Entscheidung des Nutzers: „Alles automatisch“
- Nimmt **nur** Material von Creators mit Status **erlaubt** (eindeutiger Beleg): frische Videos aus dem Radar (schnellste zuerst,
  höchstens 7 Tage alt) und je Twitch-Kanal einmal am Tag das Clip-Ranking der Woche. „geduldet“, „unklar“, „gesperrt“ nie.
- Schneidet ohne Claude (`job.run_order(via_claude=False)`) und lädt sofort hoch (`freigabe: false`) auf die eingestellten
  Ziele; Credit „Original: …“ steht automatisch im Text. Fehlen Upload-Secrets, steht das im Protokoll.
- Einstellungen `firma_daten/clip_autopilot_einstellungen.json` (optional): `aktiv`, `max_pro_tag` (3), `max_versuche` (5),
  `hochladen` („alle“), `sichtbarkeit` („oeffentlich“), `clip_stil`, `laenge` (60 s), `max_alter_tage` (7).
- Protokoll `clip_autopilot.json` (jede Quelle nur einmal, Fehlschläge höchstens 2-mal), Videos als Artefakt am Lauf (7 Tage),
  hochgeladene Links gehen in `clip_radar.clip_posts` (Messung). Export → `firma.json` `clipteam.autopilot`.
- **YouTube aus der Cloud**: YouTube verlangt von GitHub-/Cloud-Servern eine Anmeldung („Sign in to confirm you're not a bot“).
  Optional: Secret `CUDI_YT_COOKIES` = Inhalt einer cookies.txt (Netscape-Format, z. B. Browser-Erweiterung „Get cookies.txt LOCALLY“)
  eines **eigenen Zweit-Google-Kontos** (nicht dein Hauptkonto: Google kann Konten mit Download-Tools einschränken; Cookies laufen nach
  einigen Wochen ab). Ohne Secret nutzt der Autopilot nur Quellen, die ohne Anmeldung gehen (Twitch-Clips/VODs); nach dem ersten
  YouTube-Block überspringt er weitere YouTube-Quellen im selben Lauf. Erlaubnis-Prüfung braucht kein yt-dlp: Videos aus dem Feed des
  Scouts sind ihrem Kanal zugeordnet (`erlaubnis.kanal_aus_radar`).
