# Ameisenreich

Echtzeit-Strategiespiel um Ameisenkolonien, inspiriert von „Ant Colony" (iOS), aber größer angelegt.
Läuft komplett im Browser (Desktop und iPhone/iPad), ohne Abhängigkeiten.

**Spielen:** `index.html` im Browser öffnen.
**Bearbeiten:** `game.html` ändern, danach `./build.sh` ausführen (erzeugt `index.html`).

## Spielprinzip
- **Duftspuren:** Arbeiterinnen finden Futter über echte Pheromon-Simulation (Heim- und Futterspur).
  Du kannst eigene Spuren zeichnen oder Spuren (auch gegnerische) verwischen.
- **Drei Kasten:** Arbeiterin (sammelt), Soldatin (kämpft, folgt der Kampffahne), Späherin (schnell, legt Spuren zu neuem Futter).
- **Forschung:** 6 Zweige mit je 3 Stufen (Kiefer, Panzer, Beine, Sozialmagen, Duftdrüse, Brutkammern).
- **Rivalen:** 1–3 KI-Kolonien, die sammeln, forschen und angreifen.
- **Welt:** Nebel des Krieges, Wolfsspinnen, Regen, nachwachsende Blattläuse, Felsen, 3 Kartengrößen.
- **Ziel:** Alle gegnerischen Königinnen besiegen, ohne die eigene zu verlieren.

Steuerung Desktop: Leertaste Pause, 1–3 Tempo, A/S/D Brut, F Forschung, Mausrad Zoom.
