# Clip-Team: Clip-Scout und Messung

Zwei Firma-Mitarbeiter auf GitHub (kostenlos, kein Claude-Verbrauch). Sie liefern dem Clip-Team Material **mit belegter Erlaubnis**.

## Creator eintragen (du pflegst `firma_daten/clip_creators.json`)
```json
{"creators": [
  {"name": "Beispiel-Creator", "youtube": ["@beispielkanal", "UCxxxxxxxxxxxxxxxxxxxxxx"], "twitch": ["beispiel"], "tiktok": [], "gesperrt": false}
]}
```
- `youtube`: @Handle oder Kanal-ID (UC…), `twitch`: Login-Name. `gesperrt: true` schlägt immer jede Erlaubnis.
- Die Liste startet leer; es werden **keine** Creator erfunden. Leer = die Mitarbeiter melden das ehrlich im Hinweis.
- Datenschutz: Das Repo ist öffentlich. Nur öffentliche Kanalnamen eintragen, keine privaten Daten, keine Zugangsdaten.

## Clip-Scout (alle 6 h, `firma-clipscout.yml`)
- Trend-Radar: YouTube-Kanalfeeds (RSS, ohne Schlüssel) und öffentliche Twitch-Clips → `clip_radar.json` (Aufrufe/Stunde, Faktor gegenüber dem Kanal-Median).
- Aufruf-Finder: Beschreibungen mit „Clipper gesucht“, „clip me“ usw. (de/en).
- Kampagnen-Scout: öffentliche Liste contentrewards.com/c/discover (robots.txt wird geprüft, ein Abruf). Eine Kampagne allein erlaubt nichts – erst nach Beitritt und mit deren Regeln.
- Beweis-Sucher → `clip_erlaubnis.json`: „erlaubt“ nur mit eindeutigem Aufruf des Creators (wörtliches Zitat + Link + Datum). Schwacher Hinweis oder Kampagne = „unklar“, Sperre = „gesperrt“.
- `vorschlaege` im App-Auftragsformat (`art: "clip"`, `quelle`) nur für erlaubtes, aktuell überdurchschnittliches Material; `bestaetigt_erlaubnis` setzt erst du in der App.

## Messung (täglich, `firma-messung.yml`)
Öffentliche Aufrufe/Likes/Kommentare eigener Posts per yt-dlp (ohne Konto) → `messung.json` als Zeitreihe. Post-Links: `uploads.json` und `clip_radar.json` → `clip_posts` (Liste von Links oder `{"url": …}`, von dir oder der Clip-Pipeline). Der Lern-Analyst nutzt die Reihe, wenn YouTube-/TikTok-API fehlen.

## Sichtbar
Morgen-Briefing Abschnitt „6. Clip-Team“ (nur Belegtes), `docs/firma/firma.json` → `clipteam` (für das 3D-Büro), Status in `status.json`.
