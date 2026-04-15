from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.bot import state as bot_state
from app.models import TradeJournal

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Reconciles open TradeJournal entries against filled Alpaca exit orders."""

    def __init__(self, broker) -> None:
        self._broker = broker

    def check_exits(self, db: Session) -> int:
        """
        Query Alpaca for closed orders and match them to open TradeJournal rows.
        Returns the number of exits reconciled.
        """
        if self._broker is None:
            return 0

        try:
            closed_orders = self._broker.get_orders(status="closed")
        except Exception as exc:
            logger.warning("PositionMonitor: failed to fetch closed orders: %s", exc)
            return 0

        if not closed_orders:
            return 0

        # Build lookup: exit_order_id → order data
        closed_by_id: dict[str, dict] = {o["id"]: o for o in closed_orders if isinstance(o, dict)}

        # Find all open journal entries
        open_entries: list[TradeJournal] = (
            db.query(TradeJournal)
            .filter(TradeJournal.status == "open")
            .all()
        )

        reconciled = 0
        for entry in open_entries:
            # Check if the broker has a matching exit order for this symbol
            exit_order = _find_exit_order(entry, closed_orders)
            if exit_order is None:
                continue

            fill_price = _parse_fill_price(exit_order)
            if fill_price is None:
                continue

            # Determine exit reason
            order_type = exit_order.get("type", "")
            if order_type == "stop":
                new_status = "stopped_out"
            elif order_type == "limit":
                new_status = "took_profit"
            else:
                new_status = "closed"

            # Compute realized P&L (buy entry = exit_price - entry_price per share)
            if entry.side == "buy":
                pnl = (fill_price - entry.entry_price) * entry.quantity
            else:
                pnl = (entry.entry_price - fill_price) * entry.quantity

            entry.exit_order_id = exit_order["id"]
            entry.exit_price = fill_price
            entry.realized_pnl = round(pnl, 4)
            entry.status = new_status
            entry.closed_at = datetime.now(UTC)

            bot_state.record_trade()
            reconciled += 1
            logger.info(
                "Exit reconciled: %s %s pnl=%.2f status=%s",
                entry.symbol,
                entry.side,
                pnl,
                new_status,
            )

        if reconciled:
            db.commit()

        return reconciled


def _find_exit_order(entry: TradeJournal, closed_orders: list[dict]) -> dict | None:
    """Find a closed exit order matching the journal entry's symbol and opposite side."""
    exit_side = "sell" if entry.side == "buy" else "buy"
    for order in closed_orders:
        if (
            order.get("symbol", "").upper() == entry.symbol.upper()
            and order.get("side", "") == exit_side
            and order.get("status") in ("filled", "closed")
        ):
            return order
    return None


def _parse_fill_price(order: dict) -> float | None:
    """Extract fill price from an Alpaca order dict."""
    for key in ("filled_avg_price", "filled_avg_price_usd", "limit_price", "stop_price"):
        val = order.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None
