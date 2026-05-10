"""
Step 2: Enriches holdings with live market data via yfinance.

Adds: current_price, current_value, unrealized_pnl, unrealized_pnl_pct,
      day_change_pct, sector, industry, market_cap, pe_ratio,
      fifty_two_week_high, fifty_two_week_low, dividend_yield.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

from pipeline import config
from pipeline.enrichers.base import BaseEnricher
from pipeline.models.holding import Holding
from pipeline.utils.logging import get_logger
from pipeline.utils.ticker_map import to_yf_ticker

log = get_logger(__name__)


def _fetch_info(ticker_str: str) -> dict:
    try:
        t = yf.Ticker(ticker_str)
        return t.info or {}
    except Exception as exc:
        log.warning("yfinance fetch failed for %s: %s", ticker_str, exc)
        return {}


def _safe(info: dict, key: str):
    val = info.get(key)
    return None if val in (None, "N/A", "None", "") else val


class MarketDataEnricher(BaseEnricher):
    def enrich(self, holdings: list[Holding]) -> list[Holding]:
        unique_tickers: dict[str, str] = {}  # symbol → yf ticker
        for h in holdings:
            yf_ticker = to_yf_ticker(h.symbol, h.exchange, h.asset_class)
            unique_tickers[h.symbol] = yf_ticker

        log.info("Fetching market data for %d tickers", len(unique_tickers))

        ticker_data: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=config.YFINANCE_MAX_WORKERS) as pool:
            futures = {
                pool.submit(_fetch_info, yf_ticker): symbol
                for symbol, yf_ticker in unique_tickers.items()
            }
            for future in as_completed(futures):
                symbol = futures[future]
                ticker_data[symbol] = future.result()

        enriched: list[Holding] = []
        for h in holdings:
            info = ticker_data.get(h.symbol, {})

            current_price = _safe(info, "currentPrice") or _safe(info, "regularMarketPrice")
            if current_price is not None:
                current_price = float(current_price)

            current_value = (current_price * h.quantity) if current_price else h.current_value
            invested = h.invested_value
            pnl = (current_value - invested) if current_value is not None else h.unrealized_pnl
            pnl_pct = ((pnl / invested) * 100) if pnl is not None and invested else h.unrealized_pnl_pct

            prev_close = _safe(info, "previousClose")
            day_change_pct = None
            if current_price and prev_close:
                day_change_pct = ((float(current_price) - float(prev_close)) / float(prev_close)) * 100

            enriched.append(h.model_copy(update={
                "current_price": current_price or h.current_price,
                "current_value": current_value,
                "unrealized_pnl": pnl,
                "unrealized_pnl_pct": pnl_pct,
                "day_change_pct": day_change_pct,
                "sector": _safe(info, "sector"),
                "industry": _safe(info, "industry"),
                "market_cap": _safe(info, "marketCap"),
                "pe_ratio": _safe(info, "trailingPE"),
                "fifty_two_week_high": _safe(info, "fiftyTwoWeekHigh"),
                "fifty_two_week_low": _safe(info, "fiftyTwoWeekLow"),
                "dividend_yield": _safe(info, "dividendYield"),
            }))

        log.info("Market data enrichment complete")
        return enriched
