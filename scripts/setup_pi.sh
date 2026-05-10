#!/bin/bash
# Run this ONCE from your Mac to register the pipeline on your existing Pi setup.
# Does NOT touch your existing docker-compose, nginx, or cloudflared config.
#
# Prerequisites:
#   - SSH key auth already set up for the Pi
#   - Docker already running on Pi (you confirmed this)
#
# Usage: ./scripts/setup_pi.sh PI_USER@PI_HOST
#   e.g. ./scripts/setup_pi.sh pi@raspberrypi.local

set -e

TARGET="${1:?Usage: $0 PI_USER@PI_HOST}"
BACKEND_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
echo "==> Setting up asset-dashboard pipeline on $TARGET"

# 1. Create pipeline directory (separate from existing compose project)
ssh "$TARGET" "mkdir -p ~/asset-dashboard-backend/data/{raw,output,processed}"

# 2. Copy only the pipeline compose file and .env
scp "$BACKEND_DIR/docker-compose.yml" "$TARGET:~/asset-dashboard-backend/docker-compose.yml"
scp "$BACKEND_DIR/.env"               "$TARGET:~/asset-dashboard-backend/.env"

# 3. Pull the image now so the first cron run doesn't wait
ssh "$TARGET" "cd ~/asset-dashboard-backend && docker compose pull pipeline"

# 5. Install cron jobs (Pi runs UTC; IST = UTC+5:30)
ssh "$TARGET" "
  (crontab -l 2>/dev/null | grep -v asset-dashboard-backend; cat <<'EOF'
# Asset Dashboard — market open +3 min (9:18 AM IST = 03:48 UTC)
48 3 * * 1-5 cd ~/asset-dashboard-backend && docker compose run --rm pipeline >> ~/asset-dashboard.log 2>&1
# Asset Dashboard — midday (12:00 PM IST = 06:30 UTC)
30 6 * * 1-5 cd ~/asset-dashboard-backend && docker compose run --rm pipeline >> ~/asset-dashboard.log 2>&1
# Asset Dashboard — after close +5 min (3:35 PM IST = 10:05 UTC)
5 10 * * 1-5 cd ~/asset-dashboard-backend && docker compose run --rm pipeline >> ~/asset-dashboard.log 2>&1
EOF
) | crontab -
"

echo ""
echo "==> Done. Pipeline is registered alongside your existing containers."
echo ""
echo "    The named Docker volume 'asset_dashboard_data' holds all output."
echo "    Your UI container can mount it with:"
echo "      volumes:"
echo "        - asset_dashboard_data:/app/data"
echo "      volumes: (top-level)"
echo "        asset_dashboard_data:"
echo "          external: true"
echo ""
echo "    Logs: ssh $TARGET 'tail -f ~/asset-dashboard.log'"
echo ""
echo "    GitHub Actions secrets needed (repo → Settings → Secrets → Actions):"
echo "      PI_HOST    = $(echo "$TARGET" | cut -d@ -f2)"
echo "      PI_USER    = $(echo "$TARGET" | cut -d@ -f1)"
echo "      PI_SSH_KEY = (paste your private SSH key)"
