"""
Step 4: Generates per-holding AI commentary using the Anthropic API.

Uses prompt caching: the system prompt (market context + instructions) is cached
across all per-holding calls so only the holding-specific user message is billed
at full token price on subsequent calls.
"""
from __future__ import annotations

import anthropic

from pipeline import config
from pipeline.enrichers.base import BaseEnricher
from pipeline.models.holding import Holding
from pipeline.utils.logging import get_logger

log = get_logger(__name__)

_SYSTEM_PROMPT = """You are a concise investment analyst assistant for an Indian retail investor.
For each stock holding provided, write a 2-3 sentence commentary covering:
1. What the company does and its current market position
2. Key risk or tailwind relevant to the current market environment
3. A one-word sentiment: bullish, neutral, or bearish

Respond with JSON in this exact format:
{"commentary": "<2-3 sentences>", "sentiment": "<bullish|neutral|bearish>"}

Be direct and specific. Avoid generic disclaimers."""


def _build_user_message(h: Holding) -> str:
    parts = [
        f"Stock: {h.symbol}",
        f"Sector: {h.sector or 'Unknown'}",
        f"Industry: {h.industry or 'Unknown'}",
        f"Unrealized P&L: {h.unrealized_pnl_pct:.1f}%" if h.unrealized_pnl_pct else "P&L: N/A",
        f"52W High: {h.fifty_two_week_high}" if h.fifty_two_week_high else "",
        f"52W Low: {h.fifty_two_week_low}" if h.fifty_two_week_low else "",
        f"P/E Ratio: {h.pe_ratio}" if h.pe_ratio else "",
    ]
    return "\n".join(p for p in parts if p)


class AICommentaryEnricher(BaseEnricher):
    def __init__(self) -> None:
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set — skipping AI commentary")
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def enrich(self, holdings: list[Holding]) -> list[Holding]:
        enriched: list[Holding] = []

        for h in holdings:
            try:
                response = self._client.messages.create(
                    model=config.ANTHROPIC_MODEL,
                    max_tokens=300,
                    system=[
                        {
                            "type": "text",
                            "text": _SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},  # cache the system prompt
                        }
                    ],
                    messages=[{"role": "user", "content": _build_user_message(h)}],
                )
                raw = response.content[0].text.strip()
                import json
                parsed = json.loads(raw)
                sentiment = parsed.get("sentiment", "neutral")
                if sentiment not in ("bullish", "neutral", "bearish"):
                    sentiment = "neutral"
                enriched.append(h.model_copy(update={
                    "ai_commentary": parsed.get("commentary"),
                    "ai_sentiment": sentiment,
                }))
                log.info("AI commentary done: %s (%s)", h.symbol, sentiment)
            except Exception as exc:
                log.warning("AI commentary failed for %s: %s", h.symbol, exc)
                enriched.append(h)

        return enriched
