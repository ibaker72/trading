from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.schemas import AssetClass
from app.models import WatchlistItem
from app.strategy.scanner import WatchlistScanner
from app.strategy.schemas import MultiTimeframeScanResult, StrategyRule, WatchlistScanResult

router = APIRouter(prefix="/scanner", tags=["scanner"])

_DEFAULT_RULES: list[StrategyRule] = [
    StrategyRule(rule_type="ema_cross", params={"fast": 9, "slow": 21}),
    StrategyRule(rule_type="vwap_cross", params={}),
    StrategyRule(rule_type="rsi_threshold", params={"period": 14, "threshold": 50, "mode": "above"}),
    StrategyRule(rule_type="volume_spike", params={"lookback": 20, "multiplier": 1.5}),
]


def _get_scanner() -> WatchlistScanner:
    settings = get_settings()
    if settings.alpaca_api_key:
        try:
            from app.market_data.providers.alpaca import AlpacaMarketDataProvider
            provider = AlpacaMarketDataProvider(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
                data_url=settings.alpaca_data_url,
                feed=settings.alpaca_feed,
            )
        except Exception:
            provider = MockMarketDataProvider()
    else:
        provider = MockMarketDataProvider()
    return WatchlistScanner(provider=provider, rules=_DEFAULT_RULES)


def _get_watchlist_symbols(db: Session) -> tuple[list[str], list[str]]:
    items = db.query(WatchlistItem).filter(WatchlistItem.is_active == True).all()  # noqa: E712
    if items:
        stocks = [i.symbol for i in items if i.asset_class == "stock"]
        crypto = [i.symbol for i in items if i.asset_class == "crypto"]
        return stocks, crypto

    settings = get_settings()
    stocks = [s.strip() for s in settings.watchlist_stocks.split(",") if s.strip()]
    crypto = [s.strip() for s in settings.watchlist_crypto.split(",") if s.strip()]
    return stocks, crypto


def _build_watchlist(db: Session) -> list[tuple[str, AssetClass]]:
    stocks, crypto = _get_watchlist_symbols(db)
    return [(sym, "stock") for sym in stocks] + [(sym, "crypto") for sym in crypto]


@router.get("/watchlist", response_model=WatchlistScanResult)
def scan_watchlist(db: Session = Depends(get_db)) -> WatchlistScanResult:
    scanner = _get_scanner()
    watchlist = _build_watchlist(db)
    return scanner.scan_watchlist(watchlist)


@router.get("/symbol", response_model=MultiTimeframeScanResult)
def scan_symbol(
    symbol: str = Query(...),
    asset_class: AssetClass = Query(default="stock"),
) -> MultiTimeframeScanResult:
    scanner = _get_scanner()
    return scanner.scan_symbol(symbol, asset_class)


@router.get("/top-pick", response_model=MultiTimeframeScanResult)
def top_pick(db: Session = Depends(get_db)) -> MultiTimeframeScanResult:
    scanner = _get_scanner()
    watchlist = _build_watchlist(db)
    result = scanner.scan_watchlist(watchlist)
    if result.top_pick is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tradeable pick found")
    return result.top_pick
