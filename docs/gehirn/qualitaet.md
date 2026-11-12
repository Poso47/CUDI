# Upload, Betonung, Endkontrolle, Wahrheit, Musik

Teil des Projekt-Gehirns (Übersicht: CLAUDE.md). Nur lesen, wenn die Aufgabe dieses Thema berührt.

- Upload (`cudi_video/upload/`: `youtube.py` resumable videos.insert, `tiktok.py` Inbox/Direct Post, `cli.py`): `hochladen … --probe`, `youtube-login`;
  Zugang nur über Umgebungsvariablen (`CUDI_YT_*`, `CUDI_TIKTOK_*`, nie ausgeben: `upload.redact`), Auftragsfeld `hochladen` (Standard aus), Doku `docs/upload-einrichten.md`.
- Betonung (`tts.py`, Tabelle `SPEECH_PROFILES` + `MOOD_STYLE`): Abschnitte werden in Teile mit eigenem Tempo/Tonhöhe/Lautstärke und
  Spannungspausen zusammengesetzt (`assemble_parts`, Wortzeiten wandern mit; Grundtempo `+0%`). Profil nach Videoart
  (`speech_profile(spec.kind)`): ranking (Pausen vor Platz/Zahl), fakten (Frage, Pause vor dem Aha, ruhiger Erklärteil), erklaer (ruhig,
  gleichmäßig), Story je Stimmung (`plan_story_parts`: Pause vor Wendung/Pointe). `CUDI_SPEECH_PROFILE=ranking|fakten|erklaer|aus` überschreibt.
- Endkontrolle (`qa.py`, nach dem Render in `render_video`/Erklär-Render, für Story/Clip in `job._summary`): blackdetect, freezedetect (nur Ranking/Fakten), ebur128 (−14 LUFS ±1, TP ≤ −1), Dauer, 1080×1920, Sync, Safe-Zones über Layout-Konstanten; Lautheit wird einmal per zweistufigem `loudnorm` korrigiert, Befunde nur als Hinweise (`ergebnis.json` Feld `qa`, `review.md` „Endkontrolle“, nie Abbruch).
- **Wahrheit** (`wahrheit.py`, Nutzerwunsch: nie lügen, auch nicht durch Formulierung): `Pruefer` prüft Sprechtext/Hook/Untertitel/Titel/Cover/Beschreibung gegen die Daten (Regelkatalog `REGELN`, optional Gegenlesen `wahrheit_pruefung`), korrigiert automatisch (ergänzen/ersetzen/streichen); Endabnahme `pipeline.render_checked` (Wahrheit UND qa, eine Reparaturrunde, sonst `abnahme.ok=false` → `job._summary` liefert nicht aus, `ok:false` „Nicht ausgeliefert, weil …"); Abschnitt „Wahrheits-Prüfung" in review.md.
- Musik für Ranking/Fakten/Erklär (`render/audio.py`: Stil je Videoart/Format/Thema aus `story/music.py`, selbst erzeugt, Ducking unter der Stimme, Akzent-Ton je Platz-Enthüllung; Datei in `assets/music` hat Vorrang; abschaltbar `CUDI_MUSIK=0`).
