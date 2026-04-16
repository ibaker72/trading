"""
Backtesting engine — replays historical candles through the existing
signal evaluation logic and simulates bracket-order fills.

Design:
  • Walks forward bar-by-bar using a sliding candle window.
  • When a signal fires (score ≥ min_signal_score), enters on the NEXT
    bar's open to avoid look-ahead bias.
  • Simulates SL/TP fills bar-by-bar: if bar.low ≤ SL → stopped_out;
    if bar.high ≥ TP → took_profit.  SL checked first (conservative).
  • Only one trade open at a time; after exit, skips to the bar after
    the exit bar before looking for the next signal.
  • Uses existing analytics functions (compute_win_rate, compute_sharpe,
    etc.) by feeding BacktestTrade objects, which carry opened_at /
    closed_at to satisfy the duck-typing interface.
"""
from __future__ import annotations

import logging
from datetime import date

from app.analytics.service import (
    build_equity_curve,
    compute_avg_win_loss,
    compute_max_drawdown,
    compute_sharpe,
    compute_win_rate,
)
from app.backtest.schemas import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResult,
    BacktestTrade,
)
from app.market_data.schemas import MarketCandle
from app.strategy.engine import evaluate_strategy
from app.strategy.schemas import StrategyRule

logger = logging.getLogger(__name__)

_DEFAULT_RULES: list[StrategyRule] = [
    StrategyRule(rule_type="ema_cross", params={"fast": 9, "slow": 21}),
    StrategyRule(rule_type="rsi_threshold", params={"period": 14, "threshold": 50, "mode": "above"}),
]

# Number of bars in the look-back window fed to evaluate_strategy
_WINDOW = 60


class BacktestEngine:
    def __init__(self, provider) -> None:
        """
        *provider* must implement ``get_historical_bars(symbol, asset_class,
        start, end, timeframe) -> list[MarketCandle]``.
        """
        self._provider = provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, request: BacktestRequest) -> BacktestResult:
        candles = self._provider.get_historical_bars(
            symbol=request.symbol,
            asset_class=request.asset_class,
            start=request.start,
            end=request.end,
            timeframe=request.timeframe,
        )

        if len(candles) < _WINDOW + 2:
            raise ValueError(
                f"Insufficient historical data: {len(candles)} bars returned "
                f"(need at least {_WINDOW + 2}).  Try a wider date range."
            )

        rules = request.rules or _DEFAULT_RULES
        sl_pct = request.stop_loss_pct / 100.0
        tp_pct = request.take_profit_pct / 100.0
        equity = request.starting_equity
        trades: list[BacktestTrade] = []

        i = _WINDOW  # first bar where we have a full look-back window

        while i < len(candles) - 1:
            window = candles[max(0, i - _WINDOW): i + 1]
            signal = evaluate_strategy(window, rules)

            if signal.score < request.min_signal_score:
                i += 1
                continue

            # ---- Enter on next bar's open --------------------------------
            entry_bar = candles[i + 1]
            entry_price = entry_bar.open
            if entry_price <= 0:
                i += 1
                continue

            qty = _calc_qty(equity, entry_price, request.position_size_pct / 100.0)
            sl_price = round(entry_price * (1 - sl_pct), 6)
            tp_price = round(entry_price * (1 + tp_pct), 6)

            # ---- Simulate exit by scanning subsequent bars ---------------
            exit_bar: MarketCandle | None = None
            exit_price: float | None = None
            exit_status = "open"

            for j in range(i + 2, len(candles)):
                bar = candles[j]
                # Conservative: check SL before TP (worst-case assumption)
                if bar.low <= sl_price:
                    exit_price = sl_price
                    exit_bar = bar
                    exit_status = "stopped_out"
                    break
                if bar.high >= tp_price:
                    exit_price = tp_price
                    exit_bar = bar
                    exit_status = "took_profit"
                    break

            # If neither SL nor TP hit before end of data, close at last bar
            if exit_bar is None and i + 2 < len(candles):
                exit_bar = candles[-1]
                exit_price = exit_bar.close
                exit_status = "closed"

            pnl: float | None = None
            if exit_price is not None:
                pnl = round((exit_price - entry_price) * qty, 4)
                equity = max(0.0, equity + pnl)

            trade = BacktestTrade(
                entry_date=entry_bar.timestamp.date().isoformat(),
                exit_date=exit_bar.timestamp.date().isoformat() if exit_bar else None,
                entry_price=entry_price,
                exit_price=exit_price,
                side="buy",
                quantity=round(qty, 4),
                stop_loss_price=sl_price,
                take_profit_price=tp_price,
                realized_pnl=pnl,
                status=exit_status,
                fired_rules=signal.fired_rules,
                opened_at=entry_bar.timestamp,
                closed_at=exit_bar.timestamp if exit_bar else None,
            )
            trades.append(trade)

            # Advance past the exit bar so we don't overlap trades
            if exit_bar is not None:
                try:
                    exit_idx = candles.index(exit_bar)
                    i = exit_idx + 1
                except ValueError:
                    i += 2
            else:
                i += 2

        metrics = _build_metrics(trades, request.starting_equity, equity)
        eq_curve = build_equity_curve(trades, request.starting_equity)

        return BacktestResult(
            symbol=request.symbol.upper(),
            asset_class=request.asset_class,
            start=request.start.isoformat(),
            end=request.end.isoformat(),
            timeframe=request.timeframe,
            total_bars=len(candles),
            trades=trades,
            metrics=metrics,
            equity_curve=eq_curve,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calc_qty(equity: float, entry_price: float, fraction: float) -> float:
    """Position size = fraction × equity / entry_price, minimum 0.01."""
    if entry_price <= 0 or equity <= 0:
        return 1.0
    qty = (equity * fraction) / entry_price
    return max(0.01, round(qty, 4))


def _build_metrics(
    trades: list[BacktestTrade],
    starting_equity: float,
    ending_equity: float,
) -> BacktestMetrics:
    win_rate = compute_win_rate(trades)
    sharpe = compute_sharpe(trades)
    avg_wl = compute_avg_win_loss(trades)
    eq_curve = build_equity_curve(trades, starting_equity)
    max_dd = compute_max_drawdown(eq_curve)
    closed = [t for t in trades if t.realized_pnl is not None]
    total_pnl = round(sum(t.realized_pnl for t in closed), 4)  # type: ignore[arg-type]

    return BacktestMetrics(
        total_trades=len(trades),
        win_rate=win_rate,
        sharpe=sharpe,
        max_drawdown=max_dd,
        avg_win=avg_wl["avg_win"],
        avg_loss=avg_wl["avg_loss"],
        ratio=avg_wl["ratio"],
        total_pnl=total_pnl,
        starting_equity=starting_equity,
        ending_equity=round(ending_equity, 2),
    )
