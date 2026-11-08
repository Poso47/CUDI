---
name: cloud-probelauf
description: Echten App-Auftrag in der Cloud testen (geplante Aufgabe CUDI-Auftrag) und Ergebnis prüfen.
---
# Cloud-Probelauf

1. Auftrag als `jobs/<id>` per ArtifactData anlegen (gleiches JSON wie die App, `'` als `'`).
2. `fire_trigger` trig_01BniK2S5eVdSFKd18JZqBio mit dem JSON als `text`; Antwort `session_id: "cse_…"` = `session_…` → in `jobs/<id>.session` eintragen.
3. Fortschritt: `get_session` (WORKING während des Renderns). Nicht pollen – `send_later` in ~10 Min.
4. Ergebnis: `results/<id>`; Video als Asset (Artifact read mit `path` = Asset-ID), Bilderbogen ≤ 1600 px.
5. Anweisung der Aufgabe ändern (`update_trigger`) nur mit ausdrücklichem OK des Nutzers.
