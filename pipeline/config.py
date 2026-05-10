from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# --- Zerodha Kite Connect ---
# Access token expires at 6 AM daily; update manually in .env each morning.
KITE_API_KEY = os.getenv("KITE_API_KEY", "")
KITE_ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "")

# --- Groww Trade API ---
# API key + secret from Groww → Profile → Trade API → Cloud API Keys.
# Run scripts/generate_groww_token.py each morning to refresh the access token.
GROWW_API_KEY = os.getenv("GROWW_API_KEY", "")
GROWW_API_SECRET = os.getenv("GROWW_API_SECRET", "")
GROWW_ACCESS_TOKEN = os.getenv("GROWW_ACCESS_TOKEN", "")

# --- Output ---
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "output" / "asset_dashboard.db"))
CSV_OUTPUT_DIR = Path(os.getenv("CSV_OUTPUT_DIR", DATA_DIR / "output"))

# --- Anthropic ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# --- Tuning ---
YFINANCE_MAX_WORKERS = int(os.getenv("YFINANCE_MAX_WORKERS", "4"))
