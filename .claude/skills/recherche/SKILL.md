---
name: recherche
description: Recherche-Agent (cudi_video/recherche/) erweitern oder reparieren – Suchwege, Seiten lesen, Datum/Eigentümer, Abgleich, Wikipedia-Regel, Einbau in Reportage/Satire/Wissen/Ideen/verify.
---
# Recherche-Agent

- API: `suche(anfrage, sprache, zeitraum)`, `lese(url)`, `recherchiere(frage, bereich)`, `bericht(e)`, `seiten_als_quellen(e)`; aus mit `CUDI_RECHERCHE=0` (Tests setzen das in conftest; Recherche-Tests rufen die Funktionen direkt).
- Dateien: `web.py` (robots, Limits, SSRF-Schutz), `lesen.py` (Text/Datum/Typ), `suche.py` (Wege), `fachquellen.py`, `wikipedia.py`, `ablauf.py` (Aussagen/Abgleich), `cache.py` (24 h, Budget). Doku `docs/recherche.md`.
- Regeln: Aussage nur mit wörtlichem Zitat von einer SELBST geladenen Seite; „bestätigt“ ≥ 2 Gruppen nach `eigentuemer.gruppiere`; Header-Datum zählt nicht; Vergleich nur bei gleichem Gegenstand (`_thema_gleich`), gleichen Einheiten, Zeitbezug.
- Wikipedia nur `fakten`/`geschichte`, nur mit Zweitquelle und bestandener `pruefe_seite`; sonst Suchhinweis. Prüfung fällt aus = zählt nicht.
- Claude-Websuche (`recherche_suche`) nur wenn `handoff.enabled()`; im Notbetrieb (Gemini ohne Internet) nie, sonst erfundene Adressen.
- Stolperfallen: Paketname `recherche.suche` ist die Funktion – im Test das Modul per `importlib.import_module("cudi_video.recherche.suche")` holen. DuckDuckGo/robots in der Cloud-Sandbox oft gesperrt (Weg wird übersprungen). Eurostat-API liefert teils alte Stände (Datum prüfen, „veraltet“). Schlüssel nie ausgeben.
- Einbau: reportage (`recherche_quellen`), satire (nur wenn < 2 Betreiber), `firma/wissen.py`, `firma/ideen.themenrecherche`, `verify/checkers.RechercheChecker` (nur freie Themen), Firma-Rolle `firma/recherche.py` + `firma-recherche.yml`.
