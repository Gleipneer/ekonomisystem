#!/usr/bin/env bash
# Update and re-deploy the household economics system.
# Idempotent — safe to run repeatedly.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Uppdaterar economic_system ==="

# 1. Pull latest code
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "→ git pull..."
    git pull --ff-only || { echo "⚠ git pull misslyckades — kontrollera manuellt" >&2; exit 1; }
else
    echo "→ Inget git-repo — hoppar över git pull"
fi

# 2. Ensure venv
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ ! -x "$ROOT_DIR/venv/bin/python" ]]; then
    echo "→ Skapar venv..."
    "$PYTHON_BIN" -m venv "$ROOT_DIR/venv"
fi

VENV_PY="$ROOT_DIR/venv/bin/python"

# 3. Install/update deps
echo "→ Installerar beroenden..."
export PIP_DISABLE_PIP_VERSION_CHECK=1
"$VENV_PY" -m pip install -q -r "$ROOT_DIR/requirements.txt"

# 4. Run migrations
echo "→ Kör alembic upgrade head..."
"$VENV_PY" -m alembic upgrade head

# 5. Restart service (if using systemd)
if systemctl is-active --quiet economic-system 2>/dev/null; then
    echo "→ Startar om systemd-tjänsten..."
    sudo systemctl restart economic-system
    sleep 2
    if systemctl is-active --quiet economic-system; then
        echo "✅ Tjänsten startade om korrekt."
    else
        echo "❌ Tjänsten startade inte — kontrollera: journalctl -u economic-system" >&2
        exit 1
    fi
else
    echo "ℹ Ingen systemd-tjänst aktiv. Starta manuellt: ./scripts/start_app.sh"
fi

# 6. Health check
echo "→ Kör health check..."
sleep 1
if bash "$ROOT_DIR/scripts/healthcheck.sh"; then
    echo "=== Uppdatering klar ==="
else
    echo "⚠ Health check misslyckades efter uppdatering." >&2
fi
