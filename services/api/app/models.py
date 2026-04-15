from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum("admin", "trader", name="role_enum"), nullable=False, default="trader")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    asset_class = Column(Enum("stock", "crypto", name="asset_class_enum"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    candles = relationship("Candle", back_populates="asset", cascade="all, delete-orphan")


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (UniqueConstraint("asset_id", "timeframe", "timestamp", name="uq_candle_asset_tf_ts"),)

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    provider = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asset = relationship("Asset", back_populates="candles")


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    asset_class = Column(Enum("stock", "crypto", name="strategy_asset_class_enum"), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, default="1h")
    cooldown_minutes = Column(Integer, nullable=False, default=60)
    rules = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    signals = relationship("Signal", back_populates="strategy", cascade="all, delete-orphan")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    signal_type = Column(String(20), nullable=False, default="entry")
    score = Column(Float, nullable=False)
    explanation = Column(String(500), nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    strategy = relationship("Strategy", back_populates="signals")


class RiskPolicy(Base):
    __tablename__ = "risk_policies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    max_risk_per_trade_pct = Column(Float, nullable=False)
    max_daily_loss = Column(Float, nullable=False)
    max_open_positions = Column(Integer, nullable=False)
    consecutive_loss_limit = Column(Integer, nullable=False, default=3)
    allowed_symbols = Column(JSON, nullable=False, default=list)
    live_trading_enabled = Column(Boolean, nullable=False, default=False)
    is_kill_switch_on = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    approved = Column(Boolean, nullable=False)
    reason_codes = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class GlobalControl(Base):
    __tablename__ = "global_controls"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(120), nullable=False, unique=True)
    value = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    cash_balance = Column(Float, nullable=False, default=0)
    equity = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_paper_position_user_symbol"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0)
    avg_price = Column(Float, nullable=False, default=0)
    realized_pnl = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PaperOrder(Base):
    __tablename__ = "paper_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum("buy", "sell", name="paper_order_side_enum"), nullable=False)
    order_type = Column(Enum("market", name="paper_order_type_enum"), nullable=False, default="market")
    quantity = Column(Float, nullable=False)
    filled_quantity = Column(Float, nullable=False, default=0)
    requested_price = Column(Float, nullable=False)
    fill_price = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    status = Column(
        Enum("created", "partially_filled", "filled", "canceled", "rejected", name="paper_order_status_enum"),
        nullable=False,
        default="created",
    )
    rejection_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TradeJournal(Base):
    __tablename__ = "trade_journal"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    asset_class = Column(Enum("stock", "crypto", name="trade_journal_asset_class_enum"), nullable=False)
    entry_order_id = Column(String(255), nullable=False, index=True)
    exit_order_id = Column(String(255), nullable=True, index=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)
    side = Column(Enum("buy", "sell", name="trade_journal_side_enum"), nullable=False)
    stop_loss_price = Column(Float, nullable=False)
    take_profit_price = Column(Float, nullable=False)
    entry_signal_rules = Column(JSON, nullable=False, default=list)
    realized_pnl = Column(Float, nullable=True)
    status = Column(
        Enum("open", "closed", "stopped_out", "took_profit", name="trade_journal_status_enum"),
        nullable=False,
        default="open",
        index=True,
    )
    opened_at = Column(DateTime(timezone=True), nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BotSession(Base):
    __tablename__ = "bot_sessions"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(
        Enum("STOPPED", "RUNNING", "PAUSED", "ERROR", name="bot_session_status_enum"),
        nullable=False,
        default="STOPPED",
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    last_scan_at = Column(DateTime(timezone=True), nullable=True)
    last_signal_at = Column(DateTime(timezone=True), nullable=True)
    trades_today = Column(Integer, nullable=False, default=0)
    errors_today = Column(Integer, nullable=False, default=0)
    last_error = Column(String(500), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id = Column(Integer, primary_key=True, index=True)
    webhook_url = Column(String(500), nullable=True)
    email_to = Column(String(255), nullable=True)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, nullable=True, default=587)
    smtp_user = Column(String(255), nullable=True)
    smtp_password = Column(String(255), nullable=True)
    smtp_tls = Column(Boolean, nullable=False, default=True)
    notify_on_trade = Column(Boolean, nullable=False, default=True)
    notify_on_error = Column(Boolean, nullable=False, default=True)
    notify_on_kill_switch = Column(Boolean, nullable=False, default=True)
    notify_on_daily_summary = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
