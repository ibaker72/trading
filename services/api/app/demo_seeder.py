"""Seeds the database with realistic demo data for pitch demonstrations."""

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import BotSession, TradeJournal, WatchlistItem


_DEMO_STOCKS = ["AAPL", "NVDA", "TSLA", "SPY", "QQQ", "MSFT", "AMD"]
_DEMO_CRYPTO = ["BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD", "AVAX/USD", "DOGE/USD"]

_DEMO_TRADES = [
    # Profitable trades (winning ~65%)
    ("NVDA", "stock", 487.50, 497.25, 482.80, 499.75, "took_profit", 0.97),
    ("BTC/USD", "crypto", 43250.0, 44100.0, 42800.0, 44500.0, "took_profit", 0.83),
    ("AAPL", "stock", 189.20, 191.85, 187.50, 193.00, "took_profit", 1.10),
    ("ETH/USD", "crypto", 2310.0, 2356.2, 2287.0, 2380.0, "took_profit", 0.92),
    ("TSLA", "stock", 248.60, 253.55, 246.00, 256.00, "took_profit", 1.23),
    ("SPY", "stock", 471.30, 474.01, 469.10, 475.80, "took_profit", 0.57),
    ("NVDA", "stock", 501.10, 511.12, 496.00, 516.00, "took_profit", 2.00),
    ("BTC/USD", "crypto", 44800.0, 45700.0, 44300.0, 46000.0, "took_profit", 2.01),
    ("SOL/USD", "crypto", 98.50, 100.48, 97.50, 101.50, "took_profit", 0.98),
    ("AMD", "stock", 162.40, 165.65, 160.50, 167.00, "took_profit", 1.62),
    ("AAPL", "stock", 192.10, 194.88, 190.00, 196.00, "took_profit", 1.37),
    ("ETH/USD", "crypto", 2380.0, 2427.6, 2355.0, 2440.0, "took_profit", 1.18),
    ("QQQ", "stock", 399.80, 403.00, 397.50, 404.80, "took_profit", 0.80),
    # Losing trades (~35%)
    ("TSLA", "stock", 251.30, None, 247.80, 258.00, "stopped_out", -0.76),
    ("BTC/USD", "crypto", 45200.0, None, 44700.0, 46600.0, "stopped_out", -1.10),
    ("AMD", "stock", 166.20, None, 164.50, 170.80, "stopped_out", -0.84),
    ("ETH/USD", "crypto", 2450.0, None, 2425.5, 2523.5, "stopped_out", -0.60),
    ("NVDA", "stock", 512.00, None, 506.88, 527.36, "stopped_out", -1.28),
    ("SOL/USD", "crypto", 102.10, None, 101.07, 105.16, "stopped_out", -0.50),
]


def _random_past_dt(days_ago_max: int = 30, days_ago_min: int = 1) -> datetime:
    offset = random.uniform(days_ago_min, days_ago_max)
    return datetime.now(timezone.utc) - timedelta(days=offset, hours=random.uniform(0, 8))


def seed_demo_data(db: Session) -> None:
    """Seeds demo trades, watchlist, and bot session if DB looks empty."""
    existing_count = db.query(TradeJournal).count()
    if existing_count >= 5:
        return  # already seeded or real data present

    rng = random.Random(42)

    for i, (symbol, asset_class, entry_px, exit_px_raw, sl, tp, st, qty_mult) in enumerate(_DEMO_TRADES):
        opened = _random_past_dt(days_ago_max=28, days_ago_min=i * 1.5 + 1)
        closed = opened + timedelta(hours=rng.uniform(1, 24)) if st != "open" else None

        if st == "took_profit":
            actual_exit = tp
            pnl = round((actual_exit - entry_px) * qty_mult * 10, 2)
        elif st == "stopped_out":
            actual_exit = sl
            pnl = round((actual_exit - entry_px) * qty_mult * 10, 2)
        else:
            actual_exit = None
            pnl = None

        trade = TradeJournal(
            user_id=1,
            symbol=symbol,
            asset_class=asset_class,
            entry_order_id=f"demo-entry-{i:04d}",
            exit_order_id=f"demo-exit-{i:04d}" if st != "open" else None,
            entry_price=entry_px,
            exit_price=actual_exit,
            quantity=round(qty_mult * 10, 4),
            side="buy",
            stop_loss_price=sl,
            take_profit_price=tp,
            entry_signal_rules=["ema_cross", "vwap_cross"] if rng.random() > 0.4 else ["rsi_threshold", "volume_spike"],
            realized_pnl=pnl,
            status=st,
            opened_at=opened,
            closed_at=closed,
        )
        db.add(trade)

    _seed_watchlist(db)
    _ensure_bot_session(db)
    db.commit()


def _seed_watchlist(db: Session) -> None:
    if db.query(WatchlistItem).count() > 0:
        return
    for sym in _DEMO_STOCKS:
        db.add(WatchlistItem(symbol=sym, asset_class="stock", is_active=True))
    for sym in _DEMO_CRYPTO:
        db.add(WatchlistItem(symbol=sym, asset_class="crypto", is_active=True))


def _ensure_bot_session(db: Session) -> None:
    session = db.query(BotSession).filter(BotSession.id == 1).first()
    if not session:
        session = BotSession(
            id=1,
            status="STOPPED",
            trades_today=3,
            errors_today=0,
        )
        db.add(session)
