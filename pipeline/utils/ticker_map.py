"""
Maps broker symbol strings to Yahoo Finance ticker strings.

NSE equities: append '.NS'
BSE equities: append '.BO'
Crypto:       use CoinGecko IDs or yfinance crypto pairs (e.g. BTC-USD)
Gold ETF:     GOLDBEES.NS (Nippon India Gold BeES)
"""

from __future__ import annotations

# Manual overrides — only needed when the auto-rule (.NS suffix) is wrong.
SYMBOL_OVERRIDES: dict[str, str] = {
    # Sovereign Gold Bond → proxy via gold ETF
    "SGBBSE": "GOLDBEES.NS",
    # Physical gold → spot price proxy
    "GOLD": "GC=F",
    # Digital gold → spot price proxy
    "DIGITAL_GOLD": "GC=F",
    # Crypto
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "MATIC": "MATIC-USD",
}

# Symbols that trade on BSE instead of NSE
BSE_SYMBOLS: set[str] = set()


def to_yf_ticker(symbol: str, exchange: str = "NSE", asset_class: str = "equity") -> str:
    if symbol in SYMBOL_OVERRIDES:
        return SYMBOL_OVERRIDES[symbol]

    if asset_class == "crypto":
        return f"{symbol}-USD"

    if asset_class == "gold":
        return SYMBOL_OVERRIDES.get(symbol, "GC=F")

    if exchange == "BSE" or symbol in BSE_SYMBOLS:
        return f"{symbol}.BO"

    return f"{symbol}.NS"
