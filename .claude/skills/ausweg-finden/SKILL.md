---
name: ausweg-finden
description: Lösungsorientiert weiterarbeiten, wenn ein Weg scheitert (Fehler, gesperrter Dienst, Limit, fehlendes Paket). Nutzen bei jedem Fehlschlag, bevor aufgegeben oder der Nutzer gefragt wird.
---
# Ausweg finden (Wunsch des Nutzers: nie aufgeben, aber Regeln einhalten)

Reihenfolge bei einem Fehlschlag:
1. **Ursache lesen**, nicht raten (Log, Fehlermeldung, `tail` statt ganzer Ausgabe). „Flake“ ist keine Ursache.
2. **Gleicher Weg, behoben**: fehlendes Paket, falscher Aufruf, Rechte, Zeitlimit → reparieren und einmal wiederholen.
3. **Anderer Weg zum selben Ziel** (kostenlos): andere Quelle/Dienst (z. B. Wikidata → Weltbank, Reddit-JSON → Arctic Shift → RSS, edge-tts → Piper, Hugging Face → GitHub), andere Technik, offline statt online.
4. **Kleiner schneiden**: Teilziel liefern, das sicher funktioniert, Rest als klarer nächster Schritt.
5. **Erst dann den Nutzer fragen** – mit dem, was versucht wurde, und konkreter Entscheidung, die nur er treffen kann.

Grenzen, die nie überschritten werden: nichts erfinden/lügen, keine Kosten, keine Zugangsdaten in Repo/Chat, keine wiederholten Läufe gegen gesperrte Dienste (einmal Ausweichweg, sonst später), keine Rechte ausweiten ohne OK, `update_trigger`/`delete_trigger` nur mit OK.

Danach: Was gelernt wurde, als Zeile in den passenden Skill (oder neuen Skill) schreiben – siehe `docs/kommunikation.md`, Abschnitt Lernen.
