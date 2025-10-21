#!/usr/bin/env bash
set -euo pipefail
PING_URL="${CUDI_PING_URL:-http://localhost:8000/ping}"
SEARCH_URL="${CUDI_SEARCH_URL:-http://localhost:8000/search?q=}"
CFG="./cudi.tools.json"
OUT="./cudi_diag.txt"

{
  echo "== CUDI DIAG = $(date -Iseconds)"
  echo "PWD: $(pwd)"
  echo "Node: $(node -v) | npm: $(npm -v)"
  echo "Python: $(python3 --version 2>&1)"
  echo "ENV CUDI_ENV=${CUDI_ENV:-}"
  echo "ENV CUDI_API_KEY=${CUDI_API_KEY:0:6}***"

  echo "WRITE test..."
  echo ok > _cudi_write_test.txt && rm -f _cudi_write_test.txt && echo "WRITE: OK" || echo "WRITE: FAIL"

  echo "PORTS (first 20):"
  (ss -lnt || netstat -lnt) 2>/dev/null | head -n 20

  if [ -f "$CFG" ]; then
    echo "TOOLS from $CFG:"
    cat "$CFG" | head -n 100
  else
    echo "TOOLS: $CFG missing"
  fi

  echo "PING $PING_URL"
  curl -sS -m 15 -w " CODE:%{http_code} TIME:%{time_total}\n" "$PING_URL" | head -c 200; echo

  echo "SEARCH ${SEARCH_URL}cudi+sanity"
  curl -sS -m 15 -w " CODE:%{http_code} TIME:%{time_total}\n" "${SEARCH_URL}cudi+sanity" | head -c 200; echo
} | tee "$OUT"
echo "== DONE -> $OUT"