"""
Step 5a: Loads enriched holdings into SQLite.

Table: holdings — full replace on each pipeline run (snapshot model).
Power BI connects to this DB via ODBC or direct file path.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from pipeline import config
from pipeline.loaders.base import BaseLoader
from pipeline.models.holding import Holding
from pipeline.utils.logging import get_logger

log = get_logger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS holdings (
    symbol              TEXT,
    isin                TEXT,
    exchange            TEXT,
    broker              TEXT,
    asset_class         TEXT,
    quantity            REAL,
    avg_cost            REAL,
    invested_value      REAL,
    current_price       REAL,
    current_value       REAL,
    unrealized_pnl      REAL,
    unrealized_pnl_pct  REAL,
    day_change_pct      REAL,
    sector              TEXT,
    industry            TEXT,
    market_cap          REAL,
    pe_ratio            REAL,
    fifty_two_week_high REAL,
    fifty_two_week_low  REAL,
    dividend_yield      REAL,
    next_earnings_date  TEXT,
    next_dividend_date  TEXT,
    next_dividend_amount REAL,
    ai_commentary       TEXT,
    ai_sentiment        TEXT,
    news_sentiment_score REAL,
    latest_news_headline TEXT,
    last_updated        TEXT,
    PRIMARY KEY (symbol, broker)
)
"""

_UPSERT = """
INSERT OR REPLACE INTO holdings VALUES (
    :symbol, :isin, :exchange, :broker, :asset_class,
    :quantity, :avg_cost, :invested_value,
    :current_price, :current_value, :unrealized_pnl, :unrealized_pnl_pct, :day_change_pct,
    :sector, :industry, :market_cap, :pe_ratio,
    :fifty_two_week_high, :fifty_two_week_low, :dividend_yield,
    :next_earnings_date, :next_dividend_date, :next_dividend_amount,
    :ai_commentary, :ai_sentiment,
    :news_sentiment_score, :latest_news_headline,
    :last_updated
)
"""


class SQLiteLoader(BaseLoader):
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or config.DB_PATH

    def load(self, holdings: list[Holding]) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        rows = []
        for h in holdings:
            d = h.model_dump()
            d["next_earnings_date"] = str(d["next_earnings_date"]) if d["next_earnings_date"] else None
            d["next_dividend_date"] = str(d["next_dividend_date"]) if d["next_dividend_date"] else None
            d["last_updated"] = str(d["last_updated"])
            rows.append(d)

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE)
            conn.executemany(_UPSERT, rows)
            conn.commit()

        log.info("SQLite: wrote %d rows to %s", len(rows), self._db_path)
