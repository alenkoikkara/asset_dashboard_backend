#!/bin/bash
# Run this ONCE from your Mac to register the pipeline on your existing Pi setup.
# Does NOT touch your existing docker-compose, nginx, or cloudflared config.
#
# Usage: ./scripts/setup_pi.sh PI_USER@PI_HOST
#   e.g. ./scripts/setup_pi.sh charlie@raspberrypi.local

set -e

TARGET="${1:?Usage: $0 PI_USER@PI_HOST}"
BACKEND_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

echo "==> Setting up asset-dashboard on $TARGET"

# 1. Create directory on Pi
ssh "$TARGET" "mkdir -p ~/asset-dashboard-backend/data/{raw,output,processed}"

# 2. Copy compose file and .env
scp "$BACKEND_DIR/docker-compose.yml" "$TARGET:~/asset-dashboard-backend/docker-compose.yml"
scp "$BACKEND_DIR/.env"               "$TARGET:~/asset-dashboard-backend/.env"

# 3. Pull image and start the API (scheduler runs inside it — no cron needed)
ssh "$TARGET" "
  cd ~/asset-dashboard-backend
  docker compose pull
  docker compose up -d asset-dashboard-api
"

echo ""
echo "==> Done. asset-dashboard-api is running on port 8002."
echo "    The scheduler inside it will run the pipeline at:"
echo "      9:18 AM IST  — market open"
echo "      12:00 PM IST — midday"
echo "      3:35 PM IST  — after close"
echo ""
echo "    Logs: ssh $TARGET 'docker logs -f asset-dashboard-api'"
echo ""
echo "    GitHub Actions secrets needed (repo → Settings → Secrets → Actions):"
echo "      PI_HOST    = $(echo "$TARGET" | cut -d@ -f2)"
echo "      PI_USER    = $(echo "$TARGET" | cut -d@ -f1)"
echo "      PI_SSH_KEY = (paste your private SSH key)"
