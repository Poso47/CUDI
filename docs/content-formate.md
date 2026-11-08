# Weitere Social-Media-Formate – Einschätzung und Plan

Stand: Plan für später. Heute gibt es Ranking, Fakten-Ranking, Reddit-Story, Erklärvideo, Clip und (neu) **Reportage**.
Jedes neue Format läuft als eigene Videoart mit eigener Prüfung; die Experimente (`cudi_video/experimente.py`) zeigen
danach, welches Format und welcher Look ankommt. Grundsatz bleibt: **nichts erfinden** – jede Zahl und jeder Name braucht
einen Beleg.

Skala: Aufwand S = unter 1 Tag, M = 1 bis 3 Tage, L = mehr. Wahrheitsrisiko: niedrig = Inhalt kommt aus geprüften Daten,
mittel = Texte entstehen frei, aber mit wörtlichem Beleg, hoch = Aussagen über Personen/Ereignisse oder Wertung.

| Format | Kurzbeschreibung | Aufwand | Datenlage | Wahrheitsrisiko | Empfehlung |
|---|---|---|---|---|---|
| **Quiz** | Frage, drei Antworten, Auflösung mit Beleg; Fragen aus bereits geprüften Fakten-/Ranking-Daten | S–M | sehr gut (Rankings/Fakten liegen vor) | niedrig, wenn Falschantworten aus echten Werten derselben Liste stammen | **als Nächstes**: hohe Interaktion (Kommentare), nutzt vorhandene Prüfung |
| **„Wusstest du?“** | 1 Fakt in 20 bis 30 s, Aha-Satz am Ende | S | gut (`facts.py` mit wörtlichem Beleg, Aha-Regel) | niedrig | **früh**: fast nur Zuschnitt des Fakten-Rankings auf einen Fakt |
| **Mythos vs. Fakt** | Verbreitete Behauptung, dann Richtigstellung mit Quelle | M | mittel: Mythen müssen belegt falsch sein (Wikipedia „Irrtümer“-Artikel, Faktenchecks) | mittel bis hoch (falsche Entkräftung wäre selbst Falschinformation) | nur mit ≥ 2 Quellen je Richtigstellung (Reportage-Prüfung wiederverwenden) |
| **Vergleich** | A gegen B mit 3 bis 5 Kennzahlen (Größe, Alter, Einwohner …) | M | gut (Wikidata + Abgleich wie im Ranking) | niedrig, solange nur gleich definierte Kennzahlen verglichen werden | gut machbar; Bezugsgrößen-Regel der Wahrheitsprüfung nutzen |
| **Countdown** | Ranking-Variante mit starker Spannungskurve, Platz 10 bis 1, ein Wert je Platz | S | vorhanden | niedrig | im Ranking-Format `zahl` weitgehend abgedeckt; nur Hook/Tempo als Experiment |
| **Tagesnachrichten-Kurzüberblick** | 3 bis 5 bestätigte Meldungen des Tages in 45 bis 60 s | M | gut (`firma_daten/news.json`, nur „bestätigt“ = ≥ 2 Quellen) | mittel (Überschriften verkürzen kann verfälschen) | Reportage-Pipeline je Meldung; täglich automatisch nur als Entwurf zur Freigabe |
| **Hintergrund-Erklärer** | „Warum ist das passiert?“ – Einordnung eines Ereignisses | M–L | mittel (Wikipedia + Fachquellen) | mittel bis hoch (Ursachenbehauptungen) | Erklärvideo + Reportage-Regeln: nur belegte Zusammenhänge, keine Ursache ohne Quelle |
| **Karussell-Bilder** | Hochformat-Bilderfolge (TikTok-Fotomodus, Instagram) statt Video | M | gut (vorhandene Slides, Bilder aus Commons) | niedrig (gleiche Inhalte wie Video) | günstig, weil kein Ton nötig; Export der Szenen als PNG-Serie + Beschreibung |
| **Zitat-/Personenporträt** | Kurzporträt oder Zitat einer Person | L | schwach bis mittel (Zitate sind oft falsch zugeschrieben) | **hoch** (Persönlichkeitsrechte, erfundene Zitate) | nur gemeinfreie, wörtlich belegte Zitate mit Quelle und Jahr; lebende Personen nur sachliche Daten; sonst weglassen |

## Reihenfolge-Vorschlag

1. „Wusstest du?“ und Quiz – am wenigsten neuer Code, größte Datenlage, kaum Wahrheitsrisiko.
2. Vergleich und Karussell-Bilder – bauen auf vorhandenen Daten und Rendern auf.
3. Tagesnachrichten-Kurzüberblick und Mythos vs. Fakt – brauchen die strenge Mehrquellen-Prüfung der Reportage und
   immer eine Freigabe vor dem Veröffentlichen.
4. Hintergrund-Erklärer und Personenporträt zuletzt (höchstes Wahrheits- und Rechterisiko).

## Gemeinsame Regeln für neue Formate

- Jede Aussage mit wörtlichem Beleg, Zahlen nur aus dem Beleg (`textcheck`, `reportage.pruefe_satz`).
- Heikle Themen (Gewalt, Unglücke, Krieg, Missbrauch) nur als sachliche Reportage (`firma/ideen.REPORTAGE_REGELN`).
- Neue Stellschrauben (z. B. Hook-Typ) in `experimente.KNOBS` eintragen – die Auswertung läuft dann automatisch mit.
- Erst nach genug Zahlen entscheiden, welches Format ausgebaut wird (Lern-Analyst, `firma_daten/lernen.json`).
