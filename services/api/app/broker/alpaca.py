import httpx

from app.market_data.schemas import AssetClass


class AlpacaBroker:
    """Thin wrapper around the Alpaca trading API."""

    def __init__(self, api_key: str, secret_key: str, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        }

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account(self) -> dict:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{self._base_url}/v2/account", headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self) -> list[dict]:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{self._base_url}/v2/positions", headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def get_orders(self, status: str = "open") -> list[dict]:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{self._base_url}/v2/orders",
                params={"status": status},
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        asset_class: AssetClass = "stock",
    ) -> dict:
        time_in_force = "gtc" if asset_class == "crypto" else "day"
        body = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": "market",
            "time_in_force": time_in_force,
        }
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{self._base_url}/v2/orders",
                json=body,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    def cancel_order(self, order_id: str) -> bool:
        with httpx.Client(timeout=10) as client:
            resp = client.delete(
                f"{self._base_url}/v2/orders/{order_id}",
                headers=self._headers,
            )
            return resp.status_code == 204

    def cancel_all_orders(self) -> int:
        with httpx.Client(timeout=10) as client:
            resp = client.delete(f"{self._base_url}/v2/orders", headers=self._headers)
            resp.raise_for_status()
            canceled = resp.json()
            return len(canceled) if isinstance(canceled, list) else 0

    # ------------------------------------------------------------------
    # Positions management
    # ------------------------------------------------------------------

    def close_position(self, symbol: str) -> dict:
        with httpx.Client(timeout=10) as client:
            resp = client.delete(
                f"{self._base_url}/v2/positions/{symbol}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Portfolio history
    # ------------------------------------------------------------------

    def get_portfolio_history(self, period: str = "1D", timeframe: str = "5Min") -> dict:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{self._base_url}/v2/account/portfolio/history",
                params={"period": period, "timeframe": timeframe},
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()
