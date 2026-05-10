#!/bin/bash
# Run this each morning on your Mac after refreshing tokens.
# Pushes the updated .env (with fresh Kite + Groww tokens) to the Pi.
#
# Usage: ./scripts/push_tokens.sh PI_USER@PI_HOST
#   e.g. ./scripts/push_tokens.sh pi@192.168.1.42

set -e

TARGET="${1:?Usage: $0 PI_USER@PI_HOST}"
BACKEND_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
ENV_FILE="$BACKEND_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env not found at $ENV_FILE"
  exit 1
fi

echo "==> Generating fresh Groww token..."
"$BACKEND_DIR/.venv/bin/python" "$BACKEND_DIR/scripts/generate_groww_token.py"

echo ""
echo "==> Pushing .env to Pi..."
scp "$ENV_FILE" "$TARGET:~/asset-dashboard-backend/.env"

echo "==> Done. Tokens are live on the Pi."
echo "    The pipeline will use them on the next cron run."
echo "    To trigger immediately: ssh $TARGET 'cd ~/asset-dashboard-backend && docker compose run --rm pipeline'"
