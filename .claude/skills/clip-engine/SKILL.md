---
name: clip-engine
description: Clip-Engine von CUDI (cudi_video/clip/) erweitern oder prüfen – Erlaubnis, Auswahl mit Bildschnitten, Inhaltsurteil, Stil vollbild/zuschnitt, Twitch-Ranking, Instagram-Upload, Tests und Probelauf ohne fremdes Creator-Material.
---
# Clip-Engine

Ablauf `pipeline.make_clip`: Erlaubnis (nur URLs) → Quelle → Spracherkennung → Bildschnitte (`szenen.erkenne`) → Fenster-Rangliste (`highlights.fenster_rangliste`, Gewichte aus `kalibrierung.gewichte()`) → optional Claude-Wahl (`clip_hook`) → Inhaltsurteil (`urteil.urteilen`, Aufgabe `clip_urteil`, sonst Regeln) → Schnittplan (`vollbild.plane` oder `cuts.plane`) → Untertitel → `render.rendern(..., filter_fn)` → Texte (`texte.schreibe`, Prüfbericht mit Erlaubnis/Urteil/Signale).

Regeln:
1. Nie ohne Erlaubnisprüfung clippen (`erlaubnis.pruefe_auftrag`): gesperrt bricht immer ab, unklar nur mit `bestaetigt_erlaubnis`. `erlaubnis.py` ist der Vertrag mit dem Clip-Scout (`firma/clipscout.py`, `messung.py`, `firma-clip*.yml` nicht anfassen); er schreibt `clip_erlaubnis.json`, der Nutzer pflegt `clip_creators.json`. Creator-Listen nie erfinden.
2. Jede Claude-Antwort (Titel, Urteil) läuft durch `urteil.titel_pruefen`; ohne Modell gilt der Regelweg. Schwaches Urteil = Hinweis, nie Abbruch.
3. Handoff-Aufgaben werden nacheinander gestellt (`clip_hook`, dann `clip_urteil`): Tests mit `CUDI_SCHREIBEN=1` müssen beide beantworten.
4. Tests laufen offline: Fixture mit `CUDI_FIRMA_DATEN` auf tmp und `erlaubnis.meta_holen` ersetzen (sonst ruft `pruefe` yt-dlp). Sprache per `transcribe.erkenne` faken, Video mit ffmpeg `testsrc2`.
5. Probelauf ohne Creator-Material: eigene Sprache mit `piper --model video_output/_piper/de_DE-thorsten-medium.onnx` + ffmpeg-Testbild (Wikimedia-API drosselt mit 429 – nicht wiederholen). Standbilder: `ffmpeg -i clip.mp4 -vf fps=1/6,scale=360:640,tile=3x2`.
6. Twitch-Ranking: Auswahl nach Dauer NACH Pausenschnitt (`_verstehen`), Clips müssen laut Metadaten zum Kanal gehören.
7. Instagram: Reels sind sofort öffentlich → nur `oeffentlich`; Token nie ausgeben (`upload.redact`, `SECRET_VARS`).
Stolperfallen: Auftragskennung ≥ 4 Zeichen; die Umgebung kann `CUDI_LLM_*` gesetzt haben (dann ist `handoff.active()` im Probelauf wahr); Claude-gewählte Fenster (`wahl._fenster_ab`) tragen keine Auswahl-Signale.
