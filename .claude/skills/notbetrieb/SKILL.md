---
name: notbetrieb
description: Notbetrieb (Claude-Limit erreicht) pflegen oder testen – alle Videoarten per GitHub-Issue ohne Claude, Modell-Kette CUDI_LLM_*/2/3, Fakten-Auftrag, lokaler Probelauf je Art.
---

# Notbetrieb

- Weg: Issue (`cudi-auftrag` + JSON) -> `.github/scripts/auftrag.py` -> `notbetrieb.yml` -> `notbetrieb.py run/melden`.
  Alle Arten laufen in einem Zug (`NOTBETRIEB_ARTEN`); Story-Skelett wird direkt Video; bearbeiten/hochladen nur in der App.
- Texte: `llm.providers()` Kette CUDI_LLM_* -> CUDI_LLM2_* -> CUDI_LLM3_* (429/5xx: 1 Wiederholung), danach Regelweg.
  Fakten (`art:"fakten"`, `job._fakten`, `planner.plan_facts`) brauchen ein Modell – sonst ehrlicher Abbruch.
- Lokaler Probelauf je Art: Skript mit `prepare_order` + `job.run_order(order, job.job_folder(id), via_claude=False)`,
  `CUDI_SCHREIBEN` und `CUDI_LLM*` leer, `CUDI_BILDPRUEFUNG=0`; Ranking/Story ~3–5 Min., Reportage/Satire brechen bei
  zu wenig Quellen ehrlich ab. Ergebnisse: `docs/notbetrieb-fehlerliste.md`.
- Trockenlauf des Issue-Weges: `auftrag.extract_json` -> `build_json_order` -> `summary_line` (siehe `tests/test_notbetrieb_voll.py`).
- Echten Test-Issue nur nach Merge und nur der Projektleiter.
