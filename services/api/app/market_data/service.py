from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.market_data.providers.base import MarketDataProvider
from app.market_data.providers.mock import timeframe_to_timedelta
from app.market_data.schemas import AssetClass, DataQualityReport, MarketAsset, MarketCandle, MarketQuote
from app.models import Asset, Candle


class MarketDataService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def list_assets(self, asset_class: AssetClass | None = None) -> list[MarketAsset]:
        return self.provider.list_assets(asset_class=asset_class)

    def get_quote(self, symbol: str, asset_class: AssetClass) -> MarketQuote:
        return self.provider.get_quote(symbol=symbol, asset_class=asset_class)

    def get_candles(
        self,
        db: Session,
        symbol: str,
        asset_class: AssetClass,
        timeframe: str,
        limit: int,
    ) -> tuple[list[MarketCandle], DataQualityReport]:
        candles = self.provider.get_candles(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            limit=limit,
        )
        normalized = normalize_candles(candles)
        quality = build_quality_report(normalized, timeframe)
        self._upsert_assets_and_candles(db, normalized)
        return normalized, quality

    @staticmethod
    def _upsert_assets_and_candles(db: Session, candles: list[MarketCandle]) -> None:
        if not candles:
            return

        first = candles[0]
        symbol = first.symbol
        asset_class = first.asset_class

        asset = db.query(Asset).filter(Asset.symbol == symbol).first()
        if not asset:
            asset = Asset(symbol=symbol, name=symbol, asset_class=asset_class)
            db.add(asset)
            db.flush()

        for candle in candles:
            existing = (
                db.query(Candle)
                .filter(
                    Candle.asset_id == asset.id,
                    Candle.timeframe == candle.timeframe,
                    Candle.timestamp == candle.timestamp,
                )
                .first()
            )
            if existing:
                existing.open = candle.open
                existing.high = candle.high
                existing.low = candle.low
                existing.close = candle.close
                existing.volume = candle.volume
                existing.provider = candle.provider
            else:
                db.add(
                    Candle(
                        asset_id=asset.id,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        volume=candle.volume,
                        provider=candle.provider,
                    )
                )
        db.commit()


def normalize_candles(candles: list[MarketCandle]) -> list[MarketCandle]:
    ordered = sorted(candles, key=lambda candle: candle.timestamp)
    deduped: dict[datetime, MarketCandle] = {}

    for candle in ordered:
        deduped[candle.timestamp] = candle

    return list(deduped.values())


def build_quality_report(candles: list[MarketCandle], timeframe: str) -> DataQualityReport:
    step = timeframe_to_timedelta(timeframe)
    step_seconds = int(step.total_seconds())
    missing = 0

    for prev, curr in zip(candles, candles[1:]):
        delta_seconds = int((curr.timestamp - prev.timestamp).total_seconds())
        if delta_seconds > step_seconds:
            missing += (delta_seconds // step_seconds) - 1

    latest = candles[-1].timestamp if candles else datetime.fromtimestamp(0, UTC)
    is_stale = (datetime.now(UTC) - latest).total_seconds() > (step_seconds * 2)

    return DataQualityReport(
        expected_interval_seconds=step_seconds,
        missing_intervals=missing,
        is_stale=is_stale,
    )
