"""Tests for TradingBotEngine, bot state, and /bot endpoints."""
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import client


# ---------------------------------------------------------------------------
# BotState tests
# ---------------------------------------------------------------------------

class TestBotState:
    def setup_method(self):
        # Reset state before each test
        from app.bot import state as bot_state
        from app.bot.state import BotState, BotStatus
        bot_state._state = BotState()

    def test_initial_status_is_stopped(self):
        from app.bot.state import get_state, BotStatus
        assert get_state().status == BotStatus.STOPPED

    def test_set_status_running(self):
        from app.bot.state import set_status, get_state, BotStatus
        set_status(BotStatus.RUNNING)
        assert get_state().status == BotStatus.RUNNING
        assert get_state().started_at is not None

    def test_record_scan(self):
        from app.bot.state import record_scan, get_state
        record_scan()
        assert get_state().last_scan_at is not None

    def test_record_trade(self):
        from app.bot.state import record_trade, get_state
        record_trade()
        record_trade()
        assert get_state().trades_today == 2

    def test_record_error(self):
        from app.bot.state import record_error, get_state, BotStatus
        record_error("something failed")
        state = get_state()
        assert state.errors_today == 1
        assert state.last_error == "something failed"
        assert state.status == BotStatus.ERROR


# ---------------------------------------------------------------------------
# TradingBotEngine.run_cycle tests
# ---------------------------------------------------------------------------

class TestTradingBotEngine:
    def _make_settings(self, with_alpaca=False):
        settings = MagicMock()
        settings.alpaca_api_key = "test-key" if with_alpaca else ""
        settings.alpaca_secret_key = "test-secret"
        settings.alpaca_base_url = "https://paper-api.alpaca.markets"
        settings.alpaca_data_url = "https://data.alpaca.markets"
        settings.alpaca_feed = "iex"
        settings.watchlist_stocks = "AAPL,SPY"
        settings.watchlist_crypto = "BTC/USD"
        return settings

    def setup_method(self):
        from app.bot import state as bot_state
        from app.bot.state import BotState
        bot_state._state = BotState()

    def test_run_cycle_skips_when_stopped(self):
        from app.bot.engine import TradingBotEngine
        from app.bot.state import BotStatus

        settings = self._make_settings()
        engine = TradingBotEngine(db_session_factory=MagicMock(), settings=settings)

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = engine.run_cycle(db)
        # Status is STOPPED so cycle skips
        assert result["scanned"] == 0
        assert result["orders_placed"] == 0

    def test_run_cycle_respects_kill_switch(self):
        from app.bot.engine import TradingBotEngine
        from app.bot.state import BotStatus, set_status
        from app.models import GlobalControl

        settings = self._make_settings()
        engine = TradingBotEngine(db_session_factory=MagicMock(), settings=settings)
        set_status(BotStatus.RUNNING)

        kill_switch = GlobalControl(key="global_kill_switch", value="on")
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = kill_switch

        result = engine.run_cycle(db)
        assert result["scanned"] == 0

    def test_run_cycle_no_broker_skips_orders(self):
        from app.bot.engine import TradingBotEngine
        from app.bot.state import BotStatus, set_status
        from app.strategy.schemas import MultiTimeframeScanResult, WatchlistScanResult
        from datetime import UTC, datetime

        settings = self._make_settings(with_alpaca=False)
        engine = TradingBotEngine(db_session_factory=MagicMock(), settings=settings)
        set_status(BotStatus.RUNNING)

        # Mock scan returning a tradeable signal
        mock_scan_result = WatchlistScanResult(
            scanned_at=datetime.now(UTC),
            results=[
                MultiTimeframeScanResult(
                    symbol="AAPL",
                    asset_class="stock",
                    fired_timeframes=["5m", "15m"],
                    aggregate_score=0.75,
                    should_trade=True,
                    suggested_side="buy",
                )
            ],
            top_pick=None,
        )

        engine._scanner = MagicMock()
        engine._scanner.scan_watchlist.return_value = mock_scan_result

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.first.side_effect = None

        # Make _ensure_bot_user create a user
        from app.models import User
        mock_user = User()
        mock_user.id = 1
        engine._ensure_bot_user = MagicMock(return_value=mock_user)

        result = engine.run_cycle(db)
        # No broker → orders_placed stays 0
        assert result["orders_placed"] == 0
        assert result["signals_found"] == 1

    def test_run_cycle_with_mock_broker_places_order(self):
        from app.bot.engine import TradingBotEngine
        from app.bot.state import BotStatus, set_status
        from app.strategy.schemas import MultiTimeframeScanResult, WatchlistScanResult
        from app.models import User, RiskPolicy
        from datetime import UTC, datetime

        settings = self._make_settings(with_alpaca=True)
        engine = TradingBotEngine(db_session_factory=MagicMock(), settings=settings)
        set_status(BotStatus.RUNNING)

        mock_broker = MagicMock()
        mock_broker.get_account.return_value = {"equity": "100000.00"}
        mock_broker.place_market_order.return_value = {"id": "order1", "filled_avg_price": "150.00"}
        engine._broker = mock_broker

        mock_scan_result = WatchlistScanResult(
            scanned_at=datetime.now(UTC),
            results=[
                MultiTimeframeScanResult(
                    symbol="AAPL",
                    asset_class="stock",
                    fired_timeframes=["5m", "15m"],
                    aggregate_score=0.75,
                    should_trade=True,
                    suggested_side="buy",
                )
            ],
            top_pick=None,
        )
        engine._scanner = MagicMock()
        engine._scanner.scan_watchlist.return_value = mock_scan_result

        mock_user = MagicMock()
        mock_user.id = 1
        engine._ensure_bot_user = MagicMock(return_value=mock_user)

        mock_policy = MagicMock()
        mock_policy.is_kill_switch_on = False
        mock_policy.live_trading_enabled = True
        mock_policy.allowed_symbols = []
        mock_policy.max_risk_per_trade_pct = 2.0
        mock_policy.max_daily_loss = 1000.0
        mock_policy.max_open_positions = 10
        mock_policy.consecutive_loss_limit = 3

        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            None,      # GlobalControl kill switch → None (off)
            mock_policy,  # RiskPolicy
        ]
        db.add = MagicMock()
        db.commit = MagicMock()

        result = engine.run_cycle(db)
        assert result["signals_found"] == 1
        assert result["orders_placed"] == 1


# ---------------------------------------------------------------------------
# /bot endpoint tests
# ---------------------------------------------------------------------------

class TestBotEndpoints:
    def setup_method(self):
        from app.bot import state as bot_state
        from app.bot.state import BotState
        bot_state._state = BotState()

    def test_get_status(self):
        resp = client.get("/bot/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "STOPPED"

    def test_start_bot(self):
        resp = client.post("/bot/start")
        assert resp.status_code == 200
        assert resp.json()["started"] is True

    def test_pause_bot(self):
        resp = client.post("/bot/pause")
        assert resp.status_code == 200
        assert resp.json()["paused"] is True

    def test_stop_bot(self):
        client.post("/bot/start")
        resp = client.post("/bot/stop")
        assert resp.status_code == 200
        assert resp.json()["stopped"] is True
        status_resp = client.get("/bot/status")
        assert status_resp.json()["status"] == "STOPPED"

    def test_get_history_empty(self):
        resp = client.get("/bot/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_summary(self):
        resp = client.get("/bot/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "trades_today" in data
        assert "errors_today" in data
        # equity is None when Alpaca is not configured
        assert data["equity"] is None
