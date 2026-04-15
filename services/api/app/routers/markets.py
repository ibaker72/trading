from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.schemas import AssetClass, DataQualityReport, MarketAsset, MarketCandle, MarketQuote
from app.market_data.service import MarketDataService

router = APIRouter(prefix="/markets", tags=["markets"])
provider = MockMarketDataProvider()
service = MarketDataService(provider=provider)


@router.get("/assets", response_model=list[MarketAsset])
def list_assets(
    asset_class: AssetClass | None = Query(default=None),
) -> list[MarketAsset]:
    return service.list_assets(asset_class=asset_class)


@router.get("/quote", response_model=MarketQuote)
def quote(symbol: str, asset_class: AssetClass) -> MarketQuote:
    return service.get_quote(symbol=symbol, asset_class=asset_class)


@router.get("/candles", response_model=list[MarketCandle])
def candles(
    symbol: str,
    asset_class: AssetClass,
    timeframe: str = Query(default="1h"),
    limit: int = Query(default=100, ge=10, le=1000),
    db: Session = Depends(get_db),
) -> list[MarketCandle]:
    result, _ = service.get_candles(
        db=db,
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        limit=limit,
    )
    return result


@router.get("/candles/quality", response_model=DataQualityReport)
def candles_quality(
    symbol: str,
    asset_class: AssetClass,
    timeframe: str = Query(default="1h"),
    limit: int = Query(default=100, ge=10, le=1000),
    db: Session = Depends(get_db),
) -> DataQualityReport:
    _, quality = service.get_candles(
        db=db,
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        limit=limit,
    )
    return quality
