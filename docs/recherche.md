# Recherche-Agent einrichten und verstehen

Der Recherche-Agent (`cudi_video/recherche/`) sucht im Internet, öffnet Seiten, liest sie, prüft Datum und Herkunft und gleicht mit
unabhängigen Quellen ab – für Reportage, Satire, freie Faktenthemen, Ideen, Regie-Wissen und den Rechercheur der Firma.

## Ablauf (`recherchiere(frage, bereich)`)
1. Frage zerlegen -> bis zu 4 Suchanfragen (deutsch zuerst, Region DE; englisch nur ergänzend zum Abgleich; Behörden-Seite per `site:`).
2. Suchwege der Reihe nach, jeder einzeln abgesichert: Claude-Websuche (nur App-Lauf, Aufgabe `recherche_suche`) -> Brave (optional) ->
   DuckDuckGo-HTML -> GDELT (aktuelle Nachrichten) -> Fachquellen (Eurostat, Weltbank, Europe PMC).
3. Treffer ordnen (Primärquellen vor Medien vor Blogs, Foren nie) und höchstens `CUDI_RECHERCHE_SEITEN` (Standard 10) Seiten lesen
   (robots.txt, Zeit-/Größenlimit, keine Logins/Cookies, Cache 24 h).
4. Aussagen nur mit WÖRTLICHEM Zitat + Adresse + Datum + Eigentümer. Datum: Meta-Tags, JSON-LD, `<time>`, Text, zuletzt HTTP-Header (zählt nicht für den Vergleich).
5. Abgleich: „bestätigt“ = mindestens 2 unabhängige Gruppen (`eigentuemer.gruppiere`); Widersprüche werden ausgewiesen, nie geglättet;
   andere Zeiträume/Zeitspannen sind kein Widerspruch, ältere Stände werden „veraltet“ markiert (Grenze je Bereich, `ablauf.MAX_ALTER`).
6. Ergebnis `{aussagen, widersprueche, quellen, stand, schritte}`; `bericht(e)` liefert den Prüfbericht-Abschnitt „Recherche“.

## Wikipedia-Regel
Wikipedia zählt nur in den Bereichen `fakten` und `geschichte`, nur zusätzlich zu einer Nicht-Wikipedia-Quelle und nur ohne
Manipulations-/Streitzeichen (MediaWiki-API: Bausteine wie Neutralität/POV/Belege fehlen, Rückgängig-Häufung, viele Änderungen in 30 Tagen,
Seitenschutz wegen Streit). Fällt die Prüfung aus, zählt Wikipedia nicht. Überall sonst ist Wikipedia höchstens ein Suchhinweis.

## Optional: Brave Search (kostenlos)
1. Auf https://brave.com/search/api/ ein Konto anlegen und die kostenlose Stufe wählen (Schlüssel „Data for Search“).
2. Schlüssel NUR als GitHub-Secret `CUDI_BRAVE_API_KEY` eintragen (Repository -> Settings -> Secrets and variables -> Actions); lokal als Umgebungsvariable.
   Nie in den Chat, ins Repo oder in Logs. Die Workflows reichen das Secret bereits durch (ideen, wissen, briefing, clipscout, recherche, notbetrieb).
3. Ohne Schlüssel läuft DuckDuckGo-HTML (kann Captcha zeigen -> Weg wird übersprungen) und GDELT.

Weitere Einstellungen: `CUDI_RECHERCHE=0` (aus), `CUDI_RECHERCHE_REGION=AT|CH` (Standard DE), `CUDI_RECHERCHE_SUCHEN`, `CUDI_RECHERCHE_CACHE=0`.
