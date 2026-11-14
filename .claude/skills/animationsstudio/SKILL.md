---
name: animationsstudio
description: Arbeit am CUDI-Animationsstudio (eigene Animation für Fakten/Erklär/Reportage/Satire/Schaubild) – Abteilungen, Anleitungen, Abgleich, Bildlehrer, neue Bausteine oder Figuren.
---
1. Wissen: `docs/gehirn/videoarten.md` → „Animationsstudio“ und „Abgrenzung der Videoarten“. Nicht das ganze Repo lesen.
2. Anleitung einer Abteilung ändern: `animation.STORYBOARD` / `SZENENBAU` / `schaubild.SZENEN_ANLEITUNG` (Bausteine) / `schaubild.KORREKTUR`.
3. Neuer Baustein: `zeichnen.ARTEN`, `pruefe_szene`, `Buehne.bild`, eine Zeile in `SZENEN_ANLEITUNG`, Test.
4. Neue/bessere Figur: erst Referenz-Scout (`python -m cudi_video referenzen "…"`), dann Agent `figuren-zeichner` bzw. 3D in `drei/szene3d.html` (Wünsche stehen in `firma_daten/bildregeln.json` → `figur_wuensche`).
5. Prüfen: `pytest tests/test_studio.py tests/test_schaubild.py -q`; sichtbar: einzelne Frames (`ErklaerScene`/Satire-Szenen/`animation.Bild`)
   als Bilderbogen statt ganzem Video (spart Zeit).
6. Abgrenzung: Satire nur über Politik/Mächtige (`videoarten.satire_ziel`), Erklärfragen nie als Satire.
