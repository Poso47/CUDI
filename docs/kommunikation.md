# Kommunikation: jeder Auftrag als klarer Prompt

Wunsch des Nutzers: Jede Kommunikation läuft als vollständiger, klarer Prompt mit einem eindeutigen Ziel. Das gilt
vom Nutzer zur Hauptsitzung, von der Hauptsitzung zu den Agenten und zwischen Agenten. So gibt es keine Rückfragen,
keine Suchschritte und keine halbe Arbeit, und es wird weniger Nutzungslimit verbraucht.

## Ablauf

1. **Nutzer → Hauptsitzung:** Der Nutzer schreibt frei, auch kurz oder umgangssprachlich. Die Hauptsitzung macht
   daraus einen **Auftrags-Prompt** nach der Vorlage unten und zeigt ihn dem Nutzer kurz („So habe ich dich
   verstanden“). Bei echten Unklarheiten fragt sie einmal gezielt nach, sonst legt sie direkt los.
2. **Hauptsitzung → Agent:** Agenten bekommen immer den vollständigen Auftrags-Prompt, nie nur „mach X“.
3. **Agent → Hauptsitzung:** Der Agent liefert einen **Bericht** nach der Berichtsvorlage, nicht frei formuliert.
4. **Agent → Agent / Folgeauftrag:** Übergaben laufen ebenfalls als Auftrags-Prompt. Die Hauptsitzung gibt
   Ergebnisse weiter (Agenten sprechen nicht direkt miteinander).
5. **Ergänzungen** während der Arbeit (`SendMessage`) heißen „Ergänzung vom Projektleiter“ und nennen nur, was sich
   ändert. Der Rest des Auftrags bleibt gültig.

## Vorlage Auftrags-Prompt

```
ZIEL: <ein Satz: was soll am Ende für den Nutzer besser sein>
WARUM: <Nutzerwunsch in eigenen Worten, ggf. Zitat>
GRUNDSÄTZE (immer): kostenlos · nie lügen, auch nicht durch Formulierung · keine Fehlschläge (Ausweichwege) ·
  Qualität vor „funktioniert irgendwie“ · sparsam (wenig Schritte/Ausgaben) · nur geprüfte, fertige Ergebnisse ·
  keine Zugangsdaten in Repo/Chat · Deutsch
KONTEXT: <Repo, Zweig, relevante Dateien/Module, was es schon gibt, Stolperfallen>
AUFGABE:
  1. <konkreter Schritt>
  2. ...
NICHT TUN: <Grenzen: keine Merges, keine fremden Dateien, kein update_trigger usw.>
ABNAHME: <messbar: Tests grün, Probelauf, Bilderbogen, Datei X enthält Y>
BERICHT: Vorlage „Bericht“, höchstens 15 Zeilen
MODELL/PRIORITÄT: haiku (mechanisch) | sonnet (Neuentwicklung) · Warteschlange max. 2 Agenten
```

## Vorlage Bericht

```
ERGEBNIS: fertig | teilweise | blockiert – <ein Satz>
GEÄNDERT: <Dateien/Zweig/Commit>
GEPRÜFT: <Tests, Probelauf, was genau gesehen wurde>
OFFEN/RISIKEN: <was nicht geht und warum, ehrlich>
NÄCHSTER SCHRITT: <Vorschlag, falls sinnvoll>
```

## Beispiel

Nutzer: „Ich möchte, dass die deutschen Nachrichten auch getrackt werden, aber von anderen Ländern …“

```
ZIEL: Morgens ein wahres Welt-Briefing; Deutschland aus Sicht anderer Länder.
WARUM: Nutzer will ungefilterte, abgeglichene Nachrichten (Methode Salim Samatou: ferne Länder vergleichen,
  nur Übereinstimmendes, Interessenkonflikte ausklammern, 5 Zeilen, täglich).
AUFGABE: 1. Mitarbeiter „Welt-Blick“ (RSS/GDELT, ≥ 3 Länder einig) … 2. „Morgen-Briefing“ täglich 6 Uhr …
NICHT TUN: Unbelegtes als Tatsache; Meinungen über Personen; Merge.
ABNAHME: Tests grün, echter lokaler Lauf, Beispielauszug.
```
