"""
Step 3: Enriches holdings with upcoming earnings and dividend dates.

Uses yfinance .calendar and .dividends for each ticker.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import pandas as pd
import yfinance as yf

from pipeline import config
from pipeline.enrichers.base import BaseEnricher
from pipeline.models.holding import Holding
from pipeline.utils.logging import get_logger
from pipeline.utils.ticker_map import to_yf_ticker

log = get_logger(__name__)


def _fetch_calendar(ticker_str: str) -> dict:
    try:
        t = yf.Ticker(ticker_str)
        result: dict = {}

        # Earnings
        try:
            cal = t.calendar  # dict with 'Earnings Date', 'Earnings High', etc.
            if cal and "Earnings Date" in cal:
                dates = cal["Earnings Date"]
                if isinstance(dates, list) and dates:
                    result["next_earnings_date"] = _to_date(dates[0])
                elif isinstance(dates, (datetime, date, pd.Timestamp)):
                    result["next_earnings_date"] = _to_date(dates)
        except Exception:
            pass

        # Next dividend
        try:
            divs = t.dividends
            if divs is not None and not divs.empty:
                today = pd.Timestamp.now(tz="UTC")
                future_divs = divs[divs.index > today]
                if not future_divs.empty:
                    next_idx = future_divs.index[0]
                    result["next_dividend_date"] = _to_date(next_idx)
                    result["next_dividend_amount"] = float(future_divs.iloc[0])
        except Exception:
            pass

        return result
    except Exception as exc:
        log.warning("Calendar fetch failed for %s: %s", ticker_str, exc)
        return {}


def _to_date(value) -> date | None:
    try:
        if isinstance(value, date):
            return value
        if isinstance(value, pd.Timestamp):
            return value.date()
        if isinstance(value, datetime):
            return value.date()
        return pd.Timestamp(value).date()
    except Exception:
        return None


class CalendarEnricher(BaseEnricher):
    def enrich(self, holdings: list[Holding]) -> list[Holding]:
        unique_tickers: dict[str, str] = {
            h.symbol: to_yf_ticker(h.symbol, h.exchange, h.asset_class)
            for h in holdings
        }

        log.info("Fetching calendar data for %d tickers", len(unique_tickers))

        calendar_data: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=config.YFINANCE_MAX_WORKERS) as pool:
            futures = {
                pool.submit(_fetch_calendar, yf_ticker): symbol
                for symbol, yf_ticker in unique_tickers.items()
            }
            for future in as_completed(futures):
                symbol = futures[future]
                calendar_data[symbol] = future.result()

        enriched = [
            h.model_copy(update=calendar_data.get(h.symbol, {}))
            for h in holdings
        ]
        log.info("Calendar enrichment complete")
        return enriched
