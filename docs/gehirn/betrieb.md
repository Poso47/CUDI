# Tempo, Kosten, Ausweichwege

Teil des Projekt-Gehirns (Übersicht: CLAUDE.md). Nur lesen, wenn die Aufgabe dieses Thema berührt.

- **Tempo** (Skill `tempo`, `cudi_video/zeiten.py`): Zeit je Stufe in `ergebnis.json["zeiten"]`/Prüfbericht „Zeiten“; Bündel-Schreibrunde `handoff.request_many` (Erzählen + Titel), parallele Quellen/Plätze/TTS, Cover nur auf dem Intro, Ton-loudnorm vorab, kleine Paketliste `requirements-basis.txt`; Messen immer mit frischem Cache (`CUDI_VIDEO_CACHE`), Umgebungs-Vorschlag `docs/umgebung-setup.sh`.
- Kosten: alles kostenlose Dienste; App-Aufträge zählen nur zum Claude-Nutzungslimit des Nutzers.
- **Keine Fehlschläge** (Wunsch des Nutzers) – kostenlose Ausweichwege, siehe README „Probleme?“:
  edge-tts 6 Versuche → Piper offline (`tts.PIPER_VOICES`, Modelle in `video_output/_piper`, `piper-tts`
  wird bei Bedarf installiert); Story: Reddit-JSON (Cloud: 403) → Arctic Shift → Reddit-RSS (gedrosselt);
  Beschreibung ohne Treffer → beliebte Story der Stimmung; `job.run_order` wiederholt Störungen einmal
  (`RETRY_PAUSE`); App startet Fehler/ohne Ergebnis einmal automatisch neu (`versuch: 2`) und prüft
  vor jedem Start den Speicherbedarf (`needMB`: 20 MB je möglichem Video + 10 MB; Skelett-Schritt 0).
