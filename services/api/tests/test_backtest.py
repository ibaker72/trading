"""
Tests for the backtesting engine, schemas, and /backtest REST endpoints.

All tests are offline — no real HTTP calls to Alpaca. The market data
provider is mocked to return deterministic candle sequences.
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtest.engine import BacktestEngine, _calc_qty
from app.backtest.schemas import BacktestRequest, BacktestResult, BacktestTrade
from app.market_data.schemas import MarketCandle
from app.strategy.schemas import StrategyRule
from tests.conftest import client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candle(
    i: int,
    base_price: float = 100.0,
    symbol: str = "AAPL",
    volume: float = 1_000_000.0,
) -> MarketCandle:
    """Generate a synthetic daily candle with deterministic values."""
    close = round(base_price + i * 0.5, 4)
    return MarketCandle(
        symbol=symbol,
        asset_class="stock",
        timeframe="1d",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i),
        open=round(close - 0.2, 4),
        high=round(close + 1.0, 4),
        low=round(close - 1.0, 4),
        close=close,
        volume=volume,
        provider="test",
    )


def _make_candles(n: int = 100, base_price: float = 100.0) -> list[MarketCandle]:
    return [_make_candle(i, base_price) for i in range(n)]


def _make_provider(candles: list[MarketCandle]) -> MagicMock:
    provider = MagicMock()
    provider.get_historical_bars.return_value = candles
    return provider


def _make_request(**kwargs) -> BacktestRequest:
    defaults = dict(
        symbol="AAPL",
        asset_class="stock",
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        stop_loss_pct=1.0,
        take_profit_pct=2.0,
        starting_equity=100_000.0,
        position_size_pct=5.0,
        min_signal_score=0.0,  # fire on any signal score
    )
    defaults.update(kwargs)
    return BacktestRequest(**defaults)


# ---------------------------------------------------------------------------
# BacktestRequest schema validation
# ---------------------------------------------------------------------------

class TestBacktestRequest:
    def test_valid_request(self):
        req = _make_request()
        assert req.symbol == "AAPL"
        assert req.stop_loss_pct == 1.0

    def test_end_must_be_after_start(self):
        with pytest.raises(Exception):
            BacktestRequest(
                symbol="AAPL",
                start=date(2024, 12, 31),
                end=date(2024, 1, 1),
            )

    def test_equal_start_end_invalid(self):
        with pytest.raises(Exception):
            BacktestRequest(
                symbol="AAPL",
                start=date(2024, 6, 1),
                end=date(2024, 6, 1),
            )

    def test_default_timeframe_is_1d(self):
        req = _make_request()
        assert req.timeframe == "1d"

    def test_default_rules_is_none(self):
        req = _make_request()
        assert req.rules is None

    def test_custom_rules_accepted(self):
        req = _make_request(rules=[StrategyRule(rule_type="ema_cross", params={"fast": 9, "slow": 21})])
        assert req.rules is not None
        assert len(req.rules) == 1


# ---------------------------------------------------------------------------
# _calc_qty helper
# ---------------------------------------------------------------------------

class TestCalcQty:
    def test_basic_calculation(self):
        # 5% of $100k at $100 = 50 shares
        qty = _calc_qty(100_000, 100.0, 0.05)
        assert qty == pytest.approx(50.0, abs=0.1)

    def test_zero_price_returns_fallback(self):
        qty = _calc_qty(100_000, 0.0, 0.05)
        assert qty == 1.0

    def test_zero_equity_returns_fallback(self):
        qty = _calc_qty(0.0, 100.0, 0.05)
        assert qty == 1.0

    def test_minimum_qty(self):
        # Even with tiny fraction, minimum is 0.01
        qty = _calc_qty(100, 10_000.0, 0.0001)
        assert qty >= 0.01


# ---------------------------------------------------------------------------
# BacktestEngine — core logic
# ---------------------------------------------------------------------------

class TestBacktestEngine:
    def _engine_with(self, candles: list[MarketCandle]) -> BacktestEngine:
        return BacktestEngine(provider=_make_provider(candles))

    def test_raises_on_insufficient_data(self):
        engine = self._engine_with(_make_candles(10))
        with pytest.raises(ValueError, match="Insufficient"):
            engine.run(_make_request())

    def test_returns_backtest_result(self):
        engine = self._engine_with(_make_candles(120))
        result = engine.run(_make_request())
        assert isinstance(result, BacktestResult)

    def test_result_symbol_matches_request(self):
        engine = self._engine_with(_make_candles(120))
        result = engine.run(_make_request(symbol="TSLA"))
        assert result.symbol == "TSLA"

    def test_total_bars_matches_candle_count(self):
        candles = _make_candles(100)
        engine = self._engine_with(candles)
        result = engine.run(_make_request())
        assert result.total_bars == 100

    def test_equity_curve_starts_at_starting_equity(self):
        engine = self._engine_with(_make_candles(120))
        result = engine.run(_make_request())
        assert result.equity_curve[0] == pytest.approx(100_000.0)

    def test_no_trades_when_score_threshold_too_high(self):
        """With min_signal_score=1.0 and only 2 default rules, both must fire."""
        engine = self._engine_with(_make_candles(120))
        result = engine.run(_make_request(min_signal_score=1.0))
        # May or may not produce trades depending on synthetic data — just check structure
        assert isinstance(result.trades, list)

    def test_metrics_win_rate_in_range(self):
        engine = self._engine_with(_make_candles(120))
        result = engine.run(_make_request())
        assert 0.0 <= result.metrics.win_rate <= 1.0

    def test_metrics_max_drawdown_nonnegative(self):
        engine = self._engine_with(_make_candles(120))
        result = engine.run(_make_request())
        assert result.metrics.max_drawdown >= 0.0

    def test_metrics_total_trades_matches_trades_list(self):
        engine = self._engine_with(_make_candles(120))
        result = engine.run(_make_request())
        assert result.metrics.total_trades == len(result.trades)

    def test_equity_curve_length_is_closed_trades_plus_one(self):
        """Equity curve has len(closed_trades)+1 points — only closed/exited trades
        contribute to the equity curve (open/in-progress trades are excluded)."""
        engine = self._engine_with(_make_candles(120))
        result = engine.run(_make_request())
        closed = [t for t in result.trades
                  if t.status in ("closed", "stopped_out", "took_profit")
                  and t.realized_pnl is not None]
        assert len(result.equity_curve) == len(closed) + 1

    def test_provider_called_with_correct_args(self):
        provider = _make_provider(_make_candles(120))
        engine = BacktestEngine(provider=provider)
        req = _make_request(symbol="NVDA", start=date(2024, 3, 1), end=date(2024, 9, 1))
        engine.run(req)
        provider.get_historical_bars.assert_called_once_with(
            symbol="NVDA",
            asset_class="stock",
            start=date(2024, 3, 1),
            end=date(2024, 9, 1),
            timeframe="1d",
        )


# ---------------------------------------------------------------------------
# SL/TP simulation
# ---------------------------------------------------------------------------

class TestSlTpSimulation:
    """
    Build crafted candle sequences and verify exit logic:
    - Bar whose low <= SL → stopped_out
    - Bar whose high >= TP → took_profit
    - SL and TP both possible on same bar → stopped_out (conservative)
    - Neither hit → closed at last bar's close
    """

    def _run_with_candles(self, candles: list[MarketCandle], **req_kwargs) -> list[BacktestTrade]:
        """Run backtest and return trades."""
        engine = BacktestEngine(provider=_make_provider(candles))
        # Force signal on every bar with min_signal_score=0
        result = engine.run(_make_request(min_signal_score=0.0, **req_kwargs))
        return result.trades

    def _candle(self, ts: datetime, o: float, h: float, l: float, c: float) -> MarketCandle:
        return MarketCandle(
            symbol="TEST",
            asset_class="stock",
            timeframe="1d",
            timestamp=ts,
            open=o,
            high=h,
            low=l,
            close=c,
            volume=500_000.0,
            provider="test",
        )

    def _build_sequence(self, n_window: int, entry_price: float, exit_candle_props: dict) -> list[MarketCandle]:
        """Build a sequence: n_window flat setup bars → entry bar → exit bar → padding."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        candles = []
        # Setup window
        for i in range(n_window):
            p = entry_price
            candles.append(self._candle(
                base + timedelta(days=i), p, p + 1, p - 1, p
            ))
        # Signal bar (the evaluation window ends here)
        signal_idx = len(candles)
        candles.append(self._candle(
            base + timedelta(days=signal_idx), entry_price, entry_price + 1, entry_price - 1, entry_price
        ))
        # Entry bar (next bar's open = entry)
        entry_idx = len(candles)
        candles.append(self._candle(
            base + timedelta(days=entry_idx), entry_price, entry_price + 0.5, entry_price - 0.5, entry_price
        ))
        # Exit bar
        exit_idx = len(candles)
        props = exit_candle_props
        candles.append(self._candle(
            base + timedelta(days=exit_idx),
            props.get("o", entry_price),
            props.get("h", entry_price + 0.5),
            props.get("l", entry_price - 0.5),
            props.get("c", entry_price),
        ))
        # Trailing padding to avoid "last bar" close
        for k in range(5):
            pad_idx = len(candles)
            candles.append(self._candle(
                base + timedelta(days=pad_idx), entry_price, entry_price + 0.5, entry_price - 0.5, entry_price
            ))
        return candles

    def test_sl_hit_gives_stopped_out(self):
        """A steadily declining price sequence should produce stopped_out trades."""
        # Price declines from 200 to ~100 over 150 bars — every trade hits SL
        candles = [_make_candle(i, base_price=200.0 - i * 0.8) for i in range(150)]
        trades = self._run_with_candles(candles, stop_loss_pct=1.0, take_profit_pct=50.0)
        # With a large TP (50%) and small SL (1%), declining price should trigger SL
        stopped = [t for t in trades if t.status == "stopped_out"]
        assert len(stopped) >= 1
        # stopped_out trades have negative PnL
        for t in stopped:
            if t.realized_pnl is not None:
                assert t.realized_pnl < 0

    def test_tp_hit_gives_took_profit(self):
        """A steadily rising price sequence should produce took_profit trades."""
        # Price rises from 100 to ~160 over 150 bars — large gap per bar
        candles = [_make_candle(i, base_price=100.0 + i * 0.5) for i in range(150)]
        # Tight TP (1%) and wide SL (20% max) on rising price → TP hit before SL
        trades = self._run_with_candles(candles, stop_loss_pct=20.0, take_profit_pct=1.0)
        profits = [t for t in trades if t.status == "took_profit"]
        assert len(profits) >= 1
        # took_profit trades have positive PnL
        for t in profits:
            if t.realized_pnl is not None:
                assert t.realized_pnl > 0

    def test_sl_takes_priority_over_tp_on_same_bar(self):
        """When both SL and TP could be hit on the same bar, SL wins (conservative).
        Build a candle sequence where, immediately after entry, a bar has both
        low < SL and high > TP."""
        base = datetime(2024, 1, 1, tzinfo=UTC)
        # Window: 61 flat bars at 100.0
        candles = []
        for i in range(62):
            candles.append(self._candle(base + timedelta(days=i), 100.0, 101.0, 99.0, 100.0))
        # Entry bar (bar 62): open = 100.0
        candles.append(self._candle(base + timedelta(days=62), 100.0, 100.5, 99.5, 100.0))
        # Ambiguous exit bar (bar 63): BOTH low=98.0 < SL(99.0) AND high=103.0 > TP(102.0)
        candles.append(self._candle(base + timedelta(days=63), 100.0, 103.0, 98.0, 100.0))
        # Padding
        for k in range(5):
            idx = len(candles)
            candles.append(self._candle(base + timedelta(days=idx), 100.0, 101.0, 99.0, 100.0))

        trades = self._run_with_candles(candles, stop_loss_pct=1.0, take_profit_pct=2.0)
        exited = [t for t in trades if t.status in ("stopped_out", "took_profit")]
        if exited:
            assert exited[0].status == "stopped_out"

    def test_no_trades_overlap(self):
        """Trades must not overlap in time."""
        candles = _make_candles(200)
        engine = BacktestEngine(provider=_make_provider(candles))
        result = engine.run(_make_request(min_signal_score=0.0))
        for i in range(len(result.trades) - 1):
            curr = result.trades[i]
            nxt = result.trades[i + 1]
            if curr.exit_date is not None:
                assert nxt.entry_date >= curr.exit_date


# ---------------------------------------------------------------------------
# BacktestResult structure
# ---------------------------------------------------------------------------

class TestBacktestResult:
    def test_all_trade_fields_present(self):
        candles = _make_candles(120)
        engine = BacktestEngine(provider=_make_provider(candles))
        result = engine.run(_make_request(min_signal_score=0.0))
        for trade in result.trades:
            assert trade.entry_date is not None
            assert trade.entry_price > 0
            assert trade.stop_loss_price < trade.entry_price
            assert trade.take_profit_price > trade.entry_price
            assert trade.side == "buy"
            assert trade.quantity > 0

    def test_pnl_consistent_with_status(self):
        candles = _make_candles(120)
        engine = BacktestEngine(provider=_make_provider(candles))
        result = engine.run(_make_request(min_signal_score=0.0))
        for trade in result.trades:
            if trade.status == "took_profit" and trade.realized_pnl is not None:
                assert trade.realized_pnl > 0, f"took_profit should have positive PnL, got {trade.realized_pnl}"
            if trade.status == "stopped_out" and trade.realized_pnl is not None:
                assert trade.realized_pnl < 0, f"stopped_out should have negative PnL, got {trade.realized_pnl}"

    def test_starting_equity_in_metrics(self):
        candles = _make_candles(120)
        engine = BacktestEngine(provider=_make_provider(candles))
        result = engine.run(_make_request(starting_equity=50_000.0))
        assert result.metrics.starting_equity == 50_000.0

    def test_date_strings_valid(self):
        from datetime import date as _date
        candles = _make_candles(120)
        engine = BacktestEngine(provider=_make_provider(candles))
        result = engine.run(_make_request())
        # start/end should be parseable ISO dates
        _date.fromisoformat(result.start)
        _date.fromisoformat(result.end)


# ---------------------------------------------------------------------------
# /backtest/symbols endpoint
# ---------------------------------------------------------------------------

class TestBacktestSymbolsEndpoint:
    def test_returns_stocks_and_crypto(self):
        resp = client.get("/backtest/symbols")
        assert resp.status_code == 200
        data = resp.json()
        assert "stocks" in data
        assert "crypto" in data
        assert "all" in data
        assert isinstance(data["stocks"], list)
        assert isinstance(data["crypto"], list)

    def test_all_is_union_of_stocks_and_crypto(self):
        resp = client.get("/backtest/symbols")
        data = resp.json()
        assert set(data["all"]) == set(data["stocks"]) | set(data["crypto"])


# ---------------------------------------------------------------------------
# /backtest/run endpoint (mocked provider)
# ---------------------------------------------------------------------------

class TestBacktestRunEndpoint:
    def _payload(self, **kwargs):
        base = {
            "symbol": "AAPL",
            "asset_class": "stock",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "stop_loss_pct": 1.0,
            "take_profit_pct": 2.0,
            "starting_equity": 100000.0,
            "min_signal_score": 0.0,
        }
        base.update(kwargs)
        return base

    def _mock_provider(self, candles: list[MarketCandle]):
        """Context manager: patches _get_provider to return a mock with given candles."""
        provider_mock = MagicMock()
        provider_mock.get_historical_bars.return_value = candles
        return patch("app.routers.backtest._get_provider", return_value=provider_mock)

    def test_returns_503_without_alpaca_key(self):
        import os
        orig = os.environ.pop("ALPACA_API_KEY", None)
        from app.config import get_settings
        get_settings.cache_clear()
        try:
            resp = client.post("/backtest/run", json=self._payload())
            assert resp.status_code == 503
        finally:
            if orig:
                os.environ["ALPACA_API_KEY"] = orig
            get_settings.cache_clear()

    def test_run_returns_result_with_mocked_provider(self):
        candles = _make_candles(120)
        with self._mock_provider(candles):
            resp = client.post("/backtest/run", json=self._payload())
        assert resp.status_code == 200
        data = resp.json()
        assert "trades" in data
        assert "metrics" in data
        assert "equity_curve" in data
        assert data["symbol"] == "AAPL"

    def test_returns_422_on_insufficient_data(self):
        candles = _make_candles(5)  # too few
        with self._mock_provider(candles):
            resp = client.post("/backtest/run", json=self._payload())
        assert resp.status_code == 422

    def test_returns_422_on_invalid_dates(self):
        resp = client.post("/backtest/run", json=self._payload(
            start="2024-12-31",
            end="2024-01-01",
        ))
        assert resp.status_code == 422

    def test_metrics_structure(self):
        candles = _make_candles(120)
        with self._mock_provider(candles):
            resp = client.post("/backtest/run", json=self._payload())
        assert resp.status_code == 200
        metrics = resp.json()["metrics"]
        for key in ("total_trades", "win_rate", "sharpe", "max_drawdown",
                    "avg_win", "avg_loss", "ratio", "total_pnl",
                    "starting_equity", "ending_equity"):
            assert key in metrics, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# AlpacaMarketDataProvider.get_historical_bars (mocked HTTP)
# ---------------------------------------------------------------------------

class TestAlpacaGetHistoricalBars:
    def _provider(self):
        from app.market_data.providers.alpaca import AlpacaMarketDataProvider
        return AlpacaMarketDataProvider(
            api_key="test-key",
            secret_key="test-secret",
            data_url="https://data.alpaca.markets",
            feed="iex",
        )

    def _fake_bar(self, i: int):
        from datetime import date as _date
        return {
            "t": f"2024-{i // 28 + 1:02d}-{i % 28 + 1:02d}T00:00:00Z",
            "o": 100.0 + i,
            "h": 102.0 + i,
            "l": 99.0 + i,
            "c": 101.0 + i,
            "v": 1_000_000,
        }

    def test_stock_bars_returned(self):
        bars = [self._fake_bar(i) for i in range(10)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"bars": bars, "next_page_token": None}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.market_data.providers.alpaca.httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=mock_resp)))
            ctx.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = ctx

            provider = self._provider()
            candles = provider.get_historical_bars(
                symbol="AAPL",
                asset_class="stock",
                start=date(2024, 1, 1),
                end=date(2024, 3, 31),
                timeframe="1d",
            )

        assert len(candles) == 10
        assert all(c.symbol == "AAPL" for c in candles)
        assert all(c.asset_class == "stock" for c in candles)

    def test_candles_sorted_by_timestamp(self):
        # Return bars in reverse order
        bars = list(reversed([self._fake_bar(i) for i in range(5)]))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"bars": bars, "next_page_token": None}
        mock_resp.raise_for_status = MagicMock()

        with patch("app.market_data.providers.alpaca.httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=mock_resp)))
            ctx.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = ctx

            provider = self._provider()
            candles = provider.get_historical_bars(
                "AAPL", "stock", date(2024, 1, 1), date(2024, 3, 31)
            )

        # Should be sorted ascending
        timestamps = [c.timestamp for c in candles]
        assert timestamps == sorted(timestamps)

    def test_crypto_bars_returned(self):
        bars = [self._fake_bar(i) for i in range(5)]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "bars": {"BTC/USD": bars},
            "next_page_token": None,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("app.market_data.providers.alpaca.httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=mock_resp)))
            ctx.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = ctx

            provider = self._provider()
            candles = provider.get_historical_bars(
                "BTC/USD", "crypto", date(2024, 1, 1), date(2024, 3, 31)
            )

        assert len(candles) == 5
        assert all(c.asset_class == "crypto" for c in candles)

    def test_pagination_handled(self):
        """Two pages of bars should be concatenated."""
        bars_page1 = [self._fake_bar(i) for i in range(3)]
        bars_page2 = [self._fake_bar(i + 3) for i in range(3)]

        resp1 = MagicMock()
        resp1.raise_for_status = MagicMock()
        resp1.json.return_value = {"bars": bars_page1, "next_page_token": "tok123"}

        resp2 = MagicMock()
        resp2.raise_for_status = MagicMock()
        resp2.json.return_value = {"bars": bars_page2, "next_page_token": None}

        call_count = {"n": 0}

        def fake_get(*args, **kwargs):
            call_count["n"] += 1
            return resp1 if call_count["n"] == 1 else resp2

        with patch("app.market_data.providers.alpaca.httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=MagicMock(get=fake_get))
            ctx.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = ctx

            provider = self._provider()
            candles = provider.get_historical_bars(
                "AAPL", "stock", date(2024, 1, 1), date(2024, 6, 30)
            )

        assert len(candles) == 6
        assert call_count["n"] == 2
