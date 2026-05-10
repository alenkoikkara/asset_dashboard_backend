"""
Merges holdings from all registered extractors into one unified list.

Primary key is (symbol, broker) — the same stock held across brokers is kept
as separate rows so each broker's cost basis and P&L are preserved independently.
Power BI can group/sum by symbol for a consolidated view.
"""
from __future__ import annotations

from pipeline.extractors.base import BaseExtractor
from pipeline.models.holding import Holding
from pipeline.utils.logging import get_logger

log = get_logger(__name__)


def merge(extractors: list[BaseExtractor]) -> list[Holding]:
    all_holdings: list[Holding] = []

    for extractor in extractors:
        if not extractor.is_available():
            log.info("Skipping %s (source not available)", extractor.broker)
            continue
        holdings = extractor.extract()
        all_holdings.extend(holdings)

    log.info("Merged total: %d holdings across %d sources", len(all_holdings), len(extractors))
    return all_holdings
