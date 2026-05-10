"""
Step 5b: Exports enriched holdings to CSV files for Power BI direct import.

Writes two files:
  holdings.csv          — one row per (symbol, broker)
  holdings_summary.csv  — one row per symbol, aggregated across brokers
"""
from __future__ import annotations

import csv
from pathlib import Path

from pipeline import config
from pipeline.loaders.base import BaseLoader
from pipeline.models.holding import Holding
from pipeline.utils.logging import get_logger

log = get_logger(__name__)

_HOLDINGS_FIELDS = [
    "symbol", "isin", "exchange", "broker", "asset_class",
    "quantity", "avg_cost", "invested_value",
    "current_price", "current_value", "unrealized_pnl", "unrealized_pnl_pct", "day_change_pct",
    "sector", "industry", "market_cap", "pe_ratio",
    "fifty_two_week_high", "fifty_two_week_low", "dividend_yield",
    "next_earnings_date", "next_dividend_date", "next_dividend_amount",
    "ai_commentary", "ai_sentiment",
    "last_updated",
]


class CSVExporter(BaseLoader):
    def __init__(self, output_dir: Path | None = None) -> None:
        self._dir = output_dir or config.CSV_OUTPUT_DIR

    def load(self, holdings: list[Holding]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

        holdings_path = self._dir / "holdings.csv"
        self._write_holdings(holdings, holdings_path)

        summary_path = self._dir / "holdings_summary.csv"
        self._write_summary(holdings, summary_path)

    def _write_holdings(self, holdings: list[Holding], path: Path) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_HOLDINGS_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for h in holdings:
                row = h.model_dump()
                row["next_earnings_date"] = str(row["next_earnings_date"]) if row["next_earnings_date"] else ""
                row["next_dividend_date"] = str(row["next_dividend_date"]) if row["next_dividend_date"] else ""
                row["last_updated"] = str(row["last_updated"])
                writer.writerow(row)
        log.info("CSV: wrote holdings.csv (%d rows)", len(holdings))

    def _write_summary(self, holdings: list[Holding], path: Path) -> None:
        summary: dict[str, dict] = {}
        for h in holdings:
            key = h.symbol
            if key not in summary:
                summary[key] = {
                    "symbol": h.symbol,
                    "isin": h.isin,
                    "asset_class": h.asset_class,
                    "sector": h.sector,
                    "industry": h.industry,
                    "total_quantity": 0.0,
                    "total_invested": 0.0,
                    "total_current_value": 0.0,
                    "brokers": [],
                }
            s = summary[key]
            s["total_quantity"] += h.quantity
            s["total_invested"] += h.invested_value
            s["total_current_value"] += h.current_value or 0.0
            s["brokers"].append(h.broker)

        rows = []
        for s in summary.values():
            invested = s["total_invested"]
            current = s["total_current_value"]
            pnl = current - invested
            rows.append({
                "symbol": s["symbol"],
                "isin": s["isin"],
                "asset_class": s["asset_class"],
                "sector": s["sector"],
                "industry": s["industry"],
                "total_quantity": s["total_quantity"],
                "total_invested": invested,
                "total_current_value": current,
                "total_unrealized_pnl": pnl,
                "total_unrealized_pnl_pct": (pnl / invested * 100) if invested else 0.0,
                "brokers": ",".join(set(s["brokers"])),
            })

        summary_fields = [
            "symbol", "isin", "asset_class", "sector", "industry",
            "total_quantity", "total_invested", "total_current_value",
            "total_unrealized_pnl", "total_unrealized_pnl_pct", "brokers",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=summary_fields)
            writer.writeheader()
            writer.writerows(rows)
        log.info("CSV: wrote holdings_summary.csv (%d symbols)", len(rows))
