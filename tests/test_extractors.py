"""Unit tests for API-based extractors — mocks network/SDK calls, no credentials needed."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pipeline.extractors.zerodha import ZerodhaExtractor
from pipeline.extractors.groww import GrowwExtractor
from pipeline.extractors.holdings_merger import merge


# ── Zerodha ──────────────────────────────────────────────────────────────────

KITE_HOLDINGS = [
    {
        "tradingsymbol": "HDFCBANK",
        "isin": "INE040A01034",
        "exchange": "NSE",
        "quantity": 10,
        "t1_quantity": 0,
        "average_price": 1600.0,
        "last_price": 1750.0,
        "pnl": 1500.0,
        "day_change_percentage": 0.11,
    },
    {
        "tradingsymbol": "POWERGRID",
        "isin": "INE752E01010",
        "exchange": "NSE",
        "quantity": 50,
        "t1_quantity": 0,
        "average_price": 230.0,
        "last_price": 245.0,
        "pnl": 750.0,
        "day_change_percentage": -0.5,
    },
]


@patch("pipeline.extractors.zerodha.config")
@patch("pipeline.extractors.zerodha.KiteConnect")
def test_zerodha_extractor(mock_kite_cls, mock_cfg):
    mock_cfg.KITE_API_KEY = "key"
    mock_cfg.KITE_ACCESS_TOKEN = "token"

    mock_kite = MagicMock()
    mock_kite.holdings.return_value = KITE_HOLDINGS
    mock_kite_cls.return_value = mock_kite

    extractor = ZerodhaExtractor()
    holdings = extractor.extract()

    assert len(holdings) == 2
    hdfc = next(h for h in holdings if h.symbol == "HDFCBANK")
    assert hdfc.quantity == 10
    assert hdfc.avg_cost == 1600.0
    assert hdfc.invested_value == 16000.0
    assert hdfc.current_price == 1750.0
    assert hdfc.unrealized_pnl == pytest.approx(1500.0)
    assert hdfc.broker == "zerodha"
    assert hdfc.day_change_pct == pytest.approx(0.11)


@patch("pipeline.extractors.zerodha.config")
def test_zerodha_skips_when_no_token(mock_cfg):
    mock_cfg.KITE_API_KEY = ""
    mock_cfg.KITE_ACCESS_TOKEN = ""
    extractor = ZerodhaExtractor()
    assert not extractor.is_available()
    assert extractor.extract() == []


# ── Groww ─────────────────────────────────────────────────────────────────────

GROWW_RESPONSE = {
    "status": "SUCCESS",
    "payload": [
        {
            "trading_symbol": "BAJAJHFL",
            "isin": "INE274G01010",
            "quantity": 20,
            "t1_quantity": 0,
            "average_price": 75.0,
        },
        {
            "trading_symbol": "FEDERALBNK",
            "isin": "INE171A01029",
            "quantity": 100,
            "t1_quantity": 0,
            "average_price": 150.0,
        },
    ],
}


@patch("pipeline.extractors.groww.config")
@patch("pipeline.extractors.groww.requests.get")
def test_groww_extractor(mock_get, mock_cfg):
    mock_cfg.GROWW_ACCESS_TOKEN = "token"

    mock_resp = MagicMock()
    mock_resp.json.return_value = GROWW_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    extractor = GrowwExtractor()
    holdings = extractor.extract()

    assert len(holdings) == 2
    bajaj = next(h for h in holdings if h.symbol == "BAJAJHFL")
    assert bajaj.quantity == 20
    assert bajaj.avg_cost == 75.0
    assert bajaj.invested_value == pytest.approx(1500.0)
    assert bajaj.current_price is None  # Groww API doesn't return live price
    assert bajaj.broker == "groww"


@patch("pipeline.extractors.groww.config")
def test_groww_skips_when_no_token(mock_cfg):
    mock_cfg.GROWW_ACCESS_TOKEN = ""
    extractor = GrowwExtractor()
    assert not extractor.is_available()
    assert extractor.extract() == []


@patch("pipeline.extractors.groww.config")
@patch("pipeline.extractors.groww.requests.get")
def test_groww_handles_api_failure(mock_get, mock_cfg):
    mock_cfg.GROWW_ACCESS_TOKEN = "token"

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "FAILURE",
        "error": {"code": "GA401", "message": "Invalid token"},
    }
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    extractor = GrowwExtractor()
    assert extractor.extract() == []


# ── Merger ────────────────────────────────────────────────────────────────────

@patch("pipeline.extractors.zerodha.config")
@patch("pipeline.extractors.zerodha.KiteConnect")
@patch("pipeline.extractors.groww.config")
@patch("pipeline.extractors.groww.requests.get")
def test_merger_combines_sources(mock_groww_get, mock_groww_cfg, mock_kite_cls, mock_kite_cfg):
    mock_kite_cfg.KITE_API_KEY = "key"
    mock_kite_cfg.KITE_ACCESS_TOKEN = "token"
    mock_kite = MagicMock()
    mock_kite.holdings.return_value = KITE_HOLDINGS
    mock_kite_cls.return_value = mock_kite

    mock_groww_cfg.GROWW_ACCESS_TOKEN = "token"
    mock_resp = MagicMock()
    mock_resp.json.return_value = GROWW_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_groww_get.return_value = mock_resp

    holdings = merge([ZerodhaExtractor(), GrowwExtractor()])
    assert len(holdings) == 4
    assert {h.broker for h in holdings} == {"zerodha", "groww"}
