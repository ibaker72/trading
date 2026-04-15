"""Pure analytics functions — no DB dependency, fully testable."""
from __future__ import annotations

import math
from datetime import date


# ---------------------------------------------------------------------------
# Type alias — any object with the TradeJournal fields we need
# ---------------------------------------------------------------------------

class _TradeLike:
    realized_pnl: float | None
    status: str
    opened_at: object
    closed_at: object | None


def compute_win_rate(trades: list) -> float:
    """Fraction of closed trades that were profitable."""
    closed = [t for t in trades if t.status in ("closed", "stopped_out", "took_profit") and t.realized_pnl is not None]
    if not closed:
        return 0.0
    winners = [t for t in closed if t.realized_pnl > 0]
    return round(len(winners) / len(closed), 4)


def compute_sharpe(trades: list, risk_free_rate: float = 0.0) -> float:
    """
    Annualised Sharpe ratio based on per-trade P&L.
    Treats each closed trade as one 'period'.
    Returns 0.0 when there is insufficient data.
    """
    pnls = [t.realized_pnl for t in trades if t.realized_pnl is not None]
    if len(pnls) < 2:
        return 0.0

    n = len(pnls)
    mean = sum(pnls) / n
    variance = sum((p - mean) ** 2 for p in pnls) / (n - 1)
    std = math.sqrt(variance)

    if std == 0:
        return 0.0

    # Annualise assuming ~252 trading days, one trade per day on average
    excess = mean - risk_free_rate
    return round((excess / std) * math.sqrt(252), 4)


def compute_max_drawdown(equity_curve: list[float]) -> float:
    """
    Maximum peak-to-trough drawdown as a positive fraction (e.g. 0.15 = 15%).
    Returns 0.0 for empty / single-element curves.
    """
    if len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve[1:]:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd

    return round(max_dd, 6)


def compute_avg_win_loss(trades: list) -> dict:
    """
    Returns avg_win, avg_loss (absolute), and win/loss ratio.
    avg_loss is returned as a positive number for readability.
    """
    closed = [t for t in trades if t.realized_pnl is not None and t.status in ("closed", "stopped_out", "took_profit")]
    wins = [t.realized_pnl for t in closed if t.realized_pnl > 0]
    losses = [abs(t.realized_pnl) for t in closed if t.realized_pnl <= 0]

    avg_win = round(sum(wins) / len(wins), 4) if wins else 0.0
    avg_loss = round(sum(losses) / len(losses), 4) if losses else 0.0
    ratio = round(avg_win / avg_loss, 4) if avg_loss > 0 else 0.0

    return {"avg_win": avg_win, "avg_loss": avg_loss, "ratio": ratio}


def compute_pnl_series(trades: list) -> list[dict]:
    """
    Returns a list of {date, pnl, cumulative_pnl} sorted by close date.
    Only includes closed trades with a realized_pnl.
    """
    closed = [
        t for t in trades
        if t.realized_pnl is not None
        and t.closed_at is not None
        and t.status in ("closed", "stopped_out", "took_profit")
    ]
    closed.sort(key=lambda t: t.closed_at)

    series: list[dict] = []
    cumulative = 0.0
    for t in closed:
        cumulative += t.realized_pnl
        closed_date = t.closed_at.date() if hasattr(t.closed_at, "date") else str(t.closed_at)
        series.append({
            "date": str(closed_date),
            "pnl": round(t.realized_pnl, 4),
            "cumulative_pnl": round(cumulative, 4),
        })

    return series


def build_equity_curve(trades: list, starting_equity: float = 100_000.0) -> list[float]:
    """Build a simple equity curve from closed trade P&L for drawdown calculation."""
    pnl_series = compute_pnl_series(trades)
    equity = starting_equity
    curve = [equity]
    for item in pnl_series:
        equity += item["pnl"]
        curve.append(equity)
    return curve
