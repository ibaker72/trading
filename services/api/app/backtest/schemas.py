"""
Pydantic schemas for the backtesting engine.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.market_data.schemas import AssetClass
from app.strategy.schemas import StrategyRule


class BacktestRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    asset_class: AssetClass = "stock"
    start: date
    end: date
    timeframe: str = "1d"
    rules: list[StrategyRule] | None = None  # None → engine default rules
    stop_loss_pct: float = Field(default=1.0, ge=0.1, le=20.0)
    take_profit_pct: float = Field(default=2.0, ge=0.1, le=50.0)
    starting_equity: float = Field(default=100_000.0, ge=1_000.0)
    # Fraction of equity allocated per trade (e.g. 0.05 = 5%)
    position_size_pct: float = Field(default=5.0, ge=0.5, le=100.0)
    # Minimum signal score to enter (0–1); 0.5 = half the rules must fire
    min_signal_score: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _dates_valid(self) -> "BacktestRequest":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class BacktestTrade(BaseModel):
    """One simulated round-trip trade."""
    entry_date: str        # ISO date string
    exit_date: str | None
    entry_price: float
    exit_price: float | None
    side: str
    quantity: float
    stop_loss_price: float
    take_profit_price: float
    realized_pnl: float | None
    status: str            # "took_profit" | "stopped_out" | "closed" | "open"
    fired_rules: list[str]
    # datetime versions used by analytics functions
    opened_at: datetime
    closed_at: datetime | None


class BacktestMetrics(BaseModel):
    total_trades: int
    win_rate: float
    sharpe: float
    max_drawdown: float
    avg_win: float
    avg_loss: float
    ratio: float
    total_pnl: float
    starting_equity: float
    ending_equity: float


class BacktestResult(BaseModel):
    symbol: str
    asset_class: str
    start: str
    end: str
    timeframe: str
    total_bars: int
    trades: list[BacktestTrade]
    metrics: BacktestMetrics
    equity_curve: list[float]
