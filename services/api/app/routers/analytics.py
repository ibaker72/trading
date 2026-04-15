from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.analytics.service import (
    build_equity_curve,
    compute_avg_win_loss,
    compute_max_drawdown,
    compute_pnl_series,
    compute_sharpe,
    compute_win_rate,
)
from app.database import get_db
from app.models import TradeJournal

router = APIRouter(prefix="/analytics", tags=["analytics"])

_BOT_USER_ID = 1


class TradeJournalRead(BaseModel):
    id: int
    symbol: str
    asset_class: str
    side: str
    entry_price: float
    exit_price: float | None
    quantity: float
    stop_loss_price: float
    take_profit_price: float
    entry_signal_rules: list
    realized_pnl: float | None
    status: str
    opened_at: datetime
    closed_at: datetime | None

    class Config:
        from_attributes = True


class PerformanceRead(BaseModel):
    win_rate: float
    sharpe: float
    max_drawdown: float
    avg_win: float
    avg_loss: float
    ratio: float
    total_trades: int
    open_trades: int


class PnlPoint(BaseModel):
    date: str
    pnl: float
    cumulative_pnl: float


@router.get("/performance", response_model=PerformanceRead)
def get_performance(db: Session = Depends(get_db)) -> PerformanceRead:
    all_trades = (
        db.query(TradeJournal)
        .filter(TradeJournal.user_id == _BOT_USER_ID)
        .all()
    )
    win_loss = compute_avg_win_loss(all_trades)
    equity_curve = build_equity_curve(all_trades)
    open_count = sum(1 for t in all_trades if t.status == "open")

    return PerformanceRead(
        win_rate=compute_win_rate(all_trades),
        sharpe=compute_sharpe(all_trades),
        max_drawdown=compute_max_drawdown(equity_curve),
        avg_win=win_loss["avg_win"],
        avg_loss=win_loss["avg_loss"],
        ratio=win_loss["ratio"],
        total_trades=len(all_trades),
        open_trades=open_count,
    )


@router.get("/trades", response_model=list[TradeJournalRead])
def get_trades(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[TradeJournal]:
    query = db.query(TradeJournal).filter(TradeJournal.user_id == _BOT_USER_ID)
    if status:
        query = query.filter(TradeJournal.status == status)
    return query.order_by(TradeJournal.opened_at.desc()).limit(limit).all()


@router.get("/pnl-series", response_model=list[PnlPoint])
def get_pnl_series(db: Session = Depends(get_db)) -> list[dict]:
    trades = (
        db.query(TradeJournal)
        .filter(TradeJournal.user_id == _BOT_USER_ID)
        .all()
    )
    return compute_pnl_series(trades)
