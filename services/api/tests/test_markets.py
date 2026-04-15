from datetime import UTC, datetime, timedelta

from app.market_data.schemas import MarketCandle
from app.market_data.service import build_quality_report, normalize_candles
from conftest import client


def test_assets_and_quote() -> None:
    assets_response = client.get("/markets/assets")
    assert assets_response.status_code == 200
    assert len(assets_response.json()) >= 4

    quote_response = client.get("/markets/quote", params={"symbol": "BTCUSD", "asset_class": "crypto"})
    assert quote_response.status_code == 200
    quote = quote_response.json()
    assert quote["symbol"] == "BTCUSD"
    assert quote["asset_class"] == "crypto"


def test_candles_endpoint_and_quality_endpoint() -> None:
    candles_response = client.get(
        "/markets/candles",
        params={"symbol": "ETHUSD", "asset_class": "crypto", "timeframe": "1h", "limit": 20},
    )
    assert candles_response.status_code == 200
    candles = candles_response.json()
    assert len(candles) == 20

    quality_response = client.get(
        "/markets/candles/quality",
        params={"symbol": "ETHUSD", "asset_class": "crypto", "timeframe": "1h", "limit": 20},
    )
    assert quality_response.status_code == 200
    quality = quality_response.json()
    assert quality["expected_interval_seconds"] == 3600


def test_normalize_candles_dedupes_and_orders() -> None:
    base_ts = datetime.now(UTC).replace(second=0, microsecond=0)
    candles = [
        MarketCandle(
            symbol="BTCUSD",
            asset_class="crypto",
            timeframe="1h",
            timestamp=base_ts + timedelta(hours=1),
            open=1,
            high=2,
            low=1,
            close=2,
            volume=100,
            provider="mock",
        ),
        MarketCandle(
            symbol="BTCUSD",
            asset_class="crypto",
            timeframe="1h",
            timestamp=base_ts,
            open=1,
            high=2,
            low=1,
            close=2,
            volume=100,
            provider="mock",
        ),
        MarketCandle(
            symbol="BTCUSD",
            asset_class="crypto",
            timeframe="1h",
            timestamp=base_ts,
            open=1.1,
            high=2.1,
            low=1.1,
            close=2.1,
            volume=110,
            provider="mock",
        ),
    ]

    normalized = normalize_candles(candles)
    assert len(normalized) == 2
    assert normalized[0].timestamp == base_ts


def test_quality_report_detects_gap() -> None:
    base_ts = datetime.now(UTC).replace(second=0, microsecond=0)
    candles = [
        MarketCandle(
            symbol="BTCUSD",
            asset_class="crypto",
            timeframe="1h",
            timestamp=base_ts,
            open=1,
            high=2,
            low=1,
            close=2,
            volume=100,
            provider="mock",
        ),
        MarketCandle(
            symbol="BTCUSD",
            asset_class="crypto",
            timeframe="1h",
            timestamp=base_ts + timedelta(hours=3),
            open=1,
            high=2,
            low=1,
            close=2,
            volume=100,
            provider="mock",
        ),
    ]

    report = build_quality_report(candles, timeframe="1h")
    assert report.missing_intervals == 2
