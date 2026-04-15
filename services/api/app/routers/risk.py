from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GlobalControl, RiskEvent, RiskPolicy, User
from app.risk.schemas import (
    KillSwitchUpdate,
    OrderIntent,
    RiskDecision,
    RiskEventRead,
    RiskPolicyCreate,
    RiskPolicyRead,
)
from app.risk.service import evaluate_order_intent

router = APIRouter(prefix="/risk", tags=["risk"])


@router.post("/policies", response_model=RiskPolicyRead, status_code=status.HTTP_201_CREATED)
def upsert_policy(payload: RiskPolicyCreate, db: Session = Depends(get_db)) -> RiskPolicy:
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    policy = db.query(RiskPolicy).filter(RiskPolicy.user_id == payload.user_id).first()
    if not policy:
        policy = RiskPolicy(user_id=payload.user_id)
        db.add(policy)

    policy.max_risk_per_trade_pct = payload.max_risk_per_trade_pct
    policy.max_daily_loss = payload.max_daily_loss
    policy.max_open_positions = payload.max_open_positions
    policy.consecutive_loss_limit = payload.consecutive_loss_limit
    policy.allowed_symbols = [symbol.upper() for symbol in payload.allowed_symbols]
    policy.live_trading_enabled = payload.live_trading_enabled

    db.commit()
    db.refresh(policy)
    return policy


@router.get("/policies/{user_id}", response_model=RiskPolicyRead)
def get_policy(user_id: int, db: Session = Depends(get_db)) -> RiskPolicy:
    policy = db.query(RiskPolicy).filter(RiskPolicy.user_id == user_id).first()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk policy not found")
    return policy


@router.post("/kill-switch/global", response_model=KillSwitchUpdate)
def set_global_kill_switch(payload: KillSwitchUpdate, db: Session = Depends(get_db)) -> KillSwitchUpdate:
    control = db.query(GlobalControl).filter(GlobalControl.key == "global_kill_switch").first()
    if not control:
        control = GlobalControl(key="global_kill_switch", value="off")
        db.add(control)

    control.value = "on" if payload.enabled else "off"
    db.commit()
    return payload


@router.post("/kill-switch/user/{user_id}", response_model=KillSwitchUpdate)
def set_user_kill_switch(user_id: int, payload: KillSwitchUpdate, db: Session = Depends(get_db)) -> KillSwitchUpdate:
    policy = db.query(RiskPolicy).filter(RiskPolicy.user_id == user_id).first()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk policy not found")

    policy.is_kill_switch_on = payload.enabled
    db.commit()
    return payload


@router.post("/check-intent", response_model=RiskDecision)
def check_order_intent(intent: OrderIntent, db: Session = Depends(get_db)) -> RiskDecision:
    global_control = db.query(GlobalControl).filter(GlobalControl.key == "global_kill_switch").first()
    global_kill_switch_on = global_control.value == "on" if global_control else False

    policy = db.query(RiskPolicy).filter(RiskPolicy.user_id == intent.user_id).first()
    if global_kill_switch_on:
        decision = RiskDecision(approved=False, reason_codes=["GLOBAL_KILL_SWITCH_ON"], position_sizing=None)
    elif not policy:
        decision = RiskDecision(approved=False, reason_codes=["POLICY_MISSING"], position_sizing=None)
    else:
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

    db.add(
        RiskEvent(
            user_id=intent.user_id,
            symbol=intent.symbol.upper(),
            approved=decision.approved,
            reason_codes=decision.reason_codes,
        )
    )
    db.commit()
    return decision


@router.get("/events/{user_id}", response_model=list[RiskEventRead])
def get_risk_events(user_id: int, db: Session = Depends(get_db)) -> list[RiskEvent]:
    return (
        db.query(RiskEvent)
        .filter(RiskEvent.user_id == user_id)
        .order_by(RiskEvent.created_at.desc())
        .limit(200)
        .all()
    )
