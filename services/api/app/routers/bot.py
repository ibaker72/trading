import threading

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.bot import state as bot_state
from app.config import get_settings
from app.database import get_db
from app.models import PaperOrder

router = APIRouter(prefix="/bot", tags=["bot"])


def _state_as_dict() -> dict:
    s = bot_state.get_state()
    return {
        "status": s.status.value,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "last_scan_at": s.last_scan_at.isoformat() if s.last_scan_at else None,
        "last_signal_at": s.last_signal_at.isoformat() if s.last_signal_at else None,
        "trades_today": s.trades_today,
        "errors_today": s.errors_today,
        "last_error": s.last_error,
    }


@router.get("/status")
def get_status() -> dict:
    return _state_as_dict()


@router.post("/start")
def start_bot() -> dict:
    from app.bot.engine import TradingBotEngine
    from app.database import SessionLocal

    settings = get_settings()
    bot_state.set_status(bot_state.BotStatus.RUNNING)

    def _run():
        engine = TradingBotEngine(db_session_factory=SessionLocal, settings=settings)
        db = SessionLocal()
        try:
            engine.run_cycle(db)
        finally:
            db.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return {"started": True}


@router.post("/pause")
def pause_bot() -> dict:
    bot_state.set_status(bot_state.BotStatus.PAUSED)
    return {"paused": True}


@router.post("/stop")
def stop_bot() -> dict:
    bot_state.set_status(bot_state.BotStatus.STOPPED)
    bot_state._state.started_at = None
    return {"stopped": True}


@router.get("/history")
def get_history(limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)) -> list:
    orders = (
        db.query(PaperOrder)
        .filter(PaperOrder.user_id == 1)
        .order_by(PaperOrder.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": o.id,
            "symbol": o.symbol,
            "side": o.side,
            "quantity": o.quantity,
            "fill_price": o.fill_price,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


@router.get("/summary")
def get_summary() -> dict:
    s = bot_state.get_state()
    settings = get_settings()

    equity = None
    if settings.alpaca_enabled:
        try:
            from app.broker.alpaca import AlpacaBroker
            broker = AlpacaBroker(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
                base_url=settings.alpaca_base_url,
            )
            account = broker.get_account()
            equity = float(account.get("equity", 0))
        except Exception:
            equity = None

    return {
        "status": s.status.value,
        "trades_today": s.trades_today,
        "errors_today": s.errors_today,
        "last_scan_at": s.last_scan_at.isoformat() if s.last_scan_at else None,
        "last_signal_at": s.last_signal_at.isoformat() if s.last_signal_at else None,
        "equity": equity,
    }
