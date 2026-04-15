from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GlobalControl, PaperAccount, PaperOrder, PaperPosition, RiskEvent, RiskPolicy, User
from app.paper.schemas import (
    PaperAccountCreate,
    PaperAccountRead,
    PaperOrderCreate,
    PaperOrderRead,
    PaperPnlRead,
    PaperPositionRead,
    ReconcileResult,
)
from app.paper.service import apply_fill, compute_equity, mark_price
from app.risk.schemas import OrderIntent
from app.risk.service import evaluate_order_intent

router = APIRouter(prefix="/paper", tags=["paper"])


@router.post("/accounts", response_model=PaperAccountRead, status_code=status.HTTP_201_CREATED)
def bootstrap_account(payload: PaperAccountCreate, db: Session = Depends(get_db)) -> PaperAccount:
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = db.query(PaperAccount).filter(PaperAccount.user_id == payload.user_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paper account already exists")

    account = PaperAccount(user_id=payload.user_id, cash_balance=payload.starting_balance, equity=payload.starting_balance)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/accounts/{user_id}", response_model=PaperAccountRead)
def get_account(user_id: int, db: Session = Depends(get_db)) -> PaperAccount:
    account = db.query(PaperAccount).filter(PaperAccount.user_id == user_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper account not found")
    return account


@router.post("/orders/market", response_model=PaperOrderRead)
def place_market_order(payload: PaperOrderCreate, db: Session = Depends(get_db)) -> PaperOrder:
    account = db.query(PaperAccount).filter(PaperAccount.user_id == payload.user_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper account not found")

    policy = db.query(RiskPolicy).filter(RiskPolicy.user_id == payload.user_id).first()
    global_control = db.query(GlobalControl).filter(GlobalControl.key == "global_kill_switch").first()

    open_positions = (
        db.query(PaperPosition)
        .filter(PaperPosition.user_id == payload.user_id, PaperPosition.quantity > 0)
        .count()
    )
    realized_pnl = (
        db.query(PaperPosition)
        .filter(PaperPosition.user_id == payload.user_id)
        .with_entities(PaperPosition.realized_pnl)
        .all()
    )
    total_realized = sum(value[0] for value in realized_pnl)

    requested_price = mark_price(payload.symbol)
    intent = OrderIntent(
        user_id=payload.user_id,
        symbol=payload.symbol,
        account_equity=account.equity,
        entry_price=requested_price,
        stop_price=requested_price * 0.99,
        daily_pnl=total_realized,
        open_positions=open_positions,
        consecutive_losses_today=0,
    )

    global_kill_switch_on = global_control.value == "on" if global_control else False
    if global_kill_switch_on:
        decision_approved = False
        reason_codes = ["GLOBAL_KILL_SWITCH_ON"]
    elif not policy:
        decision_approved = False
        reason_codes = ["POLICY_MISSING"]
    else:
        decision = evaluate_order_intent(
            intent,
            has_policy=True,
            is_kill_switch_on=policy.is_kill_switch_on,
            live_trading_enabled=True,
            allowed_symbols=policy.allowed_symbols,
            max_risk_per_trade_pct=policy.max_risk_per_trade_pct,
            max_daily_loss=policy.max_daily_loss,
            max_open_positions=policy.max_open_positions,
            consecutive_loss_limit=policy.consecutive_loss_limit,
        )
        decision_approved = decision.approved
        reason_codes = decision.reason_codes

    if not decision_approved:
        rejected = PaperOrder(
            user_id=payload.user_id,
            symbol=payload.symbol.upper(),
            side=payload.side,
            order_type="market",
            quantity=payload.quantity,
            filled_quantity=0,
            requested_price=requested_price,
            fill_price=requested_price,
            fee=0,
            status="rejected",
            rejection_reason=",".join(reason_codes),
        )
        db.add(rejected)
        db.add(RiskEvent(user_id=payload.user_id, symbol=payload.symbol.upper(), approved=False, reason_codes=reason_codes))
        db.commit()
        db.refresh(rejected)
        return rejected

    position = db.query(PaperPosition).filter(PaperPosition.user_id == payload.user_id, PaperPosition.symbol == payload.symbol.upper()).first()
    order, updated_position = apply_fill(
        account,
        position,
        symbol=payload.symbol,
        side=payload.side,
        quantity=payload.quantity,
        requested_price=requested_price,
    )

    db.add(order)
    db.add(updated_position)
    db.add(account)
    db.add(RiskEvent(user_id=payload.user_id, symbol=payload.symbol.upper(), approved=True, reason_codes=[]))
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/{order_id}/cancel", response_model=PaperOrderRead)
def cancel_order(order_id: int, db: Session = Depends(get_db)) -> PaperOrder:
    order = db.query(PaperOrder).filter(PaperOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper order not found")
    if order.status in {"filled", "rejected", "canceled"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order cannot be canceled")

    order.status = "canceled"
    db.commit()
    db.refresh(order)
    return order


@router.get("/orders/{user_id}", response_model=list[PaperOrderRead])
def list_orders(user_id: int, db: Session = Depends(get_db)) -> list[PaperOrder]:
    return (
        db.query(PaperOrder)
        .filter(PaperOrder.user_id == user_id)
        .order_by(PaperOrder.created_at.desc())
        .limit(200)
        .all()
    )


@router.get("/positions/{user_id}", response_model=list[PaperPositionRead])
def list_positions(user_id: int, db: Session = Depends(get_db)) -> list[PaperPosition]:
    return db.query(PaperPosition).filter(PaperPosition.user_id == user_id).order_by(PaperPosition.symbol.asc()).all()


@router.get("/pnl/{user_id}", response_model=PaperPnlRead)
def pnl_summary(user_id: int, db: Session = Depends(get_db)) -> PaperPnlRead:
    positions = db.query(PaperPosition).filter(PaperPosition.user_id == user_id).all()
    realized = sum(position.realized_pnl for position in positions)
    unrealized = 0.0

    for position in positions:
        if position.quantity <= 0:
            continue
        current = mark_price(position.symbol)
        unrealized += (current - position.avg_price) * position.quantity

    return PaperPnlRead(realized_pnl=round(realized, 2), unrealized_pnl=round(unrealized, 2), total_pnl=round(realized + unrealized, 2))


@router.post("/reconcile/{user_id}", response_model=ReconcileResult)
def reconcile_account(user_id: int, db: Session = Depends(get_db)) -> ReconcileResult:
    account = db.query(PaperAccount).filter(PaperAccount.user_id == user_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper account not found")

    positions = db.query(PaperPosition).filter(PaperPosition.user_id == user_id).all()
    computed_equity = compute_equity(account, positions)
    drift = round(computed_equity - account.equity, 4)
    corrected = abs(drift) > 0.01

    if corrected:
        account.equity = computed_equity
        db.commit()

    return ReconcileResult(
        user_id=user_id,
        computed_equity=computed_equity,
        stored_equity=round(account.equity, 4),
        drift=drift,
        corrected=corrected,
    )
