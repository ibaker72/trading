"""
/backtest endpoints
  POST /backtest/run     → run a backtest, returns BacktestResult
  GET  /backtest/symbols → list symbols available from the configured watchlist
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.backtest.schemas import BacktestRequest, BacktestResult
from app.config import get_settings
from app.database import get_db
from app.models import WatchlistItem

router = APIRouter(prefix="/backtest", tags=["backtest"])


def _get_provider():
    """Return an AlpacaMarketDataProvider, or raise 503 if not configured."""
    settings = get_settings()
    if not settings.alpaca_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Alpaca API key not configured — backtesting requires live market data.",
        )
    from app.market_data.providers.alpaca import AlpacaMarketDataProvider
    return AlpacaMarketDataProvider(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        data_url=settings.alpaca_data_url,
        feed=settings.alpaca_feed,
    )


@router.post("/run", response_model=BacktestResult)
def run_backtest(request: BacktestRequest) -> BacktestResult:
    """
    Run a walk-forward backtest for *symbol* over the requested date range.

    Uses the existing signal evaluation engine — the same rules that drive
    the live bot — so results are directly comparable to live performance.
    """
    provider = _get_provider()

    from app.backtest.engine import BacktestEngine
    engine = BacktestEngine(provider=provider)

    try:
        return engine.run(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Market data fetch failed: {exc}",
        ) from exc


@router.get("/symbols")
def list_symbols(db: Session = Depends(get_db)) -> list[str]:
    items = db.query(WatchlistItem).filter(WatchlistItem.is_active == True).all()  # noqa: E712
    if items:
        return [i.symbol for i in items]

    settings = get_settings()
    stocks = [s.strip() for s in settings.watchlist_stocks.split(",") if s.strip()]
    crypto = [s.strip() for s in settings.watchlist_crypto.split(",") if s.strip()]
    return stocks + crypto
