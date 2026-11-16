# Figuren-Abteilung – Figuren im Detail bauen

Ziel: Jede Figur, die ein Erklärvideo braucht, wird **so gebaut wie die Biene** (`FIGUREN.biene` in
`cudi_video/schaubild/drei/szene3d.html`). Sie ist im Detail modelliert und hat echte Materialien und Texturen. Ihre
Proportionen kommen aus einer Fotovorlage, und sie bewegt sich natürlich. **Nie** wird eine Figur aus ein paar Kugeln
und Kästen zusammengepuzzelt.

Die App startet diese Abteilung von selbst, wenn eine Skizze „fehlende Figuren“ meldet. Danach zeichnet sie automatisch
eine neue Skizze. „Video erstellen“ geht erst, wenn keine Figur mehr fehlt.

## Ablauf je Figur (in der Figuren-Sitzung)

1. **Vorlage holen** (Crawler, bester Ganzkörper-Fund):
   `python3 -m cudi_video figur-vorlage "Imker (beekeeper)"`. Danach die ausgegebene Bilddatei mit dem Read-Werkzeug
   **ansehen**. Gemessene Farben stehen in der Ausgabe. Die Vorlage dient nur zum Ansehen: Sie kommt nie ins Video und
   nie ins Repo. Findet der Crawler nichts, einen anderen englischen Begriff versuchen (höchstens 2-mal).
2. **Beispiel lesen:** In `szene3d.html` `FIGUREN.imker()` und `FIGUREN.biene()` lesen. So sieht die verlangte Qualität aus.
3. **Figur schreiben** als Datei `video_output/figurenbau/<name>.js`. Der Inhalt ist ein **Funktionskörper** (ohne
   `function`-Kopf), der mit `return { g, teile, glieder };` endet.
4. **Probe:** `python3 -m cudi_video figur-probe <name> video_output/figurenbau/<name>.js --anker '{"kopf":[200,90],…}'`.
   Das ausgegebene JPG mit Read ansehen. Es zeigt die Vorlage links, 4 Richtungen und 2 Bewegungsmomente. Die Anker
   sind rot eingezeichnet.
5. **Nachbessern**, bis Umriss, Proportionen, Farben und alle typischen Teile der Vorlage entsprechen und jeder Anker
   genau auf seinem Teil sitzt. Das dauert höchstens 4 Runden. Meldet die Probe einen Fehler, steht die Meldung des
   Browsers in der Ausgabe.
6. **Ablegen:** `python3 -m cudi_video figur-ablegen <name> <datei.js> --anker '{…}' --anzeige "Imker"`. Der Befehl
   prüft die Figur und schreibt den Lernstand. Ab dann laden alle Video-Läufe die Figur automatisch.

## Regeln für den Code

- Erlaubt ist alles aus `szene3d.html`:
  - `T` (THREE r128) und `mat(rgb, opts)` (MeshPhysicalMaterial).
  - `kugel(r, m, x, y, z, sx, sy, sz)` und `rohr([[x,y,z],…], r, m)`.
  - `fp(x, y, z)`: Figurenraum → Welt.
  - Texturen: `fell(hex)`, `streifen()`, `ringe()`, `facetten()`, `adern()`, `blatttextur()`, `federn(grund, rand)`,
    `stoff(hex, dunkel)`, `gaze()`, `holz(grund, maser)`, `blech()`, `wabenbild()`.
  - `haare(ziel, n, r, farbe, laenge, nur)` für Fell und Härchen, `kleineBiene()`.
  - Eigene Canvas-Texturen über `document.createElement("canvas")`.
- **Verboten** (die Prüfung lehnt ab): Netz (`fetch`, `XMLHttpRequest` …), `eval`/`Function`, Timer, Speicher, `navigator`, `location`.
- **Figurenraum:**
  - 0–400 in beide Richtungen, x nach rechts, y **nach unten**, Mitte `fp(200, 200)`.
  - Die Figur füllt etwa y 40–380 und steht unten auf y ≈ 380.
  - `z` ist direkt in Welt-Einheiten, etwa −0.15…0.15.
- **Qualität wie die Biene:**
  - Aus der Vorlage abgeleitete Formen: `LatheGeometry`-Profile, `rohr` für Glieder, skalierte Kugeln.
  - Jede Fläche hat Material und Textur (Stoff, Fell, Haut mit Glanz/Rauheit).
  - Alle typischen Teile der Vorlage sind da: Gesicht mit Augen, Nase und Mund, Hände/Finger, Kleidung mit Säumen und
    Nähten, Muster.
  - Die Figur steht im leichten Dreiviertel-Profil zur Kamera und schaut nach rechts.
  - Faustregel: mindestens 25 Teile, mindestens 4 Materialien.
- **Bewegung** (die Bühne animiert sie automatisch):
  - `teile.kopf` (Group am Halsansatz) nickt.
  - `teile.schwanz` schwingt.
  - `teile.fluegel`: Kinder mit `userData.seite = ±1` schlagen.
  - `teile.koerper` ist der Hauptkörper und wird bei „durchsichtig“ verwendet.
  - `glieder`: Liste `{ gr, art, nr }`. `gr` ist eine Group mit dem Drehpunkt am Gelenk (Schulter, Hüfte), `art` ist
    `kopf|arm|bein|schwanz|fluegel`, `nr` ist 0, 1, …
  - Arme und Beine gehören als Glieder in eigene Gruppen, damit sie natürlich schwingen.
- **Anker** sind Punkte im Figurenraum, auf die Pfeile und Beschriftungen zeigen. Für jedes Teil, das ein Skript nennen
  könnte, gibt es einen Anker (mindestens 3), z. B. `kopf`, `hand`, `schleier`, `anzug`, `stiefel`, `rahmen`.

## Ablage

- `figur-ablegen` schreibt `video_output/figurenbau/lernstand.json`. Das ist der bisherige Lernstand plus
  `figuren_code[<name>] = {name, code, anker, vorlage, stand}`.
- Die Sitzung legt die Datei per ArtifactData unter `studio/lernstand` ab.
- Jeder Video-Lauf holt sie und gibt `figuren_code` beim Zurückschreiben unverändert weiter
  (`animation.lernstand_aktualisieren`).
- `python3 -m cudi_video figur-bericht <ID> --adressen '{…}' --offen '[…]'` erzeugt das Ergebnis-Dokument
  `figurenbau/<ID>`. Die App zeigt es an, zusammen mit den Probe-Bildern.

## Sitzungsablauf (geplante Aufgabe „CUDI-Figurenbau“ oder Ersatz-Sitzung der App)

Die Auftragsdaten sind `{"id", "figuren": ["Imker (beekeeper)", …], "thema"}`. Die App-Adresse steht in der Anweisung.

1. Lernstand holen: ArtifactData `get`, collection `studio`, doc_id `lernstand`, out_dir `cudi_studio`. Fehlt er, einfach
   weiter.
2. Pakete einrichten: `cd CUDI && bash scripts/cudi_auftrag.sh --nur-pakete`
3. Für jede Figur den Ablauf oben abarbeiten. Abgelegt wird nur, was in der Probe klar erkennbar ist. Sonst
   „Name: Grund“ merken.
4. `python3 -m cudi_video figur-bericht <ID>` gibt `DATEIEN: [...]` aus. Diese Dateien per Artifact-Werkzeug hochladen:
   erst `read`, dann `publish` mit `asset: true` und `file_paths`.
5. `python3 -m cudi_video figur-bericht <ID> --adressen '{Pfad: url}' --offen '[…]'` ausführen.
6. Im selben Schritt ablegen:
   - ArtifactData `set` `studio/lernstand` mit der Datei aus der Zeile „STUDIO: …“.
   - ArtifactData `set` `figurenbau/<ID>` mit der Datei aus der Zeile „DOKUMENT: …“.

Schlägt etwas fehl, trotzdem mit den Schritten 5 und 6 weitermachen (`--offen` mit Grund), damit die App Bescheid weiß.
