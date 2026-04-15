"""Tests for AlpacaBroker and /broker endpoints."""
import json
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import client


# ---------------------------------------------------------------------------
# AlpacaBroker unit tests (mock httpx)
# ---------------------------------------------------------------------------

class TestAlpacaBroker:
    def _make_broker(self):
        from app.broker.alpaca import AlpacaBroker
        return AlpacaBroker(
            api_key="test-key",
            secret_key="test-secret",
            base_url="https://paper-api.alpaca.markets",
        )

    def _mock_response(self, payload, status_code=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_get_account(self):
        broker = self._make_broker()
        payload = {"equity": "100000.00", "cash": "95000.00"}
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response(payload)
            result = broker.get_account()
        assert result["equity"] == "100000.00"

    def test_get_positions(self):
        broker = self._make_broker()
        payload = [{"symbol": "AAPL", "qty": "10"}]
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response(payload)
            result = broker.get_positions()
        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL"

    def test_place_market_order_stock(self):
        broker = self._make_broker()
        payload = {"id": "abc123", "symbol": "AAPL", "side": "buy", "filled_avg_price": "150.00"}
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = self._mock_response(payload)
            result = broker.place_market_order("AAPL", "buy", 10, "stock")
        assert result["id"] == "abc123"
        call_kwargs = mock_client.post.call_args
        body = call_kwargs[1]["json"]
        assert body["time_in_force"] == "day"

    def test_place_market_order_crypto(self):
        broker = self._make_broker()
        payload = {"id": "xyz789", "symbol": "BTC/USD"}
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.post.return_value = self._mock_response(payload)
            result = broker.place_market_order("BTC/USD", "buy", 0.1, "crypto")
        body = mock_client.post.call_args[1]["json"]
        assert body["time_in_force"] == "gtc"

    def test_cancel_order_success(self):
        broker = self._make_broker()
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.status_code = 204
            mock_client.delete.return_value = mock_resp
            result = broker.cancel_order("abc123")
        assert result is True

    def test_cancel_all_orders(self):
        broker = self._make_broker()
        payload = [{"id": "1"}, {"id": "2"}]
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.delete.return_value = self._mock_response(payload)
            count = broker.cancel_all_orders()
        assert count == 2

    def test_get_portfolio_history(self):
        broker = self._make_broker()
        payload = {"timestamp": [1000, 2000], "equity": [100.0, 101.0]}
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response(payload)
            result = broker.get_portfolio_history()
        assert result["equity"] == [100.0, 101.0]


# ---------------------------------------------------------------------------
# AlpacaMarketDataProvider unit tests
# ---------------------------------------------------------------------------

class TestAlpacaMarketDataProvider:
    def _make_provider(self):
        from app.market_data.providers.alpaca import AlpacaMarketDataProvider
        return AlpacaMarketDataProvider(
            api_key="test-key",
            secret_key="test-secret",
            data_url="https://data.alpaca.markets",
            feed="iex",
        )

    def _mock_response(self, payload, status_code=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_raises_on_empty_key(self):
        from app.market_data.providers.alpaca import AlpacaMarketDataProvider
        with pytest.raises(RuntimeError, match="Alpaca API key"):
            AlpacaMarketDataProvider(api_key="", secret_key="", data_url="")

    def test_get_quote_stock(self):
        provider = self._make_provider()
        payload = {"quote": {"bp": 149.0, "ap": 151.0, "t": "2024-01-01T10:00:00Z"}}
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response(payload)
            quote = provider.get_quote("AAPL", "stock")
        assert quote.price == 150.0
        assert quote.symbol == "AAPL"

    def test_get_candles_stock(self):
        provider = self._make_provider()
        bars = [
            {"t": "2024-01-01T10:00:00Z", "o": 100.0, "h": 102.0, "l": 99.0, "c": 101.0, "v": 5000},
            {"t": "2024-01-01T10:05:00Z", "o": 101.0, "h": 103.0, "l": 100.0, "c": 102.0, "v": 6000},
        ]
        payload = {"bars": bars}
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response(payload)
            candles = provider.get_candles("AAPL", "stock", "5m", 2)
        assert len(candles) == 2
        assert candles[0].open == 100.0
        assert candles[0].provider == "alpaca"

    def test_get_multi_quotes(self):
        provider = self._make_provider()
        payload = {"quotes": {"AAPL": {"bp": 149.0, "ap": 151.0}, "NVDA": {"bp": 499.0, "ap": 501.0}}}
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response(payload)
            prices = provider.get_multi_quotes(["AAPL", "NVDA"], "stock")
        assert prices["AAPL"] == 150.0
        assert prices["NVDA"] == 500.0

    def test_candle_limit_capped_at_1000(self):
        provider = self._make_provider()
        payload = {"bars": []}
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = self._mock_response(payload)
            provider.get_candles("AAPL", "stock", "1m", 5000)
        call_params = mock_client.get.call_args[1]["params"]
        assert call_params["limit"] == 1000


# ---------------------------------------------------------------------------
# /broker endpoint tests (503 when unconfigured)
# ---------------------------------------------------------------------------

class TestBrokerEndpoints:
    def test_account_503_when_not_configured(self):
        resp = client.get("/broker/account")
        assert resp.status_code == 503
        assert "Alpaca not configured" in resp.json()["detail"]

    def test_positions_503_when_not_configured(self):
        resp = client.get("/broker/positions")
        assert resp.status_code == 503

    def test_orders_503_when_not_configured(self):
        resp = client.get("/broker/orders")
        assert resp.status_code == 503

    def test_portfolio_history_503_when_not_configured(self):
        resp = client.get("/broker/portfolio/history")
        assert resp.status_code == 503

    def test_cancel_all_orders_503_when_not_configured(self):
        resp = client.delete("/broker/orders")
        assert resp.status_code == 503

    def test_close_position_503_when_not_configured(self):
        resp = client.delete("/broker/positions/AAPL")
        assert resp.status_code == 503
