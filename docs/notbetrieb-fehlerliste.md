# Notbetrieb: Fehlerliste (lokaler Durchlauf je Art, ohne Claude, ohne Schlüssel)

Lauf: `job.run_order(..., via_claude=False)`, `CUDI_SCHREIBEN` leer, keine `CUDI_LLM_*` – also der schlechteste Fall
(Modell-Kette komplett aus). Erwartung: Erfolg über Regelweg/Textbausteine oder ein ehrlicher, begründeter Abbruch.

| Art | Ergebnis | Bemerkung |
|---|---|---|
| ranking (Vorlage, 3 Plätze) | Video fertig | Textbausteine statt Erzählung |
| story (wholesome, kurz) | Video fertig | Lektorat per Regeln |
| fakten | ehrlicher Abbruch | Fakten brauchen ein Sprachmodell zum Formulieren; sagt es klar, erfindet nichts |
| reportage / satire | ehrlicher Abbruch | zu wenige unabhängige Quellen für das (zu vage) Testthema, nichts ergänzt |
| clip (YouTube-Link) | ehrlicher Abbruch | keine Erlaubnis des Creators bekannt; mit `bestaetigt_erlaubnis` läuft er weiter |

## Gefunden und behoben

1. **Art `fakten` fehlte** in `job.parse_order`/`run_order` → neu (`_fakten`, `planner.plan_facts`; Plätze 3–10).
2. **Notbetrieb nahm nur Ranking/Story/Reportage an** → jetzt alle Arten (`notbetrieb.NOTBETRIEB_ARTEN`); Story-Schritt
   „skelett“/„video“ wird „direkt Video“.
3. **Ein einziges Sprachmodell, bei 429 sofort Textbausteine** → Kette `CUDI_LLM_*` → `CUDI_LLM2_*` → `CUDI_LLM3_*`,
   je Anbieter ein zweiter Versuch nach kurzer Pause bei 408/425/429/5xx und Netzfehlern (nicht bei 401/404).
4. **Ergebniskommentar** zeigte keine Titel-Varianten und keine Endkontrolle; Videos ohne Beschreibungstext (Satire,
   Reportage) bekamen keinen Hinweis → ergänzt.
5. **Fakten ohne Modell**: Meldung „Es kamen keine Fakten zurück“ war unklar → nennt jetzt den Grund.
6. `CUDI_LLM2/3_API_KEY` werden im Kommentar geschwärzt (`SECRET_ENV`) und im Workflow durchgereicht.

## Offen / Beobachtung

- Clips von YouTube scheitern in der Cloud oft an der IP-Sperre (`ClipError.wiederholbar`); der Kommentar nennt den Grund.
- Fakten sind ohne erreichbares Modell nicht möglich (Absicht: nichts erfinden).
- Echter Test auf GitHub (Issue „CUDI Notbetrieb: Test Fakten“) steht aus – erst nach dem Merge durch den Projektleiter.

## Lückenliste: jede App-Funktion und ihr Notbetrieb-Weg

| App-Funktion | Notbetrieb | Stand |
|---|---|---|
| Start Ranking / Fakten / Story / Reportage / Satire / Clip | Issue mit JSON-Block, alle in einem Zug | geht (PR #69) |
| Start Erklärvideo | `art:"erklaer"`, Skript per Sprachmodell, Beleg je Szene | neu, geht |
| Story-Skelett vorher ansehen | kein Editor im Issue; „skelett“/„video“ werden direkt Video | Grund: es gibt keine Bearbeiten-Oberfläche im Issue; Ausweg: fertiges Video per „bearbeiten“ ändern |
| Bearbeiten (Ranking, Story) | neues Issue, `schritt:"bearbeiten"` + `bezug` + `aenderungen`, Grundlage aus dem Artefakt | neu, geht (Artefakt 14 Tage) |
| Bearbeiten (Fakten, Erklär, Reportage, Satire, Clip) | nicht vorgesehen (auch in der App nicht) | Absicht |
| Veröffentlichen/Hochladen später | neues Issue, `schritt:"hochladen"` + `bezug`, Video aus dem Artefakt | neu, geht; fehlende Zugangsdaten werden namentlich gemeldet |
| Hochladen im selben Auftrag | `hochladen` im Auftrag, `freigabe:false` | geht |
| Instagram/TikTok-Token | Secrets `CUDI_IG_*`, `CUDI_TIKTOK_ACCESS_TOKEN` jetzt im Notbetrieb-Workflow durchgereicht | behoben |
| Fakten bei Modellausfall | einmal nach 10 Min. erneut, dann klare Meldung | neu |
| Bewertungen 👍/👎 und Vorlieben | nur in der App-Ablage (`bewertungen/…`, braucht Claude-Sitzung zum Schreiben); im Issue gibt es keine Vorlieben | Grund: Ablage läuft über ArtifactData; Notbetrieb-Läufe lernen aus den bisher gespeicherten Bewertungen nicht. Ausweg: Wunsch im Auftrag formulieren |
| Löschen/Abbrechen | Issue schließen bzw. Workflow-Lauf abbrechen (GitHub) | geht ohne Claude |
| Firma-Mitarbeiter (Trends, News, Ideen, Putzmann, Welt, Briefing, Clip-Scout, Messung, Lernen) | GitHub-Workflows, kein Claude | geht schon immer; Ideen/Wissen nutzen `CUDI_LLM_*`, sonst Regeln |
| Firma-Tab/3D-Büro, Briefing, Kommunikation | liest Export `firma/stand` – wird bei Auftragsläufen mit Claude geschrieben; im Notbetrieb bleibt der Stand alt | Grund: nur die Claude-Sitzung schreibt in die App-Ablage; Pages-Fetch ist in Claude per CSP gesperrt |
| Ergebnisse in der App-Karte | Ergebnis nur als Issue-Kommentar + Artefakt, nicht in `results/…` | Grund: die Seite kann ohne Claude nichts lesen; Ausweg: Issue-Link |
