---
name: app-artefakt
description: CUDI-App (Artefakt DYdRsKcD3BCN3SYxj6Y5Jt, Quelltext docs/cudi-app-artefakt.html) ändern, im Demo-Modus prüfen und unter derselben URL veröffentlichen.
---
# CUDI-App ändern

1. Quelltext: `docs/cudi-app-artefakt.html` (äußerer HTML-Rahmen fehlt absichtlich). Datenbank-Sammlungen: `jobs`, `results`, `bewertungen`, `skelette`, `bearbeitungen`, `firma/stand`, `kommunikation` (nur lesen).
   Aufbau: Tab-Leiste Start/Videos/Firma/Briefing/Kommunikation, Unterseiten `#ranking`…`#app` über `data-go`; Auftragsfelder, die `cudi_video/job.py` noch nicht kennt, erst hinter `CFG.felder` (Standard aus).
2. Prüfen ohne Cloud: lokal mit Playwright öffnen, `?demo=1` (Aufträge laufen), `?demo=frei`, `?demo=limit` (Notbetrieb-Banner). Lokal über `python -m http.server` mit vorangestelltem `<meta charset>` öffnen (sonst Umlaut-Fehler, `/_blob/…` als kleine Datei anlegen), `window.claude`-Attrappe per `addInitScript` für Auftragsprüfung (fire_trigger-Text lesen). Screenshot nur für mich: deviceScaleFactor 1, Handybreite 390 px.
3. Veröffentlichen: Artifact-Werkzeug mit `url` https://claude.ai/artifact/DYdRsKcD3BCN3SYxj6Y5Jt (vorher `read`, damit keine neuere Fassung überschrieben wird); Fähigkeiten nicht weglassen (Connector „Claude Code Remote“, db, assets).
4. Externe `fetch` zu fremden Hosts sperrt die Artefakt-CSP → Daten nur über die Datenbank oder Assets.
5. Keine Umgebungs-/Zugangsdaten in die Seite.
