# Figuren-Abteilung – Figuren im Detail bauen

Ziel: Jede Figur, die ein Erklärvideo braucht, wird **so gebaut wie die Biene** (`FIGUREN.biene` in
`cudi_video/schaubild/drei/szene3d.html`). Sie ist im Detail modelliert und hat echte Materialien und Texturen. Ihre
Proportionen kommen aus einer Fotovorlage, und sie bewegt sich natürlich. **Nie** wird eine Figur aus ein paar Kugeln
und Kästen zusammengepuzzelt.

Die App startet diese Abteilung von selbst, wenn eine Skizze „fehlende Figuren“ meldet. Danach zeichnet sie automatisch
eine neue Skizze. „Video erstellen“ geht erst, wenn keine Figur mehr fehlt.

## Zuerst: freies Profi-Modell (Entscheidung des Nutzers vom 16.11.: realistisch statt selbst gebaut)

Selbst geschriebener 3D-Code wirkt bei Tieren und Menschen nie wie ein Foto. Deshalb gilt für **jede** Figur zuerst
dieser Weg. Selbst gebaut (Ablauf unten) wird nur, wenn er kein passendes Modell liefert.

1. `python3 -m cudi_video figur-modell "Kuh (cow)"` sucht freie 3D-Modelle (Objaverse/Sketchfab, nur CC0 oder CC BY,
   frei und kommerziell nutzbar). Ausgegeben wird ein Vergleichsbogen: links das Foto, je Zeile ein Modell aus
   4 Richtungen, mit Nummer, Urheber, Lizenz und „bewegt“ (Modell hat eigene Animationen). Den Bogen mit Read ansehen.
2. **Wählen.** Am wichtigsten ist der Realismus: fotorealistische oder eingescannte Modelle vor Cartoon- und
   Low-Poly-Modellen. Danach zählen die passende Art und Farbe zum Thema (z. B. Milchkuh schwarz-weiß), dann
   Bewegung, dann Vollständigkeit. Kaputte, halbe oder falsche Modelle nie nehmen.
3. `python3 -m cudi_video figur-modell-probe <name> <nr> --dreh <grad> --anker '{…}' [--boden-weg] [--clip <animation>]`
   ansehen.
   - `--dreh` so wählen, dass die Figur in der 0°-Ansicht im Dreiviertelprofil nach rechts schaut.
   - `--boden-weg` entfernt bei eingescannten Modellen mitgescannten Boden.
   - Die Anker (0–400, rot eingezeichnet) so oft verschieben, bis jeder genau auf seinem Teil sitzt.
4. `python3 -m cudi_video figur-modell-ablegen <name> <nr> --dreh … --anker '{…}' [--boden-weg] [--clip …] --anzeige "Kuh"`
   legt das Modell ab. Es landet im Lernstand unter `figuren` und hat Vorrang vor einer selbst gebauten Fassung.
   Urheber und Lizenz kommen automatisch in Beschreibung und Prüfbericht jedes Videos, das die Figur zeigt
   (Pflicht bei CC BY).

**Maßstab (vom Nutzer bestätigt am 16.11.):** Die eingescannte Kuh „Cow brown“ (Nyilonelycompany, CC BY, Nr. 1 im
Vergleichsbogen, `--dreh 90 --boden-weg`) ist „genau so“ gewollt. Realismus geht vor exakter Fellfarbe und vor eigener
Laufbewegung. Selbst gebaute Tiere sahen trotz Opus und 3 Runden nach Spielzeug aus, daher dieser Weg.

## Ablauf je Figur, wenn kein Profi-Modell passt (in der Figuren-Sitzung)

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
   genau auf seinem Teil sitzt. Mindestens 3 und höchstens 6 Runden, jede mit der Prüfliste unten. Meldet die Probe einen Fehler, steht die Meldung des
   Browsers in der Ausgabe.
6. **Ablegen:** `python3 -m cudi_video figur-ablegen <name> <datei.js> --anker '{…}' --anzeige "Imker"`. Der Befehl
   prüft die Figur und schreibt den Lernstand. Ab dann laden alle Video-Läufe die Figur automatisch.

## Realismus – Pflicht für jede Figur

Ziel ist eine Figur, die neben dem Foto **wie dasselbe Tier, dieselbe Person, dasselbe Ding** aussieht, nur als 3D-Modell.
Spielzeug- oder Knetfiguren-Look gilt als nicht fertig.

**Baukasten** (in `szene3d.html`, für realistische Formen):

- `organ(punkte, radien, mat, {flach})` baut Beine, Arme, Hälse, Schwänze und Finger. Die Dicke wechselt entlang des
  Glieds: Oberschenkel-Muskel, schmales Knie, Fessel, Huf. **Nie** glatte Röhren oder Zylinder für Glieder verwenden.
- `koerper(profil, mat, {liegend, skala, bei})` baut Rumpf, Kopf, Schnauze und Euter als Drehkörper aus einem
  Umriss-Profil. Das Profil wird vom Foto abgemessen (Brust tiefer als Bauch, Hüfthöcker, Widerrist).
- `fellmat(grund, {flecken, wuchs, laenge, dichte, wiederholung, relief})` erzeugt Fell mit organischen Flecken nach der
  Vorlage und Haaren in Wuchsrichtung als Relief. Für dichtes Fell zusätzlich `haare(...)`.
- `hautmat(farbe, {feucht})` ist für Haut, Schnauze, Euter und Lippen gedacht: Poren, feuchter Glanz.
- `auge(r, iris, {quer, pupille, lid})` baut ein echtes Auge: Augapfel, Iris, Pupille (`quer` bei Kuh, Ziege, Schaf),
  glänzende Hornhaut, Lid.

**Prüfliste je Probe-Runde.** Jeden Punkt gegen die Vorlage abhaken und im Kopf begründen:

1. Proportionen: Länge zu Höhe, Kopfgröße, Beinlänge, Halsansatz und Rückenlinie stimmen mit dem Foto überein.
2. Silhouette aus 0°, 90° und 180° ist sofort erkennbar, auch ohne Farbe.
3. Anatomie: Gelenke an der richtigen Stelle und in der richtigen Richtung (Kuh-Hinterbein: Sprunggelenk nach hinten),
   Muskeln, Knochenpunkte, Hufe, Krallen und Finger.
4. Gesicht in der Nahaufnahme: Augen mit Glanz und Lid, Nasenlöcher, Maul oder Lippen, Ohren mit Innenseite,
   Hörner und Haare.
5. Oberfläche: Fell, Haut oder Stoff mit Struktur. Fleckenmuster und Farben wie die Vorlage (gemessene Farben nutzen).
6. Typische Merkmale der Vorlage sind alle da (bei der Kuh z. B. Euter mit 4 Zitzen, Ohrmarke, Quaste, Blesse).

**Ablage nur nach bestandener Prüfung:**

- `figur-ablegen` verweigert die Ablage, wenn weniger als 3 Probe-Runden gemacht wurden.
- Es verweigert auch, wenn genau dieser Code nicht geprobt wurde.
- Und es verweigert, wenn der Detailgrad fehlt: mindestens 35 Teile, 5 Materialien, 3 mit Textur oder Relief,
  6 organische Formen und nicht mehr als 30 % Kästen, Zylinder oder Kegel.
- Die Probe zeigt die Werte und „FEHLT: …“ oben im Bild.

Lieber 6 gründliche Runden als 3 schnelle: Jede Runde behebt die größten Abweichungen aus der Prüfliste.

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
