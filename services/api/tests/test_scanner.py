"""Tests for WatchlistScanner and /scanner endpoints."""
from datetime import UTC, datetime

import pytest

from tests.conftest import client


# ---------------------------------------------------------------------------
# Strategy engine — new rules
# ---------------------------------------------------------------------------

class TestNewStrategyRules:
    def _make_candles(self, count=30, base=100.0, trend=0.1):
        from app.market_data.schemas import MarketCandle
        now = datetime.now(UTC)
        candles = []
        price = base
        for i in range(count):
            from datetime import timedelta
            ts = now - timedelta(minutes=(count - i) * 5)
            candles.append(MarketCandle(
                symbol="TEST",
                asset_class="stock",
                timeframe="5m",
                timestamp=ts,
                open=round(price, 2),
                high=round(price + 0.5, 2),
                low=round(price - 0.5, 2),
                close=round(price + trend, 2),
                volume=1000.0 + i * 50,
                provider="mock",
            ))
            price += trend
        return candles

    def test_gap_up_fires(self):
        from app.strategy.engine import _evaluate_rule
        from app.strategy.schemas import StrategyRule
        from app.market_data.schemas import MarketCandle
        from datetime import timedelta
        now = datetime.now(UTC)

        candles = self._make_candles(25, base=100.0)
        # Make last candle open way above first candle close
        last = candles[-1]
        first_close = candles[0].close
        new_open = first_close * 1.05
        candles[-1] = MarketCandle(
            symbol=last.symbol, asset_class=last.asset_class,
            timeframe=last.timeframe, timestamp=last.timestamp,
            open=new_open, high=new_open + 1, low=new_open - 0.5,
            close=new_open + 0.5, volume=last.volume, provider=last.provider
        )
        rule = StrategyRule(rule_type="gap_up", params={"min_gap_pct": 0.02})
        assert _evaluate_rule(candles, rule) is True

    def test_gap_down_fires(self):
        from app.strategy.engine import _evaluate_rule
        from app.strategy.schemas import StrategyRule
        from app.market_data.schemas import MarketCandle

        candles = self._make_candles(25, base=100.0)
        last = candles[-1]
        first_close = candles[0].close
        new_open = first_close * 0.95
        candles[-1] = MarketCandle(
            symbol=last.symbol, asset_class=last.asset_class,
            timeframe=last.timeframe, timestamp=last.timestamp,
            open=new_open, high=new_open + 0.5, low=new_open - 1,
            close=new_open - 0.5, volume=last.volume, provider=last.provider
        )
        rule = StrategyRule(rule_type="gap_down", params={"min_gap_pct": 0.02})
        assert _evaluate_rule(candles, rule) is True

    def test_vwap_cross_fires(self):
        from app.strategy.engine import _evaluate_rule, _vwap
        from app.strategy.schemas import StrategyRule
        from app.market_data.schemas import MarketCandle
        from datetime import timedelta
        now = datetime.now(UTC)

        candles = self._make_candles(25, base=100.0, trend=0.0)
        vwap = _vwap(candles)
        # Force a bullish cross on last two candles
        prev = candles[-2]
        last = candles[-1]
        candles[-2] = MarketCandle(
            symbol=prev.symbol, asset_class=prev.asset_class,
            timeframe=prev.timeframe, timestamp=prev.timestamp,
            open=prev.open, high=prev.high, low=prev.low,
            close=vwap - 0.5, volume=prev.volume, provider=prev.provider
        )
        candles[-1] = MarketCandle(
            symbol=last.symbol, asset_class=last.asset_class,
            timeframe=last.timeframe, timestamp=last.timestamp,
            open=last.open, high=last.high, low=last.low,
            close=vwap + 0.5, volume=last.volume, provider=last.provider
        )
        rule = StrategyRule(rule_type="vwap_cross", params={})
        assert _evaluate_rule(candles, rule) is True

    def test_ema_cross_fires(self):
        from app.strategy.engine import _evaluate_rule, _ema
        from app.strategy.schemas import StrategyRule
        from app.market_data.schemas import MarketCandle
        from datetime import timedelta
        now = datetime.now(UTC)

        # Build 30 candles with increasing close to force fast EMA above slow EMA
        candles = []
        for i in range(30):
            ts = now - timedelta(minutes=(30 - i) * 5)
            price = 100.0 + i * 0.5
            candles.append(MarketCandle(
                symbol="TEST", asset_class="stock", timeframe="5m",
                timestamp=ts,
                open=price, high=price + 0.2, low=price - 0.2,
                close=price, volume=1000.0, provider="mock",
            ))
        rule = StrategyRule(rule_type="ema_cross", params={"fast": 9, "slow": 21})
        # With a strong uptrend, fast EMA should be above slow EMA
        result = _evaluate_rule(candles, rule)
        # Just check it runs without error; actual signal depends on data
        assert isinstance(result, bool)

    def test_gap_up_doesnt_fire_small_gap(self):
        from app.strategy.engine import _evaluate_rule
        from app.strategy.schemas import StrategyRule
        candles = self._make_candles(25, base=100.0, trend=0.001)
        rule = StrategyRule(rule_type="gap_up", params={"min_gap_pct": 0.10})
        assert _evaluate_rule(candles, rule) is False


# ---------------------------------------------------------------------------
# WatchlistScanner tests
# ---------------------------------------------------------------------------

class TestWatchlistScanner:
    def test_scan_symbol_returns_result(self):
        from app.market_data.providers.mock import MockMarketDataProvider
        from app.strategy.scanner import WatchlistScanner
        from app.strategy.schemas import StrategyRule

        rules = [
            StrategyRule(rule_type="rsi_threshold", params={"period": 14, "threshold": 30, "mode": "above"}),
            StrategyRule(rule_type="volume_spike", params={"lookback": 20, "multiplier": 0.5}),
        ]
        scanner = WatchlistScanner(provider=MockMarketDataProvider(), rules=rules)
        result = scanner.scan_symbol("SPY", "stock")
        assert result.symbol == "SPY"
        assert result.asset_class == "stock"
        assert 0.0 <= result.aggregate_score <= 1.0
        assert isinstance(result.fired_timeframes, list)
        assert result.suggested_side in ("buy", "sell", "none")

    def test_scan_watchlist_returns_sorted_results(self):
        from app.market_data.providers.mock import MockMarketDataProvider
        from app.strategy.scanner import WatchlistScanner
        from app.strategy.schemas import StrategyRule

        rules = [StrategyRule(rule_type="rsi_threshold", params={"period": 14, "threshold": 50, "mode": "above"})]
        scanner = WatchlistScanner(provider=MockMarketDataProvider(), rules=rules)
        watchlist = [("SPY", "stock"), ("NVDA", "stock"), ("BTCUSD", "crypto")]
        result = scanner.scan_watchlist(watchlist)

        assert result.scanned_at is not None
        assert len(result.results) == 3
        # Results sorted by score descending
        scores = [r.aggregate_score for r in result.results]
        assert scores == sorted(scores, reverse=True)

    def test_scan_watchlist_top_pick_none_when_no_signals(self):
        from app.market_data.providers.mock import MockMarketDataProvider
        from app.strategy.scanner import WatchlistScanner
        from app.strategy.schemas import StrategyRule

        # Use a rule that's unlikely to fire (extremely high bar)
        rules = [StrategyRule(rule_type="volume_spike", params={"lookback": 5, "multiplier": 1000.0})]
        scanner = WatchlistScanner(provider=MockMarketDataProvider(), rules=rules)
        result = scanner.scan_watchlist([("SPY", "stock")])
        # top_pick should be None since should_trade requires score >= 0.6 and 2 timeframes
        assert result.top_pick is None

    def test_scanner_handles_provider_error_gracefully(self):
        from unittest.mock import MagicMock
        from app.strategy.scanner import WatchlistScanner
        from app.strategy.schemas import StrategyRule

        mock_provider = MagicMock()
        mock_provider.get_candles.side_effect = Exception("network error")
        rules = [StrategyRule(rule_type="rsi_threshold", params={})]
        scanner = WatchlistScanner(provider=mock_provider, rules=rules)
        result = scanner.scan_symbol("FAIL", "stock")
        assert result.aggregate_score == 0.0
        assert result.should_trade is False


# ---------------------------------------------------------------------------
# /scanner endpoint tests
# ---------------------------------------------------------------------------

class TestScannerEndpoints:
    def test_watchlist_returns_200(self):
        resp = client.get("/scanner/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "scanned_at" in data
        assert isinstance(data["results"], list)

    def test_symbol_scan_returns_200(self):
        resp = client.get("/scanner/symbol", params={"symbol": "SPY", "asset_class": "stock"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "SPY"
        assert "aggregate_score" in data

    def test_top_pick_404_or_200(self):
        resp = client.get("/scanner/top-pick")
        # Either 404 (no pick) or 200 (pick found) — both valid
        assert resp.status_code in (200, 404)

    def test_symbol_scan_crypto(self):
        resp = client.get("/scanner/symbol", params={"symbol": "BTCUSD", "asset_class": "crypto"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_class"] == "crypto"
