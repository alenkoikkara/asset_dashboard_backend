#!/bin/bash
# Run this each morning on your Mac after refreshing tokens.
# Merges fresh Kite + Groww tokens into the Pi's ~/.env and restarts the container.
#
# Usage: ./scripts/push_tokens.sh PI_USER@PI_HOST
#   e.g. ./scripts/push_tokens.sh charlie@raspberrypi.local

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
echo "==> Merging tokens into Pi's ~/.env ..."
scp "$ENV_FILE" "$TARGET:~/asset-dashboard.env"
ssh "$TARGET" "
  while IFS='=' read -r key value; do
    [[ -z \"\$key\" || \"\$key\" == '#'* ]] && continue
    if grep -q \"^\${key}=\" ~/.env 2>/dev/null; then
      sed -i \"s|^\${key}=.*|\${key}=\${value}|\" ~/.env
    else
      echo \"\${key}=\${value}\" >> ~/.env
    fi
  done < ~/asset-dashboard.env
  rm ~/asset-dashboard.env
  cd ~
  docker compose up -d --no-deps --force-recreate asset-dashboard-api
"

echo "==> Done. Tokens are live on the Pi."
echo "    To trigger pipeline now: curl -X POST 'http://raspberrypi.local:8002/api/pipeline/run?skip_ai=true'"
