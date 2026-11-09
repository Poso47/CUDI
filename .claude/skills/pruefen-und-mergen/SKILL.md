---
name: pruefen-und-mergen
description: Abnahme und Merge eines fertigen Pakets in Poso47/CUDI (Tests, PR, Merge, Bericht). Nutzen vor jedem Merge, auch bei „nur YAML/Doku“.
---
# Prüfen und mergen

1. Diff ansehen: `git diff --stat origin/main...HEAD`; Sicherheitsstellen (Zugangsdaten, `.env`, Secrets-Ausgaben) stichprobenartig prüfen.
2. **Ganze Suite immer**, auch bei Workflow-/Doku-Änderungen: `timeout 600 python -m pytest tests -q` (≈ 100 s; länger als 120 s → `run_in_background` + Monitor auf „passed|failed“). Tests prüfen auch YAML-Inhalte (z. B. `test_lernen.py::test_workflows_yaml`) – ein geänderter Aufruf kann sie brechen.
3. Commit auf Deutsch mit den Attributionszeilen, Push auf den eigenen Zweig.
4. PR (`create_pull_request`): Was/Warum, wie geprüft, Testzahlen. Merge (`merge_pull_request`, merge) – Nutzer hat dauerhaft erlaubt, geprüfte Pakete selbst zu mergen.
5. Die Benachrichtigungen „subscription.created“/„closed merged“ brauchen keine Aktion.
6. Dem Nutzer kurz berichten: was besser ist, was geprüft wurde, was offen ist.
7. Hauptordner gehört evtl. einem laufenden Agenten → eigene Änderungen in einem `git worktree` im Scratchpad machen, danach `git worktree remove`.
