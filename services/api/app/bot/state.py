"""
Bot state management — persisted to BotSession DB table, with an in-memory
cache so hot-path reads never hit the database.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

logger = logging.getLogger(__name__)


class BotStatus(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


@dataclass
class BotState:
    status: BotStatus = BotStatus.STOPPED
    started_at: datetime | None = None
    last_scan_at: datetime | None = None
    last_signal_at: datetime | None = None
    trades_today: int = 0
    errors_today: int = 0
    last_error: str | None = None


# ---------------------------------------------------------------------------
# In-memory cache (always authoritative for hot reads)
# ---------------------------------------------------------------------------

_state = BotState()


def get_state() -> BotState:
    return _state


# ---------------------------------------------------------------------------
# DB persistence helpers
# ---------------------------------------------------------------------------

def _save(db) -> None:
    """Upsert the singleton BotSession row (id=1)."""
    try:
        from app.models import BotSession
        row = db.query(BotSession).filter(BotSession.id == 1).first()
        if row is None:
            row = BotSession(id=1)
            db.add(row)
        row.status = _state.status.value
        row.started_at = _state.started_at
        row.last_scan_at = _state.last_scan_at
        row.last_signal_at = _state.last_signal_at
        row.trades_today = _state.trades_today
        row.errors_today = _state.errors_today
        row.last_error = _state.last_error
        db.commit()
    except Exception as exc:
        logger.warning("BotState DB save failed: %s", exc)


def rehydrate(db) -> None:
    """Load the last saved BotSession into the in-memory cache on startup."""
    try:
        from app.models import BotSession
        row = db.query(BotSession).filter(BotSession.id == 1).first()
        if row is None:
            return
        _state.status = BotStatus(row.status)
        # On rehydrate always mark as STOPPED — don't auto-resume a RUNNING state
        if _state.status == BotStatus.RUNNING:
            _state.status = BotStatus.STOPPED
        _state.started_at = row.started_at
        _state.last_scan_at = row.last_scan_at
        _state.last_signal_at = row.last_signal_at
        _state.trades_today = row.trades_today
        _state.errors_today = row.errors_today
        _state.last_error = row.last_error
        logger.info("BotState rehydrated from DB (trades_today=%d)", _state.trades_today)
    except Exception as exc:
        logger.warning("BotState rehydrate failed: %s", exc)


# ---------------------------------------------------------------------------
# Mutation helpers — update cache, then persist if a DB session is provided
# ---------------------------------------------------------------------------

def set_status(status: BotStatus, db=None) -> None:
    _state.status = status
    if status == BotStatus.RUNNING and _state.started_at is None:
        _state.started_at = datetime.now(UTC)
    if db is not None:
        _save(db)


def record_scan(db=None) -> None:
    _state.last_scan_at = datetime.now(UTC)
    if db is not None:
        _save(db)


def record_signal(db=None) -> None:
    _state.last_signal_at = datetime.now(UTC)
    if db is not None:
        _save(db)


def record_trade(db=None) -> None:
    _state.trades_today += 1
    if db is not None:
        _save(db)


def record_error(msg: str, db=None) -> None:
    _state.errors_today += 1
    _state.last_error = msg
    _state.status = BotStatus.ERROR
    if db is not None:
        _save(db)
