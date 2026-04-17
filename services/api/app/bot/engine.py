from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.bot import state as bot_state
from app.market_data.schemas import AssetClass
from app.models import GlobalControl, PaperAccount, PaperOrder, RiskPolicy, TradeJournal, User
from app.risk.schemas import OrderIntent
from app.risk.service import evaluate_order_intent
from app.strategy.schemas import StrategyRule

logger = logging.getLogger(__name__)

_DEFAULT_RULES: list[StrategyRule] = [
    StrategyRule(rule_type="ema_cross", params={"fast": 9, "slow": 21}),
    StrategyRule(rule_type="vwap_cross", params={}),
    StrategyRule(rule_type="rsi_threshold", params={"period": 14, "threshold": 50, "mode": "above"}),
    StrategyRule(rule_type="volume_spike", params={"lookback": 20, "multiplier": 1.5}),
]


class TradingBotEngine:
    def __init__(self, db_session_factory, settings) -> None:
        self._session_factory = db_session_factory
        self._settings = settings
        self._broker = None
        self._scanner = None
        self._init_components()

    def _init_components(self) -> None:
        from app.strategy.scanner import WatchlistScanner

        if self._settings.alpaca_enabled:
            try:
                from app.broker.alpaca import AlpacaBroker
                from app.market_data.providers.alpaca import AlpacaMarketDataProvider

                self._broker = AlpacaBroker(
                    api_key=self._settings.alpaca_api_key,
                    secret_key=self._settings.alpaca_secret_key,
                    base_url=self._settings.alpaca_base_url,
                )
                provider = AlpacaMarketDataProvider(
                    api_key=self._settings.alpaca_api_key,
                    secret_key=self._settings.alpaca_secret_key,
                    data_url=self._settings.alpaca_data_url,
                    feed=self._settings.alpaca_feed,
                )
            except Exception as exc:
                logger.warning("Failed to init Alpaca components: %s — falling back to mock", exc)
                from app.market_data.providers.mock import MockMarketDataProvider
                provider = MockMarketDataProvider()
        else:
            logger.warning("Alpaca disabled — running in mock mode, orders will not be placed")
            from app.market_data.providers.mock import MockMarketDataProvider
            provider = MockMarketDataProvider()

        self._scanner = WatchlistScanner(provider=provider, rules=_DEFAULT_RULES)

    def _build_watchlist(self) -> list[tuple[str, AssetClass]]:
        pairs: list[tuple[str, AssetClass]] = []
        for sym in self._settings.watchlist_stocks.split(","):
            sym = sym.strip()
            if sym:
                pairs.append((sym, "stock"))
        for sym in self._settings.watchlist_crypto.split(","):
            sym = sym.strip()
            if sym:
                pairs.append((sym, "crypto"))
        return pairs

    def _ensure_bot_user(self, db: Session) -> User:
        user = db.query(User).filter(User.id == 1).first()
        if user:
            return user

        from app.security import get_password_hash
        password = secrets.token_urlsafe(16)
        user = User(
            id=1,
            email="bot@trading.local",
            full_name="Trading Bot",
            password_hash=get_password_hash(password),
            role="trader",
        )
        db.add(user)
        db.flush()

        policy = RiskPolicy(
            user_id=1,
            max_risk_per_trade_pct=1.0,
            max_daily_loss=500.0,
            max_open_positions=10,
            consecutive_loss_limit=3,
            allowed_symbols=[],
            live_trading_enabled=True,
        )
        db.add(policy)

        account = PaperAccount(user_id=1, cash_balance=100000.0, equity=100000.0)
        db.add(account)

        db.commit()
        db.refresh(user)
        return user

    def run_cycle(self, db: Session) -> dict:
        summary = {"scanned": 0, "signals_found": 0, "orders_placed": 0, "errors": 0}

        try:
            # a. Check global kill switch
            control = db.query(GlobalControl).filter(GlobalControl.key == "global_kill_switch").first()
            if control and control.value == "on":
                logger.info("Global kill switch is ON — skipping cycle")
                return summary

            # b. Check bot status
            current_status = bot_state.get_state().status
            if current_status != bot_state.BotStatus.RUNNING:
                return summary

            # c. Reconcile exits from previous entries
            if self._broker:
                try:
                    from app.bot.monitor import PositionMonitor
                    from app.notifications.service import build_from_db as _build_notif
                    monitor = PositionMonitor(broker=self._broker)
                    notif_svc = _build_notif(db)
                    exited = monitor.check_exits(db, notif_svc=notif_svc)
                    if exited:
                        logger.info("Reconciled %d exit(s) this cycle", exited)
                except Exception as exc:
                    logger.warning("Exit reconciliation error: %s", exc)

            # d. Scan watchlist
            watchlist = self._build_watchlist()
            scan_result = self._scanner.scan_watchlist(watchlist)
            bot_state.record_scan()
            summary["scanned"] = len(scan_result.results)

            # e. Process signals
            user = self._ensure_bot_user(db)
            policy = db.query(RiskPolicy).filter(RiskPolicy.user_id == user.id).first()

            sl_pct = getattr(self._settings, "stop_loss_pct", 1.0) / 100.0
            tp_pct = getattr(self._settings, "take_profit_pct", 2.0) / 100.0

            for result in scan_result.results:
                if not result.should_trade or result.suggested_side == "none":
                    continue

                summary["signals_found"] += 1
                bot_state.record_signal()

                if not self._broker:
                    logger.warning("No broker configured — skipping order for %s", result.symbol)
                    continue

                # Get account equity
                try:
                    account_data = self._broker.get_account()
                    equity = float(account_data.get("equity", 100000.0))
                except Exception as exc:
                    logger.warning("Failed to get account equity: %s", exc)
                    equity = 100000.0

                # Risk check
                entry_price_proxy = equity * 0.01
                intent = OrderIntent(
                    user_id=user.id,
                    symbol=result.symbol,
                    account_equity=equity,
                    entry_price=max(entry_price_proxy, 1.0),
                    stop_price=max(entry_price_proxy * (1 - sl_pct), 0.01),
                    daily_pnl=0.0,
                    open_positions=0,
                    consecutive_losses_today=0,
                )

                if policy:
                    decision = evaluate_order_intent(
                        intent,
                        has_policy=True,
                        is_kill_switch_on=policy.is_kill_switch_on,
                        live_trading_enabled=policy.live_trading_enabled,
                        allowed_symbols=policy.allowed_symbols,
                        max_risk_per_trade_pct=policy.max_risk_per_trade_pct,
                        max_daily_loss=policy.max_daily_loss,
                        max_open_positions=policy.max_open_positions,
                        consecutive_loss_limit=policy.consecutive_loss_limit,
                    )
                    if not decision.approved:
                        logger.info("Order for %s rejected: %s", result.symbol, decision.reason_codes)
                        continue
                    qty = decision.position_sizing.suggested_quantity if decision.position_sizing else 1
                else:
                    qty = 1

                qty = max(qty, 1)

                # Place bracket order (entry + SL + TP in one shot)
                try:
                    # We need an approximate price for SL/TP. Use a fresh quote if possible.
                    approx_price = _estimate_price(self._broker, result.symbol, result.asset_class)

                    if result.suggested_side == "buy":
                        sl_price = round(approx_price * (1 - sl_pct), 4)
                        tp_price = round(approx_price * (1 + tp_pct), 4)
                    else:
                        sl_price = round(approx_price * (1 + sl_pct), 4)
                        tp_price = round(approx_price * (1 - tp_pct), 4)

                    order_resp = self._broker.place_bracket_order(
                        symbol=result.symbol,
                        side=result.suggested_side,
                        qty=qty,
                        take_profit_price=tp_price,
                        stop_loss_price=sl_price,
                        asset_class=result.asset_class,
                    )

                    fill_price = float(order_resp.get("filled_avg_price") or approx_price)
                    order_id = order_resp.get("id", "unknown")

                    # Send trade-entered notification (fire-and-forget)
                    try:
                        from app.notifications.service import build_from_db as _build_notif
                        _build_notif(db).trade_entered(
                            symbol=result.symbol,
                            side=result.suggested_side,
                            qty=float(qty),
                            price=fill_price,
                            sl=sl_price,
                            tp=tp_price,
                        )
                    except Exception:
                        pass

                    # Record paper order for history endpoint
                    order_record = PaperOrder(
                        user_id=user.id,
                        symbol=result.symbol.upper(),
                        side=result.suggested_side,
                        order_type="market",
                        quantity=float(qty),
                        filled_quantity=float(qty),
                        requested_price=fill_price,
                        fill_price=fill_price,
                        fee=0.0,
                        status="filled",
                    )
                    db.add(order_record)

                    # Record trade journal entry
                    journal = TradeJournal(
                        user_id=user.id,
                        symbol=result.symbol.upper(),
                        asset_class=result.asset_class,
                        entry_order_id=str(order_id),
                        entry_price=fill_price,
                        quantity=float(qty),
                        side=result.suggested_side,
                        stop_loss_price=sl_price,
                        take_profit_price=tp_price,
                        entry_signal_rules=result.fired_timeframes,
                        status="open",
                        opened_at=datetime.now(UTC),
                    )
                    db.add(journal)
                    db.commit()

                    bot_state.record_trade()
                    summary["orders_placed"] += 1
                    logger.info(
                        "Bracket order placed: %s %s qty=%s sl=%.4f tp=%.4f",
                        result.suggested_side, result.symbol, qty, sl_price, tp_price,
                    )

                except Exception as exc:
                    logger.error("Failed to place order for %s: %s", result.symbol, exc)
                    bot_state.record_error(str(exc))
                    summary["errors"] += 1
                    try:
                        from app.notifications.service import build_from_db as _build_notif
                        _build_notif(db).error_occurred(
                            f"Order placement failed for {result.symbol}: {exc}"
                        )
                    except Exception:
                        pass

        except Exception as exc:
            logger.error("Bot cycle error: %s", exc)
            bot_state.record_error(str(exc))
            summary["errors"] += 1
            try:
                from app.notifications.service import build_from_db as _build_notif
                _build_notif(db).error_occurred(f"Bot cycle error: {exc}")
            except Exception:
                pass

        return summary

    async def run_cycle_async(self) -> dict:
        """APScheduler-compatible async wrapper."""
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            return self.run_cycle(db)
        finally:
            db.close()


def _estimate_price(broker, symbol: str, asset_class: AssetClass) -> float:
    """Best-effort price estimate using positions or a fallback."""
    try:
        positions = broker.get_positions()
        for pos in positions:
            if pos.get("symbol", "").upper() == symbol.upper():
                return float(pos.get("current_price") or pos.get("avg_entry_price") or 1.0)
    except Exception:
        pass
    return 1.0
