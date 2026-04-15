from datetime import datetime

from pydantic import BaseModel, Field


class RiskPolicyCreate(BaseModel):
    user_id: int
    max_risk_per_trade_pct: float = Field(gt=0, le=10)
    max_daily_loss: float = Field(gt=0)
    max_open_positions: int = Field(gt=0, le=100)
    consecutive_loss_limit: int = Field(default=3, ge=1, le=20)
    allowed_symbols: list[str] = Field(default_factory=list)
    live_trading_enabled: bool = False


class RiskPolicyRead(BaseModel):
    id: int
    user_id: int
    max_risk_per_trade_pct: float
    max_daily_loss: float
    max_open_positions: int
    consecutive_loss_limit: int
    allowed_symbols: list[str]
    live_trading_enabled: bool
    is_kill_switch_on: bool
    created_at: datetime

    class Config:
        from_attributes = True


class OrderIntent(BaseModel):
    user_id: int
    symbol: str
    account_equity: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    daily_pnl: float
    open_positions: int = Field(ge=0)
    consecutive_losses_today: int = Field(ge=0)


class PositionSizingResult(BaseModel):
    risk_amount: float
    risk_per_unit: float
    suggested_quantity: int


class RiskDecision(BaseModel):
    approved: bool
    reason_codes: list[str]
    position_sizing: PositionSizingResult | None = None


class KillSwitchUpdate(BaseModel):
    enabled: bool


class RiskEventRead(BaseModel):
    id: int
    user_id: int
    symbol: str
    approved: bool
    reason_codes: list[str]
    created_at: datetime

    class Config:
        from_attributes = True
