"""
Generate a fresh Kite Connect access token and write it to .env.

Run once each morning before the pipeline:
    python scripts/generate_kite_token.py

Steps:
  1. Opens the Kite login URL in your browser
  2. You log in and are redirected to localhost (the URL will fail to load — that's fine)
  3. Copy the `request_token` value from the redirected URL
  4. Paste it here — the script exchanges it for an access token and updates .env
"""
from __future__ import annotations

import re
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values, set_key
from kiteconnect import KiteConnect

from pipeline.config import KITE_API_KEY

ENV_PATH = ROOT / ".env"

if not KITE_API_KEY:
    print("ERROR: KITE_API_KEY is not set in .env or config.py")
    sys.exit(1)

api_secret = dotenv_values(ENV_PATH).get("KITE_API_SECRET", "")
if not api_secret:
    api_secret = input("Enter your Kite API Secret: ").strip()

kite = KiteConnect(api_key=KITE_API_KEY)
login_url = kite.login_url()

print(f"\nOpening Kite login URL in your browser:\n{login_url}\n")
webbrowser.open(login_url)

print("After login you'll be redirected to a URL like:")
print("  https://127.0.0.1/?request_token=XXXXX&action=login&status=success")
print("(The page won't load — that's expected)\n")

raw = input("Paste the full redirected URL (or just the request_token value): ").strip()

match = re.search(r"request_token=([A-Za-z0-9]+)", raw)
request_token = match.group(1) if match else raw

try:
    session = kite.generate_session(request_token, api_secret=api_secret)
    access_token = session["access_token"]
except Exception as exc:
    print(f"ERROR generating session: {exc}")
    sys.exit(1)

# Write to .env (creates file if absent)
if not ENV_PATH.exists():
    ENV_PATH.write_text("")

set_key(str(ENV_PATH), "KITE_ACCESS_TOKEN", access_token)
set_key(str(ENV_PATH), "KITE_API_KEY", KITE_API_KEY)
if api_secret:
    set_key(str(ENV_PATH), "KITE_API_SECRET", api_secret)

print(f"\nAccess token saved to .env — valid until 6 AM tomorrow.")
print("Run the pipeline now:\n  python -m pipeline.run --dry-run")
