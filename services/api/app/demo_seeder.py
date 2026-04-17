from datetime import datetime, timedelta

from sqlalchemy.orm import Session


def seed_initial_watchlist(db: Session) -> None:
    """Populates watchlist from env vars on first boot if table is empty."""
    from app.config import get_settings
    from app.models import WatchlistItem

    if db.query(WatchlistItem).count() > 0:
        return

    settings = get_settings()
    for sym in settings.watchlist_stocks.split(","):
        sym = sym.strip()
        if sym:
            db.add(WatchlistItem(symbol=sym, asset_class="stock", is_active=True))
    for sym in settings.watchlist_crypto.split(","):
        sym = sym.strip()
        if sym:
            db.add(WatchlistItem(symbol=sym, asset_class="crypto", is_active=True))
    db.commit()


def seed_demo_data(db: Session) -> None:
    """Seeds 19 realistic demo trades when DEMO_MODE=true. Idempotent."""
    from app.models import TradeJournal

    if db.query(TradeJournal).count() > 0:
        return

    now = datetime.utcnow()
    trades = [
        dict(symbol="AAPL", asset_class="stock", side="buy", entry_price=182.50, exit_price=185.90, qty=10, stop_loss=180.50, take_profit=186.50, status="took_profit", opened_at=now - timedelta(days=14), closed_at=now - timedelta(days=13)),
        dict(symbol="NVDA", asset_class="stock", side="buy", entry_price=465.00, exit_price=480.20, qty=5, stop_loss=455.00, take_profit=485.00, status="took_profit", opened_at=now - timedelta(days=13), closed_at=now - timedelta(days=12)),
        dict(symbol="TSLA", asset_class="stock", side="buy", entry_price=248.00, exit_price=243.50, qty=8, stop_loss=243.00, take_profit=258.00, status="stopped_out", opened_at=now - timedelta(days=12), closed_at=now - timedelta(days=12)),
        dict(symbol="SPY", asset_class="stock", side="buy", entry_price=447.80, exit_price=451.20, qty=15, stop_loss=443.00, take_profit=455.00, status="took_profit", opened_at=now - timedelta(days=11), closed_at=now - timedelta(days=10)),
        dict(symbol="QQQ", asset_class="stock", side="buy", entry_price=378.50, exit_price=373.80, qty=10, stop_loss=373.00, take_profit=388.00, status="stopped_out", opened_at=now - timedelta(days=10), closed_at=now - timedelta(days=10)),
        dict(symbol="AAPL", asset_class="stock", side="buy", entry_price=183.20, exit_price=187.60, qty=12, stop_loss=181.00, take_profit=188.00, status="took_profit", opened_at=now - timedelta(days=9), closed_at=now - timedelta(days=8)),
        dict(symbol="NVDA", asset_class="stock", side="buy", entry_price=471.00, exit_price=488.50, qty=4, stop_loss=461.00, take_profit=491.00, status="took_profit", opened_at=now - timedelta(days=8), closed_at=now - timedelta(days=7)),
        dict(symbol="TSLA", asset_class="stock", side="buy", entry_price=252.50, exit_price=261.80, qty=7, stop_loss=247.00, take_profit=263.00, status="took_profit", opened_at=now - timedelta(days=7), closed_at=now - timedelta(days=6)),
        dict(symbol="SPY", asset_class="stock", side="buy", entry_price=449.20, exit_price=444.50, qty=20, stop_loss=444.00, take_profit=458.00, status="stopped_out", opened_at=now - timedelta(days=6), closed_at=now - timedelta(days=6)),
        dict(symbol="QQQ", asset_class="stock", side="buy", entry_price=381.00, exit_price=389.40, qty=8, stop_loss=375.00, take_profit=391.00, status="took_profit", opened_at=now - timedelta(days=5), closed_at=now - timedelta(days=4)),
        dict(symbol="AAPL", asset_class="stock", side="buy", entry_price=186.40, exit_price=191.20, qty=10, stop_loss=184.00, take_profit=192.00, status="took_profit", opened_at=now - timedelta(days=4), closed_at=now - timedelta(days=3)),
        dict(symbol="NVDA", asset_class="stock", side="buy", entry_price=479.50, exit_price=474.00, qty=3, stop_loss=469.00, take_profit=499.00, status="stopped_out", opened_at=now - timedelta(days=3), closed_at=now - timedelta(days=3)),
        dict(symbol="BTC/USD", asset_class="crypto", side="buy", entry_price=42800.00, exit_price=44100.00, qty=0.1, stop_loss=42000.00, take_profit=45000.00, status="took_profit", opened_at=now - timedelta(days=13), closed_at=now - timedelta(days=12)),
        dict(symbol="ETH/USD", asset_class="crypto", side="buy", entry_price=2280.00, exit_price=2195.00, qty=0.8, stop_loss=2200.00, take_profit=2400.00, status="stopped_out", opened_at=now - timedelta(days=12), closed_at=now - timedelta(days=12)),
        dict(symbol="BTC/USD", asset_class="crypto", side="buy", entry_price=43500.00, exit_price=45200.00, qty=0.15, stop_loss=42700.00, take_profit=46000.00, status="took_profit", opened_at=now - timedelta(days=10), closed_at=now - timedelta(days=9)),
        dict(symbol="ETH/USD", asset_class="crypto", side="buy", entry_price=2310.00, exit_price=2390.00, qty=1.0, stop_loss=2250.00, take_profit=2420.00, status="took_profit", opened_at=now - timedelta(days=8), closed_at=now - timedelta(days=7)),
        dict(symbol="BTC/USD", asset_class="crypto", side="buy", entry_price=44100.00, exit_price=43250.00, qty=0.1, stop_loss=43200.00, take_profit=46000.00, status="stopped_out", opened_at=now - timedelta(days=6), closed_at=now - timedelta(days=6)),
        dict(symbol="ETH/USD", asset_class="crypto", side="buy", entry_price=2355.00, exit_price=2440.00, qty=0.5, stop_loss=2300.00, take_profit=2460.00, status="took_profit", opened_at=now - timedelta(days=4), closed_at=now - timedelta(days=3)),
        dict(symbol="BTC/USD", asset_class="crypto", side="buy", entry_price=44800.00, exit_price=46100.00, qty=0.2, stop_loss=44000.00, take_profit=47000.00, status="took_profit", opened_at=now - timedelta(days=2), closed_at=now - timedelta(days=1)),
    ]

    for idx, t in enumerate(trades, start=1):
        pnl = (t["exit_price"] - t["entry_price"]) * t["qty"]
        db.add(
            TradeJournal(
                user_id=1,
                symbol=t["symbol"],
                asset_class=t.get("asset_class", "stock"),
                entry_order_id=f"demo-entry-{idx}",
                exit_order_id=f"demo-exit-{idx}",
                side=t["side"],
                entry_price=t["entry_price"],
                exit_price=t["exit_price"],
                quantity=t["qty"],
                stop_loss_price=t["stop_loss"],
                take_profit_price=t["take_profit"],
                entry_signal_rules=["demo_seed"],
                realized_pnl=round(pnl, 2),
                status=t["status"],
                opened_at=t["opened_at"],
                closed_at=t["closed_at"],
            )
        )
    db.commit()
