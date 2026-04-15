from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PaperAccountCreate(BaseModel):
    user_id: int
    starting_balance: float = Field(gt=0)


class PaperAccountRead(BaseModel):
    id: int
    user_id: int
    cash_balance: float
    equity: float
    created_at: datetime

    class Config:
        from_attributes = True


class PaperOrderCreate(BaseModel):
    user_id: int
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)


class PaperOrderRead(BaseModel):
    id: int
    user_id: int
    symbol: str
    side: str
    order_type: str
    quantity: float
    filled_quantity: float
    requested_price: float
    fill_price: float
    fee: float
    status: str
    rejection_reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class PaperPositionRead(BaseModel):
    id: int
    user_id: int
    symbol: str
    quantity: float
    avg_price: float
    realized_pnl: float
    updated_at: datetime

    class Config:
        from_attributes = True


class PaperPnlRead(BaseModel):
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float


class ReconcileResult(BaseModel):
    user_id: int
    computed_equity: float
    stored_equity: float
    drift: float
    corrected: bool
