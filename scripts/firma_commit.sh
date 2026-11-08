#!/usr/bin/env bash
# Firma-Mitarbeiter: firma_daten/ als Bot-Commit sichern – nur wenn sich etwas geändert hat (ein Commit je Lauf).
# Aufruf: bash scripts/firma_commit.sh "<Mitarbeiter>"      (im Workflow, mit contents: write)
# Konfliktfest: Läufe starten oft auf einem älteren Stand (anderer Mitarbeiter hat inzwischen committet).
# Darum: eigene Dateien sichern → auf den neuesten Stand setzen → eigene Dateien zurück, status.json nur um
# die eigenen Einträge ergänzen, firma.json neu erzeugen → committen → pushen (bis 5 Versuche).
set -euo pipefail
# Sich selbst vorher kopieren: das Zurücksetzen auf den neuesten Stand darf das laufende Skript nicht verändern
if [ -z "${FIRMA_COMMIT_KOPIE:-}" ]; then
  kopie="$(mktemp)"; cp "$0" "$kopie"; FIRMA_COMMIT_KOPIE=1 exec bash "$kopie" "$@"
fi
branch="${GITHUB_REF_NAME:-main}"
git config user.name "cudi-firma[bot]"
git config user.email "cudi-firma[bot]@users.noreply.github.com"
save="$(mktemp -d)"
mkdir -p firma_daten
# Eigene, geänderte/neue Dateien (ohne status.json) sichern
git add -A firma_daten
git diff --cached --name-only -- firma_daten | grep -v '^firma_daten/status.json$' > "$save/liste" || true
while IFS= read -r f; do if [ -f "$f" ]; then mkdir -p "$save/$(dirname "$f")"; cp "$f" "$save/$f"; else echo "$f" >> "$save/geloescht"; fi; done < "$save/liste"
touch "$save/geloescht"
[ -f firma_daten/status.json ] && cp firma_daten/status.json "$save/status_eigen.json" || echo '{}' > "$save/status_eigen.json"
git reset -q
for attempt in 1 2 3 4 5; do
  git fetch -q origin "$branch"
  git reset -q --hard "origin/$branch"
  while IFS= read -r f; do if [ -f "$save/$f" ]; then mkdir -p "$(dirname "$f")"; cp "$save/$f" "$f"; fi; done < "$save/liste"
  while IFS= read -r f; do rm -f "$f"; done < "$save/geloescht"
  python - "$save/status_eigen.json" <<'PY'
import json, sys, pathlib
p = pathlib.Path("firma_daten/status.json")
basis = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
eigen = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
alt = basis.get("mitarbeiter", {})
for name, eintrag in (eigen.get("mitarbeiter") or {}).items():
    if eintrag != alt.get(name) and (eintrag.get("letzter_lauf") or "") >= (alt.get(name, {}).get("letzter_lauf") or ""):
        alt[name] = eintrag
basis["mitarbeiter"] = alt
basis["erzeugt"] = max(basis.get("erzeugt") or "", eigen.get("erzeugt") or "")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(basis, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
PY
  # Kompakte Sammeldatei für die App; ein Fehler hier stoppt den Lauf nicht
  python -m cudi_video.firma export || echo "firma.json nicht erzeugt."
  mkdir -p docs/firma
  git add -A firma_daten docs/firma
  if git diff --cached --quiet; then
    echo "Keine Änderungen in firma_daten/ – kein Commit."
    exit 0
  fi
  git commit -q -m "Firma: ${1:-Daten} aktualisiert [skip ci]"
  if git push -q origin "HEAD:${branch}"; then
    echo "Gepusht (Versuch ${attempt})."
    exit 0
  fi
  sleep $((attempt * 3))
done
echo "Push nach fünf Versuchen nicht möglich." >&2
exit 1
