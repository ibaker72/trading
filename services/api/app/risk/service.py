from app.risk.schemas import OrderIntent, PositionSizingResult, RiskDecision


def evaluate_order_intent(
    intent: OrderIntent,
    *,
    has_policy: bool,
    is_kill_switch_on: bool,
    live_trading_enabled: bool,
    allowed_symbols: list[str],
    max_risk_per_trade_pct: float,
    max_daily_loss: float,
    max_open_positions: int,
    consecutive_loss_limit: int,
) -> RiskDecision:
    reason_codes: list[str] = []

    if not has_policy:
        return RiskDecision(approved=False, reason_codes=["POLICY_MISSING"])

    if is_kill_switch_on:
        return RiskDecision(approved=False, reason_codes=["KILL_SWITCH_ON"])

    if not live_trading_enabled:
        reason_codes.append("LIVE_TRADING_DISABLED")

    if allowed_symbols and intent.symbol.upper() not in {symbol.upper() for symbol in allowed_symbols}:
        reason_codes.append("SYMBOL_NOT_ALLOWED")

    if intent.daily_pnl <= -abs(max_daily_loss):
        reason_codes.append("DAILY_LOSS_LIMIT_REACHED")

    if intent.open_positions >= max_open_positions:
        reason_codes.append("MAX_OPEN_POSITIONS_REACHED")

    if intent.consecutive_losses_today >= consecutive_loss_limit:
        reason_codes.append("CONSECUTIVE_LOSS_LIMIT_REACHED")

    sizing = suggest_position_size(
        account_equity=intent.account_equity,
        entry_price=intent.entry_price,
        stop_price=intent.stop_price,
        max_risk_per_trade_pct=max_risk_per_trade_pct,
    )

    if sizing.suggested_quantity < 1:
        reason_codes.append("POSITION_SIZE_TOO_SMALL")

    approved = len(reason_codes) == 0
    return RiskDecision(approved=approved, reason_codes=reason_codes, position_sizing=sizing)


def suggest_position_size(
    *,
    account_equity: float,
    entry_price: float,
    stop_price: float,
    max_risk_per_trade_pct: float,
) -> PositionSizingResult:
    risk_amount = account_equity * (max_risk_per_trade_pct / 100)
    risk_per_unit = abs(entry_price - stop_price)
    if risk_per_unit == 0:
        return PositionSizingResult(risk_amount=risk_amount, risk_per_unit=0.0, suggested_quantity=0)

    qty = int(risk_amount // risk_per_unit)
    return PositionSizingResult(
        risk_amount=round(risk_amount, 2),
        risk_per_unit=round(risk_per_unit, 4),
        suggested_quantity=max(0, qty),
    )
