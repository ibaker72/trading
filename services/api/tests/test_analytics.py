"""Tests for analytics service, PositionMonitor, new broker order types, and /analytics endpoints."""
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trade(
    realized_pnl: float | None = None,
    status: str = "closed",
    opened_at: datetime | None = None,
    closed_at: datetime | None = None,
    side: str = "buy",
    entry_price: float = 100.0,
    exit_price: float | None = 102.0,
    quantity: float = 10.0,
    stop_loss_price: float = 99.0,
    take_profit_price: float = 103.0,
):
    t = MagicMock()
    t.realized_pnl = realized_pnl
    t.status = status
    t.opened_at = opened_at or datetime.now(UTC)
    t.closed_at = closed_at or (datetime.now(UTC) if status != "open" else None)
    t.side = side
    t.entry_price = entry_price
    t.exit_price = exit_price
    t.quantity = quantity
    t.stop_loss_price = stop_loss_price
    t.take_profit_price = take_profit_price
    return t


# ---------------------------------------------------------------------------
# Analytics service — pure function tests
# ---------------------------------------------------------------------------

class TestAnalyticsService:
    def test_win_rate_all_winners(self):
        from app.analytics.service import compute_win_rate
        trades = [_make_trade(realized_pnl=100.0), _make_trade(realized_pnl=50.0)]
        assert compute_win_rate(trades) == 1.0

    def test_win_rate_all_losers(self):
        from app.analytics.service import compute_win_rate
        trades = [_make_trade(realized_pnl=-50.0), _make_trade(realized_pnl=-20.0)]
        assert compute_win_rate(trades) == 0.0

    def test_win_rate_mixed(self):
        from app.analytics.service import compute_win_rate
        trades = [
            _make_trade(realized_pnl=100.0),
            _make_trade(realized_pnl=-50.0),
            _make_trade(realized_pnl=30.0),
            _make_trade(realized_pnl=-10.0),
        ]
        assert compute_win_rate(trades) == 0.5

    def test_win_rate_empty(self):
        from app.analytics.service import compute_win_rate
        assert compute_win_rate([]) == 0.0

    def test_win_rate_open_trades_excluded(self):
        from app.analytics.service import compute_win_rate
        trades = [
            _make_trade(realized_pnl=100.0, status="closed"),
            _make_trade(realized_pnl=None, status="open"),
        ]
        assert compute_win_rate(trades) == 1.0

    def test_sharpe_returns_float(self):
        from app.analytics.service import compute_sharpe
        trades = [_make_trade(realized_pnl=v) for v in [10.0, -5.0, 15.0, -3.0, 20.0]]
        result = compute_sharpe(trades)
        assert isinstance(result, float)

    def test_sharpe_zero_for_single_trade(self):
        from app.analytics.service import compute_sharpe
        assert compute_sharpe([_make_trade(realized_pnl=100.0)]) == 0.0

    def test_sharpe_zero_for_empty(self):
        from app.analytics.service import compute_sharpe
        assert compute_sharpe([]) == 0.0

    def test_max_drawdown_simple(self):
        from app.analytics.service import compute_max_drawdown
        # Peak at 100, drops to 80 → 20% drawdown
        curve = [100.0, 105.0, 90.0, 80.0, 95.0]
        dd = compute_max_drawdown(curve)
        assert abs(dd - (105.0 - 80.0) / 105.0) < 0.001

    def test_max_drawdown_no_drawdown(self):
        from app.analytics.service import compute_max_drawdown
        curve = [100.0, 110.0, 120.0, 130.0]
        assert compute_max_drawdown(curve) == 0.0

    def test_max_drawdown_empty(self):
        from app.analytics.service import compute_max_drawdown
        assert compute_max_drawdown([]) == 0.0

    def test_compute_avg_win_loss(self):
        from app.analytics.service import compute_avg_win_loss
        trades = [
            _make_trade(realized_pnl=100.0),
            _make_trade(realized_pnl=50.0),
            _make_trade(realized_pnl=-30.0),
            _make_trade(realized_pnl=-20.0),
        ]
        result = compute_avg_win_loss(trades)
        assert result["avg_win"] == 75.0
        assert result["avg_loss"] == 25.0
        assert result["ratio"] == 3.0

    def test_compute_avg_win_loss_no_losses(self):
        from app.analytics.service import compute_avg_win_loss
        trades = [_make_trade(realized_pnl=100.0)]
        result = compute_avg_win_loss(trades)
        assert result["avg_loss"] == 0.0
        assert result["ratio"] == 0.0

    def test_compute_pnl_series_sorted(self):
        from app.analytics.service import compute_pnl_series
        now = datetime.now(UTC)
        trades = [
            _make_trade(realized_pnl=50.0, closed_at=now - timedelta(hours=2)),
            _make_trade(realized_pnl=-20.0, closed_at=now - timedelta(hours=1)),
            _make_trade(realized_pnl=30.0, closed_at=now),
        ]
        series = compute_pnl_series(trades)
        assert len(series) == 3
        assert series[0]["pnl"] == 50.0
        assert series[1]["pnl"] == -20.0
        assert series[2]["pnl"] == 30.0
        assert series[0]["cumulative_pnl"] == 50.0
        assert series[1]["cumulative_pnl"] == 30.0
        assert series[2]["cumulative_pnl"] == 60.0

    def test_compute_pnl_series_excludes_open(self):
        from app.analytics.service import compute_pnl_series
        trades = [
            _make_trade(realized_pnl=100.0, status="closed"),
            _make_trade(realized_pnl=None, status="open"),
        ]
        series = compute_pnl_series(trades)
        assert len(series) == 1

    def test_build_equity_curve(self):
        from app.analytics.service import build_equity_curve
        now = datetime.now(UTC)
        trades = [
            _make_trade(realized_pnl=100.0, closed_at=now - timedelta(hours=2)),
            _make_trade(realized_pnl=-50.0, closed_at=now - timedelta(hours=1)),
        ]
        curve = build_equity_curve(trades, starting_equity=1000.0)
        assert curve[0] == 1000.0
        assert curve[1] == 1100.0
        assert curve[2] == 1050.0


# ---------------------------------------------------------------------------
# New broker order type tests
# ---------------------------------------------------------------------------

class TestBrokerNewOrderTypes:
    def _make_broker(self):
        from app.broker.alpaca import AlpacaBroker
        return AlpacaBroker("key", "secret", "https://paper-api.alpaca.markets")

    def _mock_client(self, payload):
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        return mock_client

    def test_place_limit_order(self):
        broker = self._make_broker()
        payload = {"id": "lim1", "type": "limit"}
        with patch("httpx.Client") as cls:
            cls.return_value.__enter__.return_value = self._mock_client(payload)
            result = broker.place_limit_order("AAPL", "buy", 5, 148.0, "stock")
        assert result["id"] == "lim1"
        body = cls.return_value.__enter__.return_value.post.call_args[1]["json"]
        assert body["type"] == "limit"
        assert body["limit_price"] == 148.0
        assert body["time_in_force"] == "day"

    def test_place_stop_order(self):
        broker = self._make_broker()
        payload = {"id": "stp1", "type": "stop"}
        with patch("httpx.Client") as cls:
            cls.return_value.__enter__.return_value = self._mock_client(payload)
            result = broker.place_stop_order("AAPL", "sell", 5, 145.0, "stock")
        assert result["id"] == "stp1"
        body = cls.return_value.__enter__.return_value.post.call_args[1]["json"]
        assert body["type"] == "stop"
        assert body["stop_price"] == 145.0

    def test_place_bracket_order(self):
        broker = self._make_broker()
        payload = {"id": "brk1", "order_class": "bracket"}
        with patch("httpx.Client") as cls:
            cls.return_value.__enter__.return_value = self._mock_client(payload)
            result = broker.place_bracket_order("AAPL", "buy", 10, 155.0, 145.0, "stock")
        assert result["id"] == "brk1"
        body = cls.return_value.__enter__.return_value.post.call_args[1]["json"]
        assert body["order_class"] == "bracket"
        assert body["take_profit"]["limit_price"] == 155.0
        assert body["stop_loss"]["stop_price"] == 145.0
        assert body["time_in_force"] == "day"

    def test_place_bracket_order_crypto_uses_gtc(self):
        broker = self._make_broker()
        payload = {"id": "brk2"}
        with patch("httpx.Client") as cls:
            cls.return_value.__enter__.return_value = self._mock_client(payload)
            broker.place_bracket_order("BTC/USD", "buy", 0.01, 70000.0, 65000.0, "crypto")
        body = cls.return_value.__enter__.return_value.post.call_args[1]["json"]
        assert body["time_in_force"] == "gtc"

    def test_place_limit_order_crypto_uses_gtc(self):
        broker = self._make_broker()
        payload = {"id": "lim2"}
        with patch("httpx.Client") as cls:
            cls.return_value.__enter__.return_value = self._mock_client(payload)
            broker.place_limit_order("ETH/USD", "sell", 1, 3000.0, "crypto")
        body = cls.return_value.__enter__.return_value.post.call_args[1]["json"]
        assert body["time_in_force"] == "gtc"


# ---------------------------------------------------------------------------
# PositionMonitor tests
# ---------------------------------------------------------------------------

class TestPositionMonitor:
    def _make_journal_entry(self, symbol="AAPL", side="buy", entry_price=150.0, qty=10.0):
        from app.models import TradeJournal
        entry = MagicMock(spec=TradeJournal)
        entry.symbol = symbol
        entry.side = side
        entry.entry_price = entry_price
        entry.quantity = qty
        entry.status = "open"
        entry.exit_order_id = None
        entry.exit_price = None
        entry.realized_pnl = None
        entry.closed_at = None
        return entry

    def test_check_exits_no_broker_returns_zero(self):
        from app.bot.monitor import PositionMonitor
        monitor = PositionMonitor(broker=None)
        db = MagicMock()
        assert monitor.check_exits(db) == 0

    def test_check_exits_no_closed_orders(self):
        from app.bot.monitor import PositionMonitor
        mock_broker = MagicMock()
        mock_broker.get_orders.return_value = []
        monitor = PositionMonitor(broker=mock_broker)
        db = MagicMock()
        assert monitor.check_exits(db) == 0

    def test_check_exits_reconciles_sell_exit(self):
        from app.bot.monitor import PositionMonitor
        from app.bot import state as bot_state
        from app.bot.state import BotState
        bot_state._state = BotState()

        closed_orders = [
            {
                "id": "exit1",
                "symbol": "AAPL",
                "side": "sell",
                "type": "limit",
                "status": "filled",
                "filled_avg_price": "155.0",
            }
        ]
        mock_broker = MagicMock()
        mock_broker.get_orders.return_value = closed_orders

        journal_entry = self._make_journal_entry("AAPL", "buy", 150.0, 10.0)

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [journal_entry]

        monitor = PositionMonitor(broker=mock_broker)
        count = monitor.check_exits(db)

        assert count == 1
        assert journal_entry.exit_order_id == "exit1"
        assert journal_entry.exit_price == 155.0
        assert journal_entry.realized_pnl == pytest.approx(50.0)  # (155-150)*10
        assert journal_entry.status == "took_profit"
        db.commit.assert_called_once()

    def test_check_exits_stop_loss_sets_stopped_out(self):
        from app.bot.monitor import PositionMonitor
        from app.bot import state as bot_state
        from app.bot.state import BotState
        bot_state._state = BotState()

        closed_orders = [
            {
                "id": "sl1",
                "symbol": "NVDA",
                "side": "sell",
                "type": "stop",
                "status": "filled",
                "filled_avg_price": "480.0",
            }
        ]
        mock_broker = MagicMock()
        mock_broker.get_orders.return_value = closed_orders

        entry = self._make_journal_entry("NVDA", "buy", 500.0, 5.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        monitor = PositionMonitor(broker=mock_broker)
        count = monitor.check_exits(db)

        assert count == 1
        assert entry.status == "stopped_out"
        assert entry.realized_pnl == pytest.approx(-100.0)  # (480-500)*5

    def test_check_exits_unmatched_symbol_skipped(self):
        from app.bot.monitor import PositionMonitor
        closed_orders = [
            {
                "id": "exit9",
                "symbol": "TSLA",
                "side": "sell",
                "type": "limit",
                "status": "filled",
                "filled_avg_price": "200.0",
            }
        ]
        mock_broker = MagicMock()
        mock_broker.get_orders.return_value = closed_orders

        entry = self._make_journal_entry("AAPL", "buy", 150.0)
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [entry]

        monitor = PositionMonitor(broker=mock_broker)
        count = monitor.check_exits(db)
        assert count == 0


# ---------------------------------------------------------------------------
# /analytics endpoint tests
# ---------------------------------------------------------------------------

class TestAnalyticsEndpoints:
    def test_performance_returns_200(self):
        resp = client.get("/analytics/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert "win_rate" in data
        assert "sharpe" in data
        assert "max_drawdown" in data
        assert "total_trades" in data
        assert "open_trades" in data

    def test_performance_empty_db(self):
        resp = client.get("/analytics/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trades"] == 0
        assert data["win_rate"] == 0.0
        assert data["sharpe"] == 0.0

    def test_trades_returns_list(self):
        resp = client.get("/analytics/trades")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_trades_status_filter(self):
        resp = client.get("/analytics/trades", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data:
            assert item["status"] == "open"

    def test_pnl_series_returns_list(self):
        resp = client.get("/analytics/pnl-series")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_trades_limit_param(self):
        resp = client.get("/analytics/trades", params={"limit": 5})
        assert resp.status_code == 200
