"""
Generate a fresh Groww Trade API access token and write it to .env.

Run once each morning before the pipeline:
    python scripts/generate_groww_token.py

Prerequisites:
  - GROWW_API_KEY and GROWW_API_SECRET set in .env
    (from Groww → Profile → Trade API → Cloud API Keys)
  - Daily approval completed on the Groww Cloud API Keys portal
    (Groww requires you to approve the API key once per day before use)

Endpoint: POST https://api.groww.in/v1/token/api/access
Auth method: SHA256(api_secret + epoch_timestamp) checksum
"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests
from dotenv import dotenv_values, set_key

ENV_PATH = ROOT / ".env"
TOKEN_URL = "https://api.groww.in/v1/token/api/access"
TIMEOUT = 15


def generate_checksum(api_secret: str, timestamp: int) -> str:
    raw = f"{api_secret}{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()


def main() -> None:
    env = dotenv_values(ENV_PATH)

    api_key = env.get("GROWW_API_KEY", "").strip()
    api_secret = env.get("GROWW_API_SECRET", "").strip()

    if not api_key:
        api_key = input("Enter your Groww API Key: ").strip()
    if not api_secret:
        api_secret = input("Enter your Groww API Secret: ").strip()

    if not api_key or not api_secret:
        print("ERROR: GROWW_API_KEY and GROWW_API_SECRET are required")
        sys.exit(1)

    print("\nIMPORTANT: Make sure you have approved this API key today on the")
    print("Groww Cloud API Keys portal (Groww → Profile → Trade API → Cloud API Keys)")
    input("Press Enter to continue once approved...")

    timestamp = int(time.time())
    checksum = generate_checksum(api_secret, timestamp)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-VERSION": "1.0",
    }
    payload = {
        "key_type": "approval",
        "checksum": checksum,
        "timestamp": str(timestamp),
    }

    print(f"\nRequesting access token from Groww API...")

    try:
        resp = requests.post(TOKEN_URL, json=payload, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
    except requests.HTTPError as exc:
        print(f"ERROR: HTTP {exc.response.status_code} — {exc.response.text}")
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    token = body.get("token")
    expiry = body.get("expiry", "6 AM tomorrow")

    if not token:
        print(f"ERROR: No token in response: {body}")
        sys.exit(1)

    if not ENV_PATH.exists():
        ENV_PATH.write_text("")

    set_key(str(ENV_PATH), "GROWW_ACCESS_TOKEN", token)
    set_key(str(ENV_PATH), "GROWW_API_KEY", api_key)
    set_key(str(ENV_PATH), "GROWW_API_SECRET", api_secret)

    print(f"\nGroww access token saved to .env (expires: {expiry})")
    print("Run the pipeline now:\n  python -m pipeline.run --dry-run")


if __name__ == "__main__":
    main()
