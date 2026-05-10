"""
Main pipeline orchestrator.

Usage:
    python -m pipeline.run                  # full pipeline
    python -m pipeline.run --skip-ai        # skip Claude commentary (saves API cost)
    python -m pipeline.run --dry-run        # extract + enrich, print summary, no DB/CSV write
    python -m pipeline.run --steps extract  # only run extraction (debug)
"""
from __future__ import annotations

import argparse
import sys

from pipeline import config
from pipeline.enrichers.calendar import CalendarEnricher
from pipeline.enrichers.market_data import MarketDataEnricher
from pipeline.extractors.groww import GrowwExtractor
from pipeline.extractors.holdings_merger import merge
from pipeline.extractors.zerodha import ZerodhaExtractor
from pipeline.loaders.csv_exporter import CSVExporter
from pipeline.loaders.sqlite_loader import SQLiteLoader
from pipeline.models.holding import Holding
from pipeline.utils.logging import get_logger

log = get_logger("pipeline.run")


def build_extractors():
    return [
        ZerodhaExtractor(),
        GrowwExtractor(),
        # GoldExtractor(),     ← add when ready
        # CryptoExtractor(),   ← add when ready
    ]


def build_enrichers(skip_ai: bool):
    enrichers = [
        MarketDataEnricher(),
        CalendarEnricher(),
    ]
    if not skip_ai:
        try:
            from pipeline.enrichers.ai_commentary import AICommentaryEnricher
            enrichers.append(AICommentaryEnricher())
        except ValueError as e:
            log.warning("%s — AI commentary will be skipped", e)
    return enrichers


def build_loaders(dry_run: bool):
    if dry_run:
        return []
    return [
        SQLiteLoader(),
        CSVExporter(),
    ]


def run(skip_ai: bool = False, dry_run: bool = False) -> list[Holding]:
    log.info("=== Asset Dashboard ETL Pipeline starting ===")

    # Extract
    extractors = build_extractors()
    holdings = merge(extractors)
    if not holdings:
        log.error("No holdings extracted — check CSV paths in .env")
        sys.exit(1)

    # Enrich
    for enricher in build_enrichers(skip_ai):
        holdings = enricher.enrich(holdings)

    # Load
    for loader in build_loaders(dry_run):
        loader.load(holdings)

    if dry_run:
        _print_summary(holdings)

    log.info("=== Pipeline complete: %d holdings processed ===", len(holdings))
    return holdings


def _print_summary(holdings: list[Holding]) -> None:
    print(f"\n{'Symbol':<15} {'Broker':<10} {'Qty':>6} {'Invested':>12} {'Value':>12} {'P&L%':>8} {'Sentiment':<10}")
    print("-" * 75)
    for h in holdings:
        pnl_pct = f"{h.unrealized_pnl_pct:.1f}%" if h.unrealized_pnl_pct is not None else "N/A"
        value = f"₹{h.current_value:,.0f}" if h.current_value else "N/A"
        invested = f"₹{h.invested_value:,.0f}"
        print(f"{h.symbol:<15} {h.broker:<10} {h.quantity:>6.0f} {invested:>12} {value:>12} {pnl_pct:>8} {h.ai_sentiment or '':10}")


def main():
    parser = argparse.ArgumentParser(description="Asset Dashboard ETL Pipeline")
    parser.add_argument("--skip-ai", action="store_true", help="Skip Claude AI commentary step")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing to DB/CSV")
    args = parser.parse_args()

    run(skip_ai=args.skip_ai, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
