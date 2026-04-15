from abc import ABC, abstractmethod

from app.market_data.schemas import AssetClass, MarketAsset, MarketCandle, MarketQuote


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def list_assets(self, asset_class: AssetClass | None = None) -> list[MarketAsset]:
        raise NotImplementedError

    @abstractmethod
    def get_quote(self, symbol: str, asset_class: AssetClass) -> MarketQuote:
        raise NotImplementedError

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        asset_class: AssetClass,
        timeframe: str,
        limit: int,
    ) -> list[MarketCandle]:
        raise NotImplementedError
