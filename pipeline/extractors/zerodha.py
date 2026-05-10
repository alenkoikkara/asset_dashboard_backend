"""
Extracts holdings from Zerodha via the Kite Connect API.

Requires in .env:
    KITE_API_KEY     — from kite.trade/developers
    KITE_ACCESS_TOKEN — copy from Kite Console each morning (expires 6 AM daily)

If KITE_ACCESS_TOKEN is absent the extractor is skipped gracefully.
"""
from __future__ import annotations

from kiteconnect import KiteConnect

from pipeline import config
from pipeline.extractors.base import BaseExtractor
from pipeline.models.holding import Holding
from pipeline.utils.logging import get_logger

log = get_logger(__name__)


class ZerodhaExtractor(BaseExtractor):
    @property
    def broker(self):
        return "zerodha"

    @property
    def asset_class(self):
        return "equity"

    def is_available(self) -> bool:
        return bool(config.KITE_API_KEY and config.KITE_ACCESS_TOKEN)

    def extract(self) -> list[Holding]:
        if not self.is_available():
            log.warning("Zerodha: KITE_API_KEY or KITE_ACCESS_TOKEN not set — skipping")
            return []

        try:
            kite = KiteConnect(api_key=config.KITE_API_KEY)
            kite.set_access_token(config.KITE_ACCESS_TOKEN)
            raw = kite.holdings()
        except Exception as exc:
            log.error("Zerodha API error: %s", exc)
            return []

        holdings: list[Holding] = []
        for row in raw:
            qty = float(row.get("quantity", 0) or 0)
            t1 = float(row.get("t1_quantity", 0) or 0)
            total_qty = qty + t1

            if total_qty <= 0:
                continue

            avg = float(row.get("average_price", 0) or 0)
            invested = total_qty * avg

            last_price = row.get("last_price") or None
            current_price = float(last_price) if last_price else None
            current_value = (current_price * total_qty) if current_price else None

            pnl = float(row["pnl"]) if row.get("pnl") is not None else (
                (current_value - invested) if current_value is not None else None
            )
            pnl_pct = ((pnl / invested) * 100) if pnl is not None and invested else None

            day_change_pct = row.get("day_change_percentage")
            day_change_pct = float(day_change_pct) if day_change_pct is not None else None

            holdings.append(Holding(
                symbol=row["tradingsymbol"].strip().upper(),
                isin=row.get("isin"),
                exchange=row.get("exchange", "NSE"),
                broker=self.broker,
                asset_class=self.asset_class,
                quantity=total_qty,
                avg_cost=avg,
                invested_value=invested,
                current_price=current_price,
                current_value=current_value,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=pnl_pct,
                day_change_pct=day_change_pct,
            ))

        log.info("Zerodha: fetched %d holdings via API", len(holdings))
        return holdings
