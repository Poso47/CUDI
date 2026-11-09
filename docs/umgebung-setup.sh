#!/usr/bin/env bash
# VORSCHLAG (nicht eingerichtet): Setup-Skript für die Cloud-Umgebung „Standard“ der CUDI-App.
#
# Warum: Jeder App-Lauf startet in einem frischen Container. Ohne Setup-Skript installiert scripts/cudi_auftrag.sh
# die Python-Pakete und ffmpeg bei JEDEM Lauf neu (Paketserver, Wartezeit ohne jede Arbeit am Video). Ein Setup-Skript
# läuft einmal beim Bauen des Containers (nicht bei jeder Fortsetzung) – danach findet der Lauf alles vor und
# cudi_auftrag.sh überspringt die Installation (CHECK besteht sofort).
#
# Einrichten (nur mit OK des Nutzers): Claude-Einstellungen -> Umgebung „Standard“ -> Setup-Skript -> diesen Inhalt einfügen.
# Hinweis: Das Skript sieht das Repo nicht garantiert; darum die Paketliste hier direkt (gleich wie cudi_video/requirements-basis.txt).
set -u
python3 -m pip install -q --disable-pip-version-check --prefer-binary \
  "requests>=2.31" "beautifulsoup4>=4.12" "lxml>=5.0" "PyYAML>=6.0" "Pillow>=10.3" "numpy>=1.26" "edge-tts>=7.0" \
  || python3 -m pip install -q --disable-pip-version-check --prefer-binary --break-system-packages \
  "requests>=2.31" "beautifulsoup4>=4.12" "lxml>=5.0" "PyYAML>=6.0" "Pillow>=10.3" "numpy>=1.26" "edge-tts>=7.0"
command -v ffmpeg > /dev/null || (apt-get update -qq && apt-get install -y -qq ffmpeg fonts-inter)
# Optional (nur wenn Bildprüfung per CLIP erwünscht ist; groß, ~0,5 GB): spart den Download im Lauf
# python3 -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu && python3 -m pip install -q open_clip_torch
true
