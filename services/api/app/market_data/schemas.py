from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AssetClass = Literal["stock", "crypto"]


class MarketAsset(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    asset_class: AssetClass


class MarketQuote(BaseModel):
    symbol: str
    asset_class: AssetClass
    price: float
    timestamp: datetime
    provider: str


class MarketCandle(BaseModel):
    symbol: str
    asset_class: AssetClass
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    provider: str


class DataQualityReport(BaseModel):
    expected_interval_seconds: int
    missing_intervals: int
    is_stale: bool
