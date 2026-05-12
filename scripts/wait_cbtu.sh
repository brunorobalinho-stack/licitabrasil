#!/bin/bash
# Aguarda o scrape CBTU terminar (ou timeout) e gera marcador
PID=$(cat /tmp/cbtu_scrape.pid 2>/dev/null)
if [ -z "$PID" ]; then
  echo "NO_PID"
  exit 1
fi

MAX_WAIT="${1:-60}"
WAITED=0
while [ "$WAITED" -lt "$MAX_WAIT" ]; do
  if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "DONE in ${WAITED}s"
    touch /tmp/cbtu_done.flag
    exit 0
  fi
  sleep 5
  WAITED=$((WAITED + 5))
done
echo "STILL_RUNNING after ${MAX_WAIT}s"
ps -p "$PID" -o etime= 2>/dev/null
exit 0
