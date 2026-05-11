#!/bin/bash
# Run this ONCE from your Mac to register the asset-dashboard service on your Pi.
# The Pi's main docker-compose.yml at ~/ must already have the asset-dashboard-api service.
#
# Usage: ./scripts/setup_pi.sh PI_USER@PI_HOST
#   e.g. ./scripts/setup_pi.sh charlie@raspberrypi.local

set -e

TARGET="${1:?Usage: $0 PI_USER@PI_HOST}"
BACKEND_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

echo "==> Merging asset-dashboard env vars into Pi's ~/.env ..."
scp "$BACKEND_DIR/.env" "$TARGET:~/asset-dashboard.env"
ssh "$TARGET" 'python3 - <<'"'"'PYEOF'"'"'
import os

src = os.path.expanduser("~/asset-dashboard.env")
dst = os.path.expanduser("~/.env")

new_vars = {}
with open(src) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        new_vars[key.strip()] = value.strip()

existing = []
try:
    with open(dst) as f:
        existing = f.readlines()
except FileNotFoundError:
    pass

seen = set()
updated = []
for line in existing:
    stripped = line.strip()
    if stripped and not stripped.startswith("#") and "=" in stripped:
        key = stripped.split("=", 1)[0].strip()
        if key in new_vars:
            updated.append(f"{key}={new_vars[key]}\n")
            seen.add(key)
            continue
    updated.append(line)

for key, value in new_vars.items():
    if key not in seen:
        updated.append(f"{key}={value}\n")

with open(dst, "w") as f:
    f.writelines(updated)

os.remove(src)
print(f"Merged {len(new_vars)} vars into ~/.env")
PYEOF'

echo "==> Pulling image and starting asset-dashboard-api ..."
ssh "$TARGET" "
  cd ~
  docker compose pull asset-dashboard-api
  docker compose up -d --no-deps --force-recreate asset-dashboard-api
"

echo ""
echo "==> Done. asset-dashboard-api is running on port 8002."
echo "    The scheduler inside it will run the pipeline at:"
echo "      9:18 AM IST  — market open"
echo "      12:00 PM IST — midday"
echo "      3:35 PM IST  — after close"
echo ""
echo "    Logs: ssh $TARGET 'docker logs -f asset-dashboard-api'"
