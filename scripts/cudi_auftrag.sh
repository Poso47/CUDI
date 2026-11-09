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
# Clip-Aufträge brauchen zusätzlich Spracherkennung und OpenCV
NEED_CLIP=0
if grep -qE '"art" *: *"clip"' <<< "${1:-}"; then NEED_CLIP=1; fi
if [ "${1:-}" = "--weiter" ] && grep -qE '"art": *"clip"' "video_output/auftrag-${2:-}/auftrag.json" 2>/dev/null; then NEED_CLIP=1; fi
if [ "$NEED_CLIP" = 1 ]; then CHECK="$CHECK, faster_whisper, cv2, yt_dlp"; fi
# Tempo: Ranking/Story/Reportage/Satire brauchen nur die kleine Liste (ohne OpenCV, Spracherkennung, Web-Server); nur Clip-Aufträge die ganze.
REQ=cudi_video/requirements-basis.txt
if [ "$NEED_CLIP" = 1 ]; then REQ=cudi_video/requirements.txt; fi
pyinstall() { python3 -m pip install -q --disable-pip-version-check --prefer-binary "$@" -r "$REQ" >> /tmp/cudi_pip.log 2>&1; }
T0=$(date +%s)
if ! python3 -c "$CHECK" 2>/dev/null; then
  echo "Pakete werden installiert …"
  python3 -m pip --version > /dev/null 2>&1 || python3 -m ensurepip -q > /tmp/cudi_pip.log 2>&1 \
    || (apt-get update -qq && apt-get install -y -qq python3-pip) >> /tmp/cudi_pip.log 2>&1
  for pause in 0 15 45; do                              # Paketserver kurz gestört: später erneut
    sleep "$pause"
    pyinstall || pyinstall --break-system-packages || pyinstall --user --break-system-packages || true
    python3 -c "$CHECK" 2>/dev/null && break
  done
  python3 -c "$CHECK" 2>/dev/null || { echo "FEHLER: Python-Pakete ließen sich nicht installieren:"; tail -5 /tmp/cudi_pip.log; }
fi
if ! command -v ffmpeg > /dev/null; then
  echo "ffmpeg wird installiert …"
  for pause in 0 20; do
    sleep "$pause"
    (apt-get update -qq && apt-get install -y -qq ffmpeg fonts-inter) > /tmp/cudi_apt.log 2>&1 && break
  done
  command -v ffmpeg > /dev/null || echo "FEHLER: ffmpeg fehlt"
fi
export CUDI_ZEIT_PAKETE=$(( $(date +%s) - T0 ))      # Zeitmessung: Prüfbericht „Zeiten“
if [ "${1:-}" = "--weiter" ]; then
  exec python3 -m cudi_video auftrag --weiter "${2:-}"
fi
exec python3 -m cudi_video auftrag "$@"
