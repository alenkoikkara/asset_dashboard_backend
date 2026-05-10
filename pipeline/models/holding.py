from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


AssetClass = Literal["equity", "gold", "crypto", "mf", "etf"]
BrokerName = Literal["zerodha", "groww", "manual"]


class Holding(BaseModel):
    # Identity
    symbol: str
    isin: str | None = None
    exchange: str = "NSE"
    broker: BrokerName
    asset_class: AssetClass = "equity"

    # Position
    quantity: float
    avg_cost: float
    invested_value: float

    # Market (filled by market_data enricher)
    current_price: float | None = None
    current_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    day_change_pct: float | None = None

    # Fundamentals (filled by market_data enricher)
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    dividend_yield: float | None = None

    # Calendar (filled by calendar enricher)
    next_earnings_date: date | None = None
    next_dividend_date: date | None = None
    next_dividend_amount: float | None = None

    # AI (filled by ai_commentary enricher)
    ai_commentary: str | None = None
    ai_sentiment: Literal["bullish", "neutral", "bearish"] | None = None

    # News / sentiment (future step)
    news_sentiment_score: float | None = None
    latest_news_headline: str | None = None

    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
