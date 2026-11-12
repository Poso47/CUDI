# Clip-Engine und Clip-Kern

Teil des Projekt-Gehirns (Übersicht: CLAUDE.md). Nur lesen, wenn die Aufgabe dieses Thema berührt.

- **Clip-Engine** (`cudi_video/clip/`, CLI `python -m cudi_video clip <datei|url>`, Doku README_VIDEO.md): Podcast-/Streamer-Clips
  1080×1920 (faster-whisper → Höhepunkt/Hook nach Regeln, optional Claude-Auswahl `clip_hook` über `handoff` → Pausenschnitt →
  Sprecher-Zuschnitt mit YuNet/Haar → ASS-Untertitel). App-Auftrag `art: "clip"` (`job._clip`): Pflichtfeld `bestaetigt_erlaubnis`,
  nur http(s)-Links, Texte/Prüfbericht in `clip/texte.py`; YouTube sperrt Cloud-IPs oft (`ClipError.wiederholbar`, Hinweis „später/PC“).
  **Clip-Kern** (Skill `clip-engine`): `clip/erlaubnis.py` `pruefe(url)` (Sperrliste `clip_creators.json` vor Scout-Ergebnis `clip_erlaubnis.json`; erlaubt → läuft, gesperrt → Abbruch,
  unklar → nur mit `bestaetigt_erlaubnis` + Vermerk), Auswahl mit Bildschnitten/Titeltreffern/offenem Ende + Gewichte `clip_kalibrierung.json`, Inhaltsurteil `clip_urteil` (`urteil.py`),
  Auftragsfeld `clip_stil` `vollbild` (Standard, `vollbild.py`) | `zuschnitt`, Twitch-Ranking `twitch_kanal` (`twitch.py`), Upload-Ziel `instagram`/`alle` (`upload/instagram.py`, `CUDI_IG_*`).
- Weitere Wege: GitHub Actions „CUDI Video“/„CUDI Story“, Issue mit `cudi-auftrag` („CUDI Auftrag“),
  Hugging Face Space („CUDI Cloud-App“, optional, braucht Secret HF_TOKEN).
