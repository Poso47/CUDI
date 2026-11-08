#!/usr/bin/env bash
# Firma-Mitarbeiter: firma_daten/ als Bot-Commit sichern – nur wenn sich etwas geändert hat (ein Commit je Lauf).
# Aufruf: scripts/firma_commit.sh "<Mitarbeiter>"      (im Workflow, mit contents: write)
set -euo pipefail
branch="${GITHUB_REF_NAME:-main}"
git config user.name "cudi-firma[bot]"
git config user.email "cudi-firma[bot]@users.noreply.github.com"
# Kompakte Sammeldatei für die App (GitHub Pages: .../firma/firma.json); ein Fehler hier stoppt den Lauf nicht
python -m cudi_video.firma export || echo "firma.json nicht erzeugt."
mkdir -p docs/firma
git add firma_daten docs/firma
if git diff --cached --quiet; then
  echo "Keine Änderungen in firma_daten/ – kein Commit."
  exit 0
fi
git commit -q -m "Firma: ${1:-Daten} aktualisiert [skip ci]"
for attempt in 1 2 3 4 5; do
  if git push -q origin "HEAD:${branch}"; then
    echo "Gepusht (Versuch ${attempt})."
    exit 0
  fi
  sleep $((attempt * 3))
  git pull -q --rebase origin "${branch}" || { git rebase --abort 2>/dev/null || true; }
done
echo "Push nach fünf Versuchen nicht möglich." >&2
exit 1
