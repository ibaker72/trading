from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.market_data.providers.mock import MockMarketDataProvider
from app.models import Signal, Strategy
from app.strategy.engine import evaluate_strategy
from app.strategy.schemas import ScanResult, SignalRead, StrategyCreate, StrategyRead, StrategyRule

router = APIRouter(prefix="/strategies", tags=["strategies"])
provider = MockMarketDataProvider()


@router.post("", response_model=StrategyRead, status_code=status.HTTP_201_CREATED)
def create_strategy(payload: StrategyCreate, db: Session = Depends(get_db)) -> Strategy:
    strategy = Strategy(
        name=payload.name,
        symbol=payload.symbol.upper(),
        asset_class=payload.asset_class,
        timeframe=payload.timeframe,
        cooldown_minutes=payload.cooldown_minutes,
        rules=[rule.model_dump() for rule in payload.rules],
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return strategy


@router.get("", response_model=list[StrategyRead])
def list_strategies(db: Session = Depends(get_db)) -> list[Strategy]:
    return db.query(Strategy).order_by(Strategy.created_at.desc()).all()


@router.post("/{strategy_id}/scan", response_model=ScanResult)
def scan_strategy(strategy_id: int, db: Session = Depends(get_db)) -> ScanResult:
    strategy = db.query(Strategy).filter(Strategy.id == strategy_id, Strategy.is_active.is_(True)).first()
    if not strategy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")

    latest_signal = (
        db.query(Signal)
        .filter(Signal.strategy_id == strategy.id)
        .order_by(Signal.triggered_at.desc())
        .first()
    )

    now = datetime.now(UTC)
    now_naive = now.replace(tzinfo=None)
    latest_triggered_at = latest_signal.triggered_at if latest_signal else None
    if latest_triggered_at and latest_triggered_at.tzinfo is not None:
        latest_triggered_at = latest_triggered_at.astimezone(UTC).replace(tzinfo=None)

    if latest_triggered_at and latest_triggered_at >= now_naive - timedelta(minutes=strategy.cooldown_minutes):
        return ScanResult(generated=False, reason="Cooldown active")

    candles = provider.get_candles(
        symbol=strategy.symbol,
        asset_class=strategy.asset_class,
        timeframe=strategy.timeframe,
        limit=200,
    )
    rules = [StrategyRule(**rule) for rule in strategy.rules]
    result = evaluate_strategy(candles=candles, rules=rules)

    if not result.should_signal:
        return ScanResult(generated=False, reason="No qualifying signal")

    signal = Signal(
        strategy_id=strategy.id,
        symbol=strategy.symbol,
        timeframe=strategy.timeframe,
        signal_type="entry",
        score=result.score,
        explanation=f"Rules fired: {', '.join(result.fired_rules)}",
        triggered_at=now,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return ScanResult(generated=True, reason="Signal generated", signal=SignalRead.model_validate(signal))


@router.get("/signals", response_model=list[SignalRead])
def list_signals(
    strategy_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Signal]:
    query = db.query(Signal)
    if strategy_id is not None:
        query = query.filter(Signal.strategy_id == strategy_id)
    return query.order_by(Signal.triggered_at.desc()).limit(200).all()
