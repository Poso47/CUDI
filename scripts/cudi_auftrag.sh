#!/usr/bin/env bash
# CUDI-App: einen Auftrag in einer Claude-Cloud-Sitzung ausführen – Pakete sicherstellen, dann rendern.
#   bash scripts/cudi_auftrag.sh '<auftrag als json>'
#   bash scripts/cudi_auftrag.sh --weiter <id>        (nach Claudes Übersetzung)
# Alle Dateien landen in video_output/ (nicht im Git).
set -uo pipefail
cd "$(dirname "$0")/.."
CHECK="import edge_tts, PIL, numpy, requests, yaml, bs4, lxml"
# Immer „python3 -m pip“: So landen die Pakete in genau dem Python, das danach rendert
# (ein loses „pip“ gehört in manchen Cloud-Umgebungen zu einem anderen Python).
pyinstall() { python3 -m pip install -q --disable-pip-version-check "$@" -r cudi_video/requirements.txt >> /tmp/cudi_pip.log 2>&1; }
if ! python3 -c "$CHECK" 2>/dev/null; then
  echo "Pakete werden installiert …"
  python3 -m pip --version > /dev/null 2>&1 || python3 -m ensurepip -q > /tmp/cudi_pip.log 2>&1 \
    || (apt-get update -qq && apt-get install -y -qq python3-pip) >> /tmp/cudi_pip.log 2>&1
  pyinstall || pyinstall --break-system-packages || pyinstall --user --break-system-packages || true
  python3 -c "$CHECK" 2>/dev/null || { echo "FEHLER: Python-Pakete ließen sich nicht installieren:"; tail -5 /tmp/cudi_pip.log; }
fi
if ! command -v ffmpeg > /dev/null; then
  echo "ffmpeg wird installiert …"
  (apt-get update -qq && apt-get install -y -qq ffmpeg fonts-inter) > /tmp/cudi_apt.log 2>&1 || echo "FEHLER: ffmpeg fehlt"
fi
if [ "${1:-}" = "--weiter" ]; then
  exec python3 -m cudi_video auftrag --weiter "${2:-}"
fi
exec python3 -m cudi_video auftrag "$@"
