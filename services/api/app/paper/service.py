from app.market_data.providers.mock import MockMarketDataProvider
from app.models import PaperAccount, PaperOrder, PaperPosition

FEE_BPS = 10  # 0.10%
SLIPPAGE_BPS = 5  # 0.05%
provider = MockMarketDataProvider()


def mark_price(symbol: str) -> float:
    quote = provider.get_quote(symbol=symbol, asset_class="crypto")
    return quote.price


def execution_price(side: str, requested_price: float) -> float:
    factor = 1 + (SLIPPAGE_BPS / 10000) if side == "buy" else 1 - (SLIPPAGE_BPS / 10000)
    return round(requested_price * factor, 4)


def fee_for_notional(fill_price: float, quantity: float) -> float:
    notional = fill_price * quantity
    return round(notional * (FEE_BPS / 10000), 4)


def planned_fill_quantity(quantity: float) -> tuple[float, str]:
    if quantity > 1:
        return round(quantity * 0.5, 4), "partially_filled"
    return quantity, "filled"


def apply_fill(
    account: PaperAccount,
    position: PaperPosition | None,
    *,
    symbol: str,
    side: str,
    quantity: float,
    requested_price: float,
) -> tuple[PaperOrder, PaperPosition]:
    fill_price = execution_price(side, requested_price)
    filled_quantity, order_status = planned_fill_quantity(quantity)
    fee = fee_for_notional(fill_price, filled_quantity)
    notional = fill_price * filled_quantity

    if position is None:
        position = PaperPosition(user_id=account.user_id, symbol=symbol.upper(), quantity=0, avg_price=0, realized_pnl=0)

    if side == "buy":
        total_cost = notional + fee
        account.cash_balance -= total_cost
        new_qty = position.quantity + filled_quantity
        if new_qty > 0:
            position.avg_price = ((position.avg_price * position.quantity) + notional) / new_qty
        position.quantity = new_qty
    else:
        sell_qty = min(filled_quantity, position.quantity)
        proceeds = (fill_price * sell_qty) - fee
        account.cash_balance += proceeds
        realized = (fill_price - position.avg_price) * sell_qty
        position.realized_pnl += realized
        position.quantity -= sell_qty
        if position.quantity <= 0:
            position.quantity = 0
            position.avg_price = 0

    account.equity = account.cash_balance + (position.quantity * fill_price)

    order = PaperOrder(
        user_id=account.user_id,
        symbol=symbol.upper(),
        side=side,
        order_type="market",
        quantity=quantity,
        filled_quantity=filled_quantity,
        requested_price=requested_price,
        fill_price=fill_price,
        fee=fee,
        status=order_status,
        rejection_reason=None,
    )
    return order, position


def compute_equity(account: PaperAccount, positions: list[PaperPosition]) -> float:
    mark_value = 0.0
    for position in positions:
        if position.quantity <= 0:
            continue
        mark_value += mark_price(position.symbol) * position.quantity
    return round(account.cash_balance + mark_value, 4)
