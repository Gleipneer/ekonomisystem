#!/usr/bin/env bash
# Health check script for the household economics system.
# Returns 0 if healthy, 1 if not.
set -euo pipefail

HOST="${APP_HOST:-127.0.0.1}"
PORT="${APP_PORT:-8000}"
URL="http://${HOST}:${PORT}/healthz"

RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$URL" 2>/dev/null || echo "000")

if [ "$RESPONSE" = "200" ]; then
    echo "✅ Systemet lever — $URL returnerade 200"
    exit 0
else
    echo "❌ Systemet svarar inte — $URL returnerade $RESPONSE" >&2
    exit 1
fi
