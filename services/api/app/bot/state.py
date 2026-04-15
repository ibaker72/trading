from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


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


_state = BotState()


def get_state() -> BotState:
    return _state


def set_status(status: BotStatus) -> None:
    _state.status = status
    if status == BotStatus.RUNNING and _state.started_at is None:
        from datetime import UTC
        _state.started_at = datetime.now(UTC)


def record_scan() -> None:
    from datetime import UTC
    _state.last_scan_at = datetime.now(UTC)


def record_signal() -> None:
    from datetime import UTC
    _state.last_signal_at = datetime.now(UTC)


def record_trade() -> None:
    _state.trades_today += 1


def record_error(msg: str) -> None:
    from datetime import UTC
    _state.errors_today += 1
    _state.last_error = msg
    _state.status = BotStatus.ERROR
