#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "python3 krävs för att starta appen." >&2
  exit 1
fi

if [[ ! -x "$ROOT_DIR/venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$ROOT_DIR/venv"
fi

VENV_PY="$ROOT_DIR/venv/bin/python"
export PIP_DISABLE_PIP_VERSION_CHECK=1
"$VENV_PY" -m pip install -q -r "$ROOT_DIR/requirements.txt"

HOST="${APP_HOST:-0.0.0.0}"
REQUESTED_PORT="${APP_PORT:-8000}"
export START_HOST_CHECK="$HOST"
export START_PORT_CHECK="$REQUESTED_PORT"

AVAILABLE_PORT="$("$VENV_PY" - <<'PY'
import os
import socket

host = os.environ.get("START_HOST_CHECK", "0.0.0.0")
base_port = int(os.environ.get("START_PORT_CHECK", "8000"))

for port in range(base_port, base_port + 25):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            continue
        print(port)
        break
else:
    raise SystemExit("Ingen ledig port hittades i intervallet.")
PY
)"

if [[ "$AVAILABLE_PORT" != "$REQUESTED_PORT" ]]; then
  echo "Port $REQUESTED_PORT är upptagen. Startar i stället på $AVAILABLE_PORT." >&2
fi

export APP_HOST="$HOST"
export APP_PORT="$AVAILABLE_PORT"
"$VENV_PY" -m alembic upgrade head

LOCAL_URL="http://127.0.0.1:$APP_PORT"
echo "Lokal URL: $LOCAL_URL"

if command -v tailscale >/dev/null 2>&1; then
  TAILSCALE_IP="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
  if [[ -n "$TAILSCALE_IP" ]]; then
    echo "Tailscale URL: http://$TAILSCALE_IP:$APP_PORT"
  fi
fi

exec "$VENV_PY" -m uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT"
