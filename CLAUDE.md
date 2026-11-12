# CLAUDE.md – Regeln und Wegweiser (kurz halten!)

Antworte auf Deutsch. Arbeite ziel- und lösungsorientiert und **sparsam**. Diese Datei wird in jeder Sitzung und von
jedem Agenten geladen – deshalb stehen hier nur Regeln und der Wegweiser. Details stehen im **Gehirn** (`docs/gehirn/`).

## Gehirn: erst nachschlagen, nicht neu suchen

CUDI Video (`cudi_video/`): kostenlose Hochformat-Videos (1080×1920, DE + EN) für TikTok/Shorts. Repo `Poso47/CUDI`.

| Thema | Datei im Gehirn | Skill |
|---|---|---|
| Videoarten (Ranking, Fakten, Story, Reportage, Satire, Erklär, Regie, Recherche) | `docs/gehirn/videoarten.md` | `neue-videoart`, `recherche` |
| CUDI-App (Artefakt), Cloud-Auftrag, Tabs, 3D-Büro | `docs/gehirn/app.md` | `app-artefakt`, `cloud-probelauf` |
| Notbetrieb ohne Claude (GitHub-Issue) | `docs/gehirn/notbetrieb.md` | `notbetrieb` |
| Upload, Betonung, Endkontrolle, Wahrheit, Musik | `docs/gehirn/qualitaet.md` | – |
| Clips (Erlaubnis, Scout, Twitch) | `docs/gehirn/clip.md` | `clip-engine` |
| Firma-Mitarbeiter auf GitHub, Briefing, Eigentümer | `docs/gehirn/firma.md` | `firma-mitarbeiter` |
| Tempo, Kosten, Ausweichwege | `docs/gehirn/betrieb.md` | `tempo`, `ausweg-finden` |
| Gelerntes aus Beispielvideos (Schaubild-Stil, 7 Content-Gesetze) | `docs/gehirn/vorbilder.md` | – |
| Auftrags- und Berichtsvorlage | `docs/kommunikation.md` | `pruefen-und-mergen` |

**Pflicht für alle (Hauptsitzung, Agenten, künftige Sitzungen):**
1. Nur die EINE Gehirn-Datei lesen, die zur Aufgabe passt, und dort gezielt suchen (grep) statt alles zu lesen. Nie das
   ganze Repo durchgehen, wenn der Wegweiser die Stelle nennt.
2. Nach erledigter Arbeit das Gelernte in die passende Gehirn-Datei oder den Skill schreiben (1–3 Zeilen: was, wo,
   Stolperfalle) – nicht in diese Datei. Neue Themen bekommen eine neue Zeile in der Tabelle.
3. Auftrags-Prompts nennen die Gehirn-Datei, die Code-Dateien und die Abnahme – der Agent liest nichts darüber hinaus.

## Grundsätze des Nutzers

Kostenlos · nie lügen, auch nicht durch Formulierung (nichts erfinden) · keine Fehlschläge (Ausweichwege) · Qualität ·
sparsam · keine Zugangsdaten ausgeben oder ins Repo · Fokus deutschsprachig · Clips nie bei „gesperrt“ ·
`update_trigger`/`delete_trigger` nur mit ausdrücklichem OK.

## Sparsam arbeiten (gleiche Qualität, weniger Verbrauch)

- Erst prüfen, ob ein Skill passt – dann macht die Hauptsitzung es selbst. Agenten nur für große, abgegrenzte Pakete:
  mechanisch → **haiku**, Neuentwicklung → **sonnet**. Höchstens **2 gleichzeitig**, jeder im eigenen Worktree.
- **Neue Funktionen und neue Videoarten baut die Hauptsitzung selbst** (Wunsch des Nutzers) – Agenten nur für Pflege, Prüfung und wiederkehrende Arbeit.
- Kleine Änderungen (ein Fehler, eine Datei, Doku) nie an einen Agenten geben – der Start kostet mehr als die Arbeit.
- Keine Wiederholungen: nichts erneut lesen, was schon im Gespräch oder im Gehirn steht; keine Probeläufe ohne neue Frage.
- Tests gezielt: nur betroffene Testdateien, die ganze Suite (`python -m pytest tests -q`) einmal vor dem Merge.
- Berichte ≤ 15 Zeilen, keine Diffs/langen Ausgaben; Bilderbogen ≤ 1600 px und nur einer.
- Keine wiederholten Läufe gegen gesperrte Dienste (429 o. Ä.) – einmal Ausweichweg, sonst später.
- Meldungen an den Nutzer: kurz, nur Ergebnis und was er tun muss.

## Kommunikation

- Nutzerwunsch → kurzer Auftrags-Prompt („So habe ich dich verstanden“), Vorlage in `docs/kommunikation.md`
  (ZIEL, WARUM, GRUNDSÄTZE, KONTEXT, AUFGABE, NICHT TUN, ABNAHME, BERICHT; Bericht endet mit SKILL).
- Agenten dürfen sich direkt schreiben (ANFRAGE/ANTWORT/HINWEIS, ≤ 3 Nachrichten je Anliegen), ändern nie fremde Dateien.
- Lösungsorientiert: Ursache lesen → reparieren → anderer kostenloser Weg → kleiner schneiden → erst dann fragen.
- Feste Agenten (`.claude/agents/`: `firma-techniker`, `app-gestalter`, `video-pruefer`) für wiederkehrende Arbeit.

## Entwickeln

- Tests: `python -m pytest tests -q` (lokal ~15 s; GitHub-Workflow „Tests“ installiert ffmpeg).
- Ausgaben nur in `video_output/` (gitignored); Arbeitsdateien in `video_output/_work/`.
- Commits auf Deutsch, Push auf den eigenen Zweig. **Merge: Der Nutzer hat dauerhaft erlaubt, fertige und in der Hauptsitzung geprüfte Pakete selbst per PR zu mergen** (ganze Suite grün); danach kurz berichten.
- Textprüfungen für Claude-Texte (Zahlen werttreu, Vornamen, ganze Wörter als Beleg): `cudi_video/textcheck.py`.
- Probeläufe in der Cloud: Auftrag als `jobs/<id>` anlegen (ArtifactData), `fire_trigger` mit dem JSON, dann
  `jobs/<id>.session` setzen; Ergebnis in `results/<id>`, Videos als Assets (Artifact read mit `path` = Asset-ID).
- Stolperfallen: kein `pkill -f <muster>`, wenn das Muster im selben Befehl steht (beendet die eigene
  Shell) – PIDs verwenden. `update_trigger`/`delete_trigger` blockt die Rechteprüfung ohne ausdrückliches OK. Wikidata-SPARQL: Blazegraph sieht OPTIONAL-Variablen in `NOT EXISTS` nicht
  zuverlässig (eigenen Stichtag dort neu binden). Pollinations nur nacheinander (sonst 402).
