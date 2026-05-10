"""
Extracts holdings from Groww via the official Trade API.

Docs: https://groww.in/trade-api/docs/curl/portfolio

Requires in .env:
    GROWW_ACCESS_TOKEN — daily token from Groww account → Settings → API

The API does not return live prices; current_price is left None
and filled in by the MarketDataEnricher (yfinance).
"""
from __future__ import annotations

import requests

from pipeline import config
from pipeline.extractors.base import BaseExtractor
from pipeline.models.holding import Holding
from pipeline.utils.logging import get_logger

log = get_logger(__name__)

_HOLDINGS_URL = "https://api.groww.in/v1/holdings/user"
_TIMEOUT = 15


class GrowwExtractor(BaseExtractor):
    @property
    def broker(self):
        return "groww"

    @property
    def asset_class(self):
        return "equity"

    def is_available(self) -> bool:
        return bool(config.GROWW_ACCESS_TOKEN)

    def extract(self) -> list[Holding]:
        if not self.is_available():
            log.warning("Groww: GROWW_ACCESS_TOKEN not set — skipping")
            return []

        headers = {
            "Authorization": f"Bearer {config.GROWW_ACCESS_TOKEN}",
            "Accept": "application/json",
            "X-API-VERSION": "1.0",
        }

        try:
            resp = requests.get(_HOLDINGS_URL, headers=headers, timeout=_TIMEOUT)
            resp.raise_for_status()
            body = resp.json()
        except requests.HTTPError as exc:
            log.error("Groww API HTTP error %s: %s", exc.response.status_code, exc.response.text)
            return []
        except Exception as exc:
            log.error("Groww API error: %s", exc)
            return []

        if body.get("status") != "SUCCESS":
            code = body.get("error", {}).get("code", "unknown")
            msg = body.get("error", {}).get("message", "")
            log.error("Groww API returned failure: [%s] %s", code, msg)
            return []

        payload = body.get("payload") or {}
        raw_holdings = payload if isinstance(payload, list) else payload.get("holdings", [])

        holdings: list[Holding] = []
        for row in raw_holdings:
            qty = float(row.get("quantity", 0) or 0)
            t1 = float(row.get("t1_quantity", 0) or 0)
            total_qty = qty + t1

            if total_qty <= 0:
                continue

            avg = float(row.get("average_price", 0) or 0)
            invested = total_qty * avg

            holdings.append(Holding(
                symbol=row["trading_symbol"].strip().upper(),
                isin=row.get("isin"),
                exchange="NSE",
                broker=self.broker,
                asset_class=self.asset_class,
                quantity=total_qty,
                avg_cost=avg,
                invested_value=invested,
                # Groww holdings endpoint does not include live price;
                # MarketDataEnricher fills this in via yfinance.
                current_price=None,
                current_value=None,
                unrealized_pnl=None,
                unrealized_pnl_pct=None,
            ))

        log.info("Groww: fetched %d holdings via API", len(holdings))
        return holdings
