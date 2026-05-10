from pipeline.utils.ticker_map import to_yf_ticker


def test_nse_equity():
    assert to_yf_ticker("HDFCBANK") == "HDFCBANK.NS"
    assert to_yf_ticker("BAJAJHFL") == "BAJAJHFL.NS"
    assert to_yf_ticker("POWERGRID") == "POWERGRID.NS"


def test_crypto():
    assert to_yf_ticker("BTC", asset_class="crypto") == "BTC-USD"
    assert to_yf_ticker("ETH", asset_class="crypto") == "ETH-USD"


def test_gold():
    assert to_yf_ticker("GOLD", asset_class="gold") == "GC=F"


def test_override():
    assert to_yf_ticker("SGBBSE") == "GOLDBEES.NS"
