#!/bin/sh
# CUDI starten (macOS/Linux). Beim ersten Start wird alles Noetige in .venv installiert.
#   ./cudi_starten.sh            Fenster
#   ./cudi_starten.sh --cli      Chat im Terminal
#   ./cudi_starten.sh --diagnose Selbstdiagnose
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
    echo "Python 3.10 oder neuer wird benoetigt: https://www.python.org"
    exit 1
fi
if [ ! -x .venv/bin/python ]; then
    echo "Erster Start: CUDI wird eingerichtet (das dauert einige Minuten) ..."
    "$PY" -m venv .venv
fi
if [ ! -f .venv/cudi_installiert.txt ]; then
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements-core.txt
    echo installiert > .venv/cudi_installiert.txt
fi
if [ -f .env ] && grep -q "^ANTHROPIC_API_KEY=" .env; then
    .venv/bin/python -c "import anthropic" 2>/dev/null || .venv/bin/python -m pip install "anthropic>=1.0.0"
fi
exec .venv/bin/python main.py "$@"
