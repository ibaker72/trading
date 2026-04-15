from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NotificationConfig
from app.notifications.service import build_from_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationConfigCreate(BaseModel):
    webhook_url: str = ""
    email_to: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = True
    notify_on_trade: bool = True
    notify_on_error: bool = True
    notify_on_kill_switch: bool = True
    notify_on_daily_summary: bool = True
    is_active: bool = True


class NotificationConfigRead(BaseModel):
    id: int
    webhook_url: str | None
    email_to: str | None
    smtp_host: str | None
    smtp_port: int | None
    smtp_user: str | None
    smtp_tls: bool
    notify_on_trade: bool
    notify_on_error: bool
    notify_on_kill_switch: bool
    notify_on_daily_summary: bool
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/config", response_model=NotificationConfigRead | None)
def get_config(db: Session = Depends(get_db)):
    return db.query(NotificationConfig).filter(NotificationConfig.id == 1).first()


@router.post("/config", response_model=NotificationConfigRead, status_code=status.HTTP_201_CREATED)
def upsert_config(payload: NotificationConfigCreate, db: Session = Depends(get_db)):
    row = db.query(NotificationConfig).filter(NotificationConfig.id == 1).first()
    if row is None:
        row = NotificationConfig(id=1)
        db.add(row)
    row.webhook_url = payload.webhook_url or None
    row.email_to = payload.email_to or None
    row.smtp_host = payload.smtp_host or None
    row.smtp_port = payload.smtp_port
    row.smtp_user = payload.smtp_user or None
    row.smtp_password = payload.smtp_password or None
    row.smtp_tls = payload.smtp_tls
    row.notify_on_trade = payload.notify_on_trade
    row.notify_on_error = payload.notify_on_error
    row.notify_on_kill_switch = payload.notify_on_kill_switch
    row.notify_on_daily_summary = payload.notify_on_daily_summary
    row.is_active = payload.is_active
    db.commit()
    db.refresh(row)
    return row


@router.post("/test")
def test_notification(db: Session = Depends(get_db)) -> dict:
    svc = build_from_db(db)
    return svc.test()
