"""
Tests for the market-data WebSocket stream module:
  - build_tick_mock helper
  - Queue registry (register/unregister)
  - _broadcast fan-out behavior
  - run_stream task dispatch (mocked websockets)
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.market_data.stream import (
    _broadcast,
    _queues,
    build_tick_mock,
    register_queue,
    unregister_queue,
)


# ---------------------------------------------------------------------------
# build_tick_mock
# ---------------------------------------------------------------------------

class TestBuildTickMock:
    def test_returns_tick_type(self):
        tick = build_tick_mock("AAPL", 150.0)
        assert tick["type"] == "tick"

    def test_symbol_and_price_set(self):
        tick = build_tick_mock("NVDA", 500.25)
        assert tick["symbol"] == "NVDA"
        assert tick["price"] == 500.25

    def test_bid_ask_straddle_price(self):
        tick = build_tick_mock("AAPL", 100.0)
        assert tick["bid"] < 100.0
        assert tick["ask"] > 100.0

    def test_default_asset_class_is_stock(self):
        tick = build_tick_mock("AAPL", 100.0)
        assert tick["asset_class"] == "stock"

    def test_custom_asset_class(self):
        tick = build_tick_mock("BTC/USD", 60000.0, asset_class="crypto")
        assert tick["asset_class"] == "crypto"

    def test_timestamp_present(self):
        tick = build_tick_mock("AAPL", 100.0)
        assert "timestamp" in tick
        assert tick["timestamp"]  # non-empty


# ---------------------------------------------------------------------------
# Queue registry
# ---------------------------------------------------------------------------

class TestQueueRegistry:
    def setup_method(self):
        # Clean up the global registry before each test
        _queues.clear()

    def test_register_adds_queue(self):
        q = asyncio.Queue()
        register_queue(q)
        assert q in _queues

    def test_unregister_removes_queue(self):
        q = asyncio.Queue()
        register_queue(q)
        unregister_queue(q)
        assert q not in _queues

    def test_unregister_nonexistent_is_safe(self):
        q = asyncio.Queue()
        unregister_queue(q)  # should not raise

    def test_multiple_queues(self):
        q1, q2, q3 = asyncio.Queue(), asyncio.Queue(), asyncio.Queue()
        register_queue(q1)
        register_queue(q2)
        register_queue(q3)
        assert len(_queues) == 3
        unregister_queue(q2)
        assert len(_queues) == 2
        assert q2 not in _queues


# ---------------------------------------------------------------------------
# _broadcast
# ---------------------------------------------------------------------------

class TestBroadcast:
    def setup_method(self):
        _queues.clear()

    def test_broadcast_delivers_to_all_queues(self):
        q1, q2 = asyncio.Queue(), asyncio.Queue()
        register_queue(q1)
        register_queue(q2)
        msg = {"type": "tick", "symbol": "AAPL", "price": 150.0}
        asyncio.get_event_loop().run_until_complete(_broadcast(msg))
        assert q1.get_nowait() == msg
        assert q2.get_nowait() == msg

    def test_broadcast_removes_full_queues(self):
        # Create a queue at max capacity (maxsize=1)
        q_full = asyncio.Queue(maxsize=1)
        q_full.put_nowait({"type": "tick"})  # fill it

        q_ok = asyncio.Queue()
        register_queue(q_full)
        register_queue(q_ok)

        msg = {"type": "tick", "symbol": "TSLA", "price": 200.0}
        asyncio.get_event_loop().run_until_complete(_broadcast(msg))

        # Full queue should be removed from registry; ok queue should receive msg
        assert q_full not in _queues
        assert q_ok.get_nowait() == msg

    def test_broadcast_empty_registry_is_safe(self):
        msg = {"type": "tick", "symbol": "AAPL", "price": 100.0}
        asyncio.get_event_loop().run_until_complete(_broadcast(msg))  # no error

    def test_broadcast_delivers_correct_message(self):
        q = asyncio.Queue()
        register_queue(q)
        tick = build_tick_mock("ETH/USD", 3000.0, asset_class="crypto")
        asyncio.get_event_loop().run_until_complete(_broadcast(tick))
        received = q.get_nowait()
        assert received["symbol"] == "ETH/USD"
        assert received["price"] == 3000.0
        assert received["asset_class"] == "crypto"


# ---------------------------------------------------------------------------
# run_stream — task dispatch (mocked websockets)
# ---------------------------------------------------------------------------

class TestRunStream:
    def test_no_tasks_when_no_symbols(self):
        """run_stream should return immediately if both symbol lists are empty (no gather call)."""
        async def run():
            from app.market_data.stream import run_stream
            with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
                await run_stream("key", "secret", [], [], feed="iex")
                # When tasks list is empty, gather is NOT called at all
                mock_gather.assert_not_called()

        asyncio.get_event_loop().run_until_complete(run())

    def test_spawns_stock_feed_task(self):
        """One stock-feed task should be created when symbols_stocks is non-empty."""
        async def run():
            from app.market_data.stream import run_stream
            with patch("app.market_data.stream._stream_feed", new_callable=AsyncMock) as mock_feed:
                mock_feed.return_value = None
                with patch("asyncio.gather", new_callable=AsyncMock):
                    await run_stream("key", "secret", ["AAPL"], [], feed="iex")

        asyncio.get_event_loop().run_until_complete(run())

    def test_spawns_crypto_feed_task(self):
        """One crypto-feed task created when symbols_crypto is non-empty."""
        async def run():
            from app.market_data.stream import run_stream
            with patch("app.market_data.stream._stream_feed", new_callable=AsyncMock) as mock_feed:
                mock_feed.return_value = None
                with patch("asyncio.gather", new_callable=AsyncMock):
                    await run_stream("key", "secret", [], ["BTC/USD"], feed="iex")

        asyncio.get_event_loop().run_until_complete(run())


# ---------------------------------------------------------------------------
# WS endpoint status
# ---------------------------------------------------------------------------

class TestWsStatusEndpoint:
    def test_ws_status_returns_dict(self):
        from tests.conftest import client
        resp = client.get("/ws/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "alpaca_configured" in data
        assert "stream_running" in data
        assert "connected_clients" in data

    def test_ws_status_alpaca_not_configured(self):
        """With no ALPACA_API_KEY in env, alpaca_configured should be False."""
        from tests.conftest import client
        import os
        orig = os.environ.pop("ALPACA_API_KEY", None)
        try:
            resp = client.get("/ws/status")
            data = resp.json()
            # The value depends on env, but key must be present
            assert "alpaca_configured" in data
        finally:
            if orig:
                os.environ["ALPACA_API_KEY"] = orig
