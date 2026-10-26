# Ameisenreich

Echtzeit-Strategiespiel um Ameisenkolonien, inspiriert von „Ant Colony" (iOS), aber deutlich größer angelegt.
Eine einzige HTML-Datei ohne Abhängigkeiten. Läuft im Browser, als installierbare Web-App und als native iOS-App.

## Dateien

| Datei | Zweck |
|---|---|
| `game.html` | **Einzige Quelle** des Spiels (wird auch als claude.ai-Artifact veröffentlicht) |
| `build.sh` | Erzeugt `index.html` (eigenständige Web-App) und `www/` (für die iOS-App) |
| `manifest.webmanifest`, `sw.js` | Web-App-Manifest und Offline-Cache |
| `assets/` | App-Icons (180, 192, 512, 1024 px) |
| `ios/` | Xcode-Projekt (Capacitor 7, Swift Package Manager) |

Nach jeder Änderung an `game.html`: `./build.sh` (bzw. `npm run ios:sync` für die iOS-App).

## Spielinhalt

- **Duftspuren:** echte Pheromon-Simulation (Heim- und Futterspur). Eigene Spuren zeichnen oder Spuren (auch gegnerische) verwischen.
- **Drei Kasten:** Arbeiterin, Soldatin (folgt der Kampffahne), Späherin.
- **Unterirdischer Bau:** Querschnitt mit 12 Kammerplätzen. Brutkammer (+Platz, schnellere Brut), Vorratskammer (+Lager),
  Pilzgarten (stetiges Futter, auch im Winter), Wachkammer (+Bau-Lebenspunkte). Tiefere Kammern brauchen eine Verbindung.
- **Fünf Ameisenarten** mit eigenen Stärken: Waldameise, Blattschneiderameise, Wanderameise, Honigtopfameise, Feuerameise.
- **Jahreszeiten:** Frühling (schnellere Brut), Sommer (flink), Herbst (Fallobst, viel Regen), Winter (kein neues Futter,
  Ameisen zehren von Vorräten, Hunger tötet, keine Spinnen, keine KI-Angriffe).
- **Kampagne:** 9 Level mit Zielen (Futter, Kammern, Volksgröße, Spinne erlegen, Winter überstehen, Rivalen besiegen) und bis zu 3 Sternen.
- **Freies Spiel:** 1–3 Rivalen, 3 Kartengrößen, mit oder ohne Winter, Bestzeiten.
- **Forschung:** 6 Zweige à 3 Stufen.
- **Welt:** Nebel des Krieges, Wolfsspinnen, Regen, Blattläuse, Felsen, Übersichtskarte.
- **Speichern:** automatisch alle 20 s, beim Verlassen der App und über „Menü". „Fortsetzen" im Hauptmenü.

Desktop-Tasten: Leertaste Pause, 1–3 Tempo, A/S/D Brut, F Forschung, B Bau, Esc schließen.

## Als Web-App aufs iPhone (ohne App Store)

1. Den Ordner auf einen HTTPS-Webspace legen (z. B. GitHub Pages, Netlify).
2. Die Seite in Safari öffnen → Teilen → **Zum Home-Bildschirm**.
3. Das Spiel startet dann im Vollbild mit eigenem Icon und funktioniert offline.

## Als native iOS-App (App Store / TestFlight)

Voraussetzungen: Mac mit Xcode 15 oder neuer, Node.js 18+, für den App Store ein Apple-Developer-Konto (99 €/Jahr).

```sh
cd ameisenreich
npm install
npm run ios:sync      # baut www/ und kopiert es ins Xcode-Projekt
npm run ios:open      # öffnet ios/App/App.xcodeproj in Xcode
```

In Xcode:

1. Projekt „App" → Target „App" → **Signing & Capabilities**: eigenes Team wählen. Falls nötig die
   Bundle-ID `de.cudi.ameisenreich` auf eine eigene ändern (auch in `capacitor.config.json`).
2. Beim ersten Öffnen lädt Xcode die Capacitor-Pakete (Swift Package Manager) automatisch.
3. iPhone anschließen oder Simulator wählen → **Run** (⌘R).
4. Für TestFlight/App Store: **Product → Archive** → **Distribute App**.

Bereits eingerichtet: App-Icon (1024 px, ohne Transparenz), Startbildschirm, ausgeblendete Statusleiste,
Vollbild, Hoch- und Querformat, Verschlüsselungs-Erklärung (`ITSAppUsesNonExemptEncryption = NO`).

Hinweis: Die Schriften kommen von Google Fonts. Ohne Internet nutzt das Spiel die Systemschrift, es bleibt voll spielbar.
