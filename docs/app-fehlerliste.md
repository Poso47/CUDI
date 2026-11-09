# CUDI-App: Fehlerliste (Fehlersuche mit Playwright, 390 px, hell und dunkel)

Geprüft mit `?demo=1`, `?demo=frei`, `?demo=limit` und einer `window.claude`-Attrappe (Datenbank im Speicher,
`fire_trigger`/`create_session` mit Modi Erfolg, Fehler, Erlaubnis fehlt, 429/Limit, langsam, Sitzung FAILED/BLOCKED/COMPLETED).
Quelltext: `docs/cudi-app-artefakt.html`.

| Nr | Fehler | Ursache | Status |
|----|--------|---------|--------|
| 1 | Kachel „Fakten“ sprang zu Ranking | `data-go="fakten"` wurde zu `goTab("ranking")` umgeleitet, kein eigenes Formular | behoben: eigene Seite `#fakten` (Thema, Anzahl 3–10, Mehr Optionen), Auftrag `{"art":"fakten","thema","plaetze","sprache","streng"}` |
| 2 | Karte/Rolle/Speicherbedarf für Fakten fehlten | Art unbekannt (Karte ohne Artname, Speicherbedarf wie 2 Videos, Vorlieben als „Ranking“) | behoben: Art-Namen, Rolle Faktenprüfer, 1 Video, Vorlieben je Art |
| 3 | Firma-Vorschlag „Fakten-Idee“ startete ein Ranking | `baseRanking({thema})` | behoben: startet `art: "fakten"`, passende Themen |
| 4 | Dunkelmodus: Text auf Knöpfen falsch | `--on-accent: var(--on-accent)` (zyklisch, ungültig) | behoben: `#0c0e16` auf Cyan |
| 5 | Start scheitert am Limit: Auftrag wurde gelöscht, Meldung „Cloud antwortet nicht“, kein Ausweg | `startJob` löschte den Auftrag bei jedem Fehler | behoben: Auftrag bleibt (Status „Limit erreicht“), Hinweis + Knopf „Im Notbetrieb erstellen“, danach Status „im Notbetrieb“ |
| 6 | Automatischer Neustart nach Limit-Fehler lief sinnlos erneut | `autoRetry` kannte das Limit nicht | behoben: Limit-Fehler werden nicht erneut gestartet; scheitert ein Neustart am Limit, wird die Limit-Karte gezeigt |
| 7 | Manueller „Neu starten“ bei Limit: nur allgemeine Fehlermeldung | `restartJob` | behoben: Limit-Meldung, Karte mit Notbetrieb-Knopf |
| 8 | Notbetrieb-Link nur für Ranking/Story/Reportage | `nbIssueOrder` | behoben: alle Arten (Ranking, Fakten, Story, Reportage, Satire, Clip); Bearbeiten/Veröffentlichen bleiben „nur mit Claude“; Space-Adresse nur für Ranking/Story |
| 9 | Banner blieb nach Übergabe an den Notbetrieb stehen | `callLimit` wurde nie zurückgesetzt | behoben |
| 10 | Nach dem Start sprang die Seite nach 0,9 s zu „Videos“, auch wenn man schon woanders war | feste `setTimeout` | behoben: nur, wenn man noch auf dem Formular ist |
| 11 | Karte „Fehler“ mit Limit-Text hatte keinen Notbetrieb-Knopf | – | behoben |

Erledigt: 11 gefunden, 11 behoben. Klickstrecke (Kacheln, Zurück, alle Formulare gültig/ungültig, Doppelklick, Video speichern, Bewerten, Löschen
mit Ja/Nein, Neu starten, Veröffentlichen, Skelett → Video, Tabs, ungültiger Hash, Direktlink) ohne Konsolenfehler, kein Quer-Scrollen bei 390 px.

## Offen / bewusst so
- Erklärvideo bleibt hinter `CFG.felder.erklaer` ausgeblendet, bis `job.py` die Art kennt (ehrlicher Hinweis statt Formular); im Notbetrieb nicht vorgesehen.
- Firma-Ideen mit Bereich „fakten“ ohne Auftrag bleiben „nur zum Lesen“ (Thema ist ein Satz, kein Suchbegriff).
- Notbetrieb-Backend (alle Arten, Kommentar mit Ergebnis) liegt beim Agenten „Notbetrieb-voll“; die Seite öffnet nur das Issue mit dem Auftrag im App-Format.
- Der Bearbeiten-Editor wurde in dieser Runde nicht erneut durchgeklickt (unverändert).
