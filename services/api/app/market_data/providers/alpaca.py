from datetime import datetime, UTC

import httpx

from app.market_data.providers.base import MarketDataProvider
from app.market_data.schemas import AssetClass, MarketAsset, MarketCandle, MarketQuote

_TIMEFRAME_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "30m": "30Min",
    "1h": "1Hour",
    "4h": "4Hour",
    "1d": "1Day",
}


class AlpacaMarketDataProvider(MarketDataProvider):
    name = "alpaca"

    def __init__(self, api_key: str, secret_key: str, data_url: str, feed: str = "iex") -> None:
        if not api_key:
            raise RuntimeError(
                "Alpaca API key is not configured. Set ALPACA_API_KEY in your environment."
            )
        self._api_key = api_key
        self._secret_key = secret_key
        self._data_url = data_url.rstrip("/")
        self._feed = feed
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        }

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def list_assets(self, asset_class: AssetClass | None = None) -> list[MarketAsset]:
        results: list[MarketAsset] = []

        classes_to_fetch: list[AssetClass] = (
            [asset_class] if asset_class else ["stock", "crypto"]
        )

        with httpx.Client(timeout=10) as client:
            for ac in classes_to_fetch:
                alpaca_class = "us_equity" if ac == "stock" else "crypto"
                resp = client.get(
                    f"{self._data_url.replace('data.alpaca.markets', 'api.alpaca.markets')}/v2/assets",
                    params={"status": "active", "asset_class": alpaca_class},
                    headers=self._headers,
                )
                resp.raise_for_status()
                assets = resp.json()
                tradable = [a for a in assets if a.get("tradable", False)][:50]
                for a in tradable:
                    results.append(
                        MarketAsset(
                            symbol=a["symbol"],
                            name=a.get("name") or a["symbol"],
                            asset_class=ac,
                        )
                    )

        return results

    # ------------------------------------------------------------------
    # Quote
    # ------------------------------------------------------------------

    def get_quote(self, symbol: str, asset_class: AssetClass) -> MarketQuote:
        with httpx.Client(timeout=10) as client:
            if asset_class == "stock":
                resp = client.get(
                    f"{self._data_url}/v2/stocks/{symbol}/quotes/latest",
                    params={"feed": self._feed},
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
                quote = data.get("quote", {})
                bid = float(quote.get("bp", 0) or 0)
                ask = float(quote.get("ap", 0) or 0)
                price = (bid + ask) / 2 if (bid > 0 and ask > 0) else max(bid, ask)
                ts_str = quote.get("t", "")
            else:
                resp = client.get(
                    f"{self._data_url}/v1beta3/crypto/us/latest/quotes",
                    params={"symbols": symbol},
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
                quotes = data.get("quotes", {})
                quote = quotes.get(symbol, {})
                bid = float(quote.get("bp", 0) or 0)
                ask = float(quote.get("ap", 0) or 0)
                price = (bid + ask) / 2 if (bid > 0 and ask > 0) else max(bid, ask)
                ts_str = quote.get("t", "")

        try:
            timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else datetime.now(UTC)
        except ValueError:
            timestamp = datetime.now(UTC)

        return MarketQuote(
            symbol=symbol.upper(),
            asset_class=asset_class,
            price=round(price, 6),
            timestamp=timestamp,
            provider=self.name,
        )

    # ------------------------------------------------------------------
    # Candles
    # ------------------------------------------------------------------

    def get_candles(
        self,
        symbol: str,
        asset_class: AssetClass,
        timeframe: str,
        limit: int,
    ) -> list[MarketCandle]:
        limit = min(limit, 1000)
        alpaca_tf = _TIMEFRAME_MAP.get(timeframe, "1Hour")

        with httpx.Client(timeout=10) as client:
            if asset_class == "stock":
                resp = client.get(
                    f"{self._data_url}/v2/stocks/{symbol}/bars",
                    params={
                        "timeframe": alpaca_tf,
                        "limit": limit,
                        "feed": self._feed,
                        "adjustment": "raw",
                    },
                    headers=self._headers,
                )
                resp.raise_for_status()
                raw_bars = resp.json().get("bars", []) or []
            else:
                resp = client.get(
                    f"{self._data_url}/v1beta3/crypto/us/bars",
                    params={
                        "symbols": symbol,
                        "timeframe": alpaca_tf,
                        "limit": limit,
                    },
                    headers=self._headers,
                )
                resp.raise_for_status()
                bars_dict = resp.json().get("bars", {}) or {}
                raw_bars = bars_dict.get(symbol, []) or []

        candles: list[MarketCandle] = []
        for bar in raw_bars:
            try:
                ts = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            candles.append(
                MarketCandle(
                    symbol=symbol.upper(),
                    asset_class=asset_class,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=float(bar.get("o", 0)),
                    high=float(bar.get("h", 0)),
                    low=float(bar.get("l", 0)),
                    close=float(bar.get("c", 0)),
                    volume=float(bar.get("v", 0)),
                    provider=self.name,
                )
            )

        return candles

    # ------------------------------------------------------------------
    # Batch quotes
    # ------------------------------------------------------------------

    def get_multi_quotes(
        self, symbols: list[str], asset_class: AssetClass
    ) -> dict[str, float]:
        if not symbols:
            return {}

        prices: dict[str, float] = {}

        with httpx.Client(timeout=10) as client:
            if asset_class == "stock":
                resp = client.get(
                    f"{self._data_url}/v2/stocks/quotes/latest",
                    params={"symbols": ",".join(symbols), "feed": self._feed},
                    headers=self._headers,
                )
                resp.raise_for_status()
                quotes = resp.json().get("quotes", {})
                for sym, q in quotes.items():
                    bid = float(q.get("bp", 0) or 0)
                    ask = float(q.get("ap", 0) or 0)
                    prices[sym] = (bid + ask) / 2 if (bid > 0 and ask > 0) else max(bid, ask)
            else:
                resp = client.get(
                    f"{self._data_url}/v1beta3/crypto/us/latest/quotes",
                    params={"symbols": ",".join(symbols)},
                    headers=self._headers,
                )
                resp.raise_for_status()
                quotes = resp.json().get("quotes", {})
                for sym, q in quotes.items():
                    bid = float(q.get("bp", 0) or 0)
                    ask = float(q.get("ap", 0) or 0)
                    prices[sym] = (bid + ask) / 2 if (bid > 0 and ask > 0) else max(bid, ask)

        return prices
