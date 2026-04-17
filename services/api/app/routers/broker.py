from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.broker.alpaca import AlpacaBroker
from app.config import get_settings
from app.market_data.schemas import AssetClass

router = APIRouter(prefix="/broker", tags=["broker"])


def _get_broker() -> AlpacaBroker:
    settings = get_settings()
    if not settings.alpaca_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Alpaca not configured",
        )
    return AlpacaBroker(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        base_url=settings.alpaca_base_url,
    )


class MarketOrderBody(BaseModel):
    symbol: str
    side: str
    qty: float
    asset_class: AssetClass = "stock"


@router.get("/account")
def get_account() -> dict:
    return _get_broker().get_account()


@router.get("/positions")
def get_positions() -> list[dict]:
    return _get_broker().get_positions()


@router.get("/orders")
def get_orders(order_status: str = Query(default="open", alias="status")) -> list[dict]:
    return _get_broker().get_orders(status=order_status)


@router.post("/orders/market")
def place_market_order(body: MarketOrderBody) -> dict:
    return _get_broker().place_market_order(
        symbol=body.symbol,
        side=body.side,
        qty=body.qty,
        asset_class=body.asset_class,
    )


@router.delete("/orders/{order_id}")
def cancel_order(order_id: str) -> dict:
    success = _get_broker().cancel_order(order_id)
    return {"canceled": success, "order_id": order_id}


@router.delete("/orders")
def cancel_all_orders() -> dict:
    count = _get_broker().cancel_all_orders()
    return {"canceled_count": count}


@router.delete("/positions/{symbol}")
def close_position(symbol: str) -> dict:
    return _get_broker().close_position(symbol)


@router.get("/portfolio/history")
def get_portfolio_history(
    period: str = Query(default="1D"),
    timeframe: str = Query(default="5Min"),
) -> dict:
    return _get_broker().get_portfolio_history(period=period, timeframe=timeframe)
