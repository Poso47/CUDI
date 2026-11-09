---
name: tempo
description: Videos schneller fertig machen oder Laufzeit-Probleme untersuchen (Zeitmessung je Stufe, größte Bremsen, Regeln). Nutzen bei "dauert zu lange", vor jeder Änderung an Render/TTS/Bildsuche/Prüfung und beim Hinzufügen neuer Stufen.
---
# Tempo (Wunsch des Nutzers: gleiche Qualität, weniger Zeit)

**Erst messen, dann ändern.** Jede Stufe steht in `ergebnis.json["zeiten"]` und im Prüfbericht „Zeiten“ (`cudi_video/zeiten.py`, `with zeiten.stufe("name"):` misst nur die EIGENE Zeit, Verschachteltes wird abgezogen; mehrere Prozesse eines Auftrags addieren über `zeiten.json`). Stufen: pakete, planen, pruefen, bilder, schreiben, tts, render, ton, encode, qa, app. Neue Stufe = neuer Name + Eintrag in `zeiten.LABELS`.

**Messweg**: Lauf ohne Sprachmodell, frischer Cache (sonst lügt die Messung): `CUDI_BILDPRUEFUNG=0 CUDI_VIDEO_CACHE=<leerer Ordner> python -m cudi_video auftrag '{"id":"mess1","art":"ranking","vorlage":"hoechste-berge","plaetze":5,"sprachen":["de","en"]}'`. Story: gleiches `story.json` zweimal rendern (`pipeline.render(folder, skeleton=…)`). Haupt-Standard-Sprache der App ist jetzt nur "de". Hängt ein Lauf: `py-spy dump --pid <pid>`. Nie zwei Läufe gleichzeitig (verfälscht die Zeit). Wikipedia/Wikidata drosseln nach vielen Läufen (planen/pruefen schwanken dann 65–270 s): Netzstufen nur mit Vorsicht vergleichen.

**Größte Bremsen (gemessen, 5 Plätze DE+EN / Story 3 Teile)**: Wikidata-SPARQL-Zeitüberschreitung (60–90 s, danach Suchindex) und Wikipedia-429 · Bildsuche · Bilder zeichnen (PIL, ~50 ms/Bild, 4 Kerne ausgelastet) · doppeltes Kodieren (früher: ganzes Video nur wegen des Cover-Frames) · App-Fassung ≤ 19 MB · Story: `preset medium` mit Untertiteln, sequentielle Hintergrund-Clips.

**Regeln**
- Gleichzeitig nur, was unabhängig ist: Quellen einer Suche (`media.gather`), Plätze (`enrich.parallel_map`), TTS (`CUDI_TTS_PARALLEL`, 6), Stock-Vorwärmen der Story. Wikimedia bleibt einzeln und höflich (`net`-Slots, `enrich.wikimedia_pace`). KI-Bilder (Pollinations) nur nacheinander.
- Schreibaufgaben bündeln: unabhängige Aufgaben mit `handoff.request_many([...])` (Erzählen + Titel = EINE Runde statt zwei; jede Runde kostet im Cloud-Lauf einen Neustart + Wartezeit). Abhängige (Regie nach Erzählen, Gegenlesen nach Regie) bleiben getrennt. Fehlt dem Bündel eine Antwort, wird sie danach einzeln gefragt (nie Endlosschleife); Prüfregeln laufen je Aufgabe wie vorher.
- Prüfungen (Wahrheit, qa, Quellen) nie abschwächen oder überspringen; Auflösung/CRF/Bitrate nicht senken. Preset nur ändern, wenn derselbe CRF bleibt und ein Bilderbogen/Vergleich keinen Unterschied zeigt.
- Lautheit: zweistufiges `loudnorm` schon beim Muxen auf der kleinen Tonspur (`qa.loudnorm_filter`), damit qa das Video nicht noch einmal anfassen muss.
- Pakete: `scripts/cudi_auftrag.sh` installiert für Ranking/Story nur `cudi_video/requirements-basis.txt` (Clip: `requirements.txt`). CLIP/torch (`bildcheck`) wird erst bei Bedarf installiert (groß!). Vorschlag für Umgebungs-Setup: `docs/umgebung-setup.sh` (nur mit OK des Nutzers einrichten).
- Neue Parallel-/Cache-Logik bekommt einen Test ohne Netz (`tests/test_tempo.py`).
