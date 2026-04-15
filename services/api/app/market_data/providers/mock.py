from datetime import UTC, datetime, timedelta

from app.market_data.providers.base import MarketDataProvider
from app.market_data.schemas import AssetClass, MarketAsset, MarketCandle, MarketQuote


class MockMarketDataProvider(MarketDataProvider):
    name = "mock"

    def __init__(self) -> None:
        self._assets = [
            MarketAsset(symbol="BTCUSD", name="Bitcoin / USD", asset_class="crypto"),
            MarketAsset(symbol="ETHUSD", name="Ethereum / USD", asset_class="crypto"),
            MarketAsset(symbol="NVDA", name="NVIDIA Corp.", asset_class="stock"),
            MarketAsset(symbol="SPY", name="SPDR S&P 500 ETF", asset_class="stock"),
        ]

    def list_assets(self, asset_class: AssetClass | None = None) -> list[MarketAsset]:
        if asset_class is None:
            return self._assets
        return [asset for asset in self._assets if asset.asset_class == asset_class]

    def get_quote(self, symbol: str, asset_class: AssetClass) -> MarketQuote:
        now = datetime.now(UTC)
        price = self._base_price(symbol) + (now.minute / 100)
        return MarketQuote(
            symbol=symbol.upper(),
            asset_class=asset_class,
            price=round(price, 2),
            timestamp=now,
            provider=self.name,
        )

    def get_candles(
        self,
        symbol: str,
        asset_class: AssetClass,
        timeframe: str,
        limit: int,
    ) -> list[MarketCandle]:
        step = timeframe_to_timedelta(timeframe)
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        candles: list[MarketCandle] = []
        base = self._base_price(symbol)

        for idx in range(limit):
            ts = now - step * (limit - idx)
            drift = idx * 0.25
            open_price = base + drift
            close_price = open_price + 0.1
            high_price = close_price + 0.2
            low_price = open_price - 0.2
            candles.append(
                MarketCandle(
                    symbol=symbol.upper(),
                    asset_class=asset_class,
                    timeframe=timeframe,
                    timestamp=ts,
                    open=round(open_price, 2),
                    high=round(high_price, 2),
                    low=round(low_price, 2),
                    close=round(close_price, 2),
                    volume=round(1000 + idx * 10, 2),
                    provider=self.name,
                )
            )

        return candles

    @staticmethod
    def _base_price(symbol: str) -> float:
        seed = sum(ord(ch) for ch in symbol.upper())
        return float((seed % 900) + 50)


def timeframe_to_timedelta(timeframe: str) -> timedelta:
    if timeframe.endswith("m"):
        return timedelta(minutes=int(timeframe[:-1]))
    if timeframe.endswith("h"):
        return timedelta(hours=int(timeframe[:-1]))
    if timeframe.endswith("d"):
        return timedelta(days=int(timeframe[:-1]))
    raise ValueError(f"Unsupported timeframe: {timeframe}")
