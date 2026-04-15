from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.market_data.schemas import AssetClass

RuleType = Literal[
    "price_breakout",
    "ma_cross",
    "rsi_threshold",
    "volume_spike",
    "volatility_max",
    "gap_up",
    "gap_down",
    "vwap_cross",
    "ema_cross",
]


class StrategyRule(BaseModel):
    rule_type: RuleType
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class StrategyCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    symbol: str = Field(min_length=1, max_length=20)
    asset_class: AssetClass
    timeframe: str = Field(default="1h")
    cooldown_minutes: int = Field(default=60, ge=1, le=1440)
    rules: list[StrategyRule]


class StrategyRead(BaseModel):
    id: int
    name: str
    symbol: str
    asset_class: AssetClass
    timeframe: str
    cooldown_minutes: int
    is_active: bool
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


class SignalRead(BaseModel):
    id: int
    strategy_id: int
    symbol: str
    timeframe: str
    signal_type: str
    score: float
    explanation: str
    triggered_at: datetime

    class Config:
        from_attributes = True


class ScanResult(BaseModel):
    generated: bool
    reason: str
    signal: SignalRead | None = None


class MultiTimeframeScanResult(BaseModel):
    symbol: str
    asset_class: AssetClass
    fired_timeframes: list[str]
    aggregate_score: float
    should_trade: bool
    suggested_side: Literal["buy", "sell", "none"]


class WatchlistScanResult(BaseModel):
    scanned_at: datetime
    results: list[MultiTimeframeScanResult]
    top_pick: MultiTimeframeScanResult | None
