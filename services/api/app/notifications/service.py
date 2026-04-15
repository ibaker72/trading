"""
Notification service — pluggable backends: webhook (Slack/Discord) and email (SMTP).

All send functions are fire-and-forget; failures are logged but never raised
so they can never break the trading loop.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.text import MIMEText

import httpx

logger = logging.getLogger(__name__)


@dataclass
class NotificationSettings:
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class NotificationService:
    def __init__(self, settings: NotificationSettings) -> None:
        self._s = settings

    # -- Trigger-specific helpers ------------------------------------------

    def trade_entered(self, symbol: str, side: str, qty: float, price: float, sl: float, tp: float) -> None:
        if not self._s.notify_on_trade:
            return
        emoji = "🟢" if side == "buy" else "🔴"
        msg = (
            f"{emoji} *Trade Entered* | {symbol}\n"
            f"Side: {side.upper()}  Qty: {qty}  Price: ${price:.4f}\n"
            f"SL: ${sl:.4f}  TP: ${tp:.4f}"
        )
        self._dispatch(subject=f"Trade Entered: {symbol}", body=msg)

    def trade_exited(self, symbol: str, side: str, qty: float, exit_price: float, pnl: float, status: str) -> None:
        if not self._s.notify_on_trade:
            return
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        emoji = "✅" if pnl >= 0 else "❌"
        msg = (
            f"{emoji} *Trade Exited* | {symbol}\n"
            f"Exit: ${exit_price:.4f}  PnL: {pnl_str}  Status: {status}"
        )
        self._dispatch(subject=f"Trade Exited: {symbol} ({pnl_str})", body=msg)

    def error_occurred(self, error_msg: str) -> None:
        if not self._s.notify_on_error:
            return
        msg = f"🚨 *Bot Error*\n{error_msg}"
        self._dispatch(subject="Trading Bot Error", body=msg)

    def kill_switch_activated(self, scope: str, enabled: bool) -> None:
        if not self._s.notify_on_kill_switch:
            return
        state = "ENABLED" if enabled else "DISABLED"
        msg = f"⚠️ *Kill Switch {state}*\nScope: {scope}"
        self._dispatch(subject=f"Kill Switch {state}: {scope}", body=msg)

    def daily_summary(self, trades: int, pnl: float, win_rate: float, errors: int) -> None:
        if not self._s.notify_on_daily_summary:
            return
        pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        msg = (
            f"📊 *Daily Summary*\n"
            f"Trades: {trades}  P&L: {pnl_str}  Win rate: {win_rate*100:.1f}%  Errors: {errors}"
        )
        self._dispatch(subject=f"Daily Summary — P&L: {pnl_str}", body=msg)

    # -- Dispatch to backends -----------------------------------------------

    def _dispatch(self, subject: str, body: str) -> None:
        if self._s.webhook_url:
            _send_webhook(self._s.webhook_url, body)
        if self._s.email_to and self._s.smtp_user:
            _send_email(
                to=self._s.email_to,
                subject=subject,
                body=body,
                host=self._s.smtp_host,
                port=self._s.smtp_port,
                user=self._s.smtp_user,
                password=self._s.smtp_password,
                use_tls=self._s.smtp_tls,
            )

    def test(self) -> dict:
        """Send a test notification to all configured backends."""
        results: dict[str, str] = {}
        if self._s.webhook_url:
            ok = _send_webhook(self._s.webhook_url, "🔔 Test notification from Trading Bot")
            results["webhook"] = "ok" if ok else "failed"
        if self._s.email_to and self._s.smtp_user:
            ok = _send_email(
                to=self._s.email_to,
                subject="Test: Trading Bot Notification",
                body="This is a test notification from the trading bot.",
                host=self._s.smtp_host,
                port=self._s.smtp_port,
                user=self._s.smtp_user,
                password=self._s.smtp_password,
                use_tls=self._s.smtp_tls,
            )
            results["email"] = "ok" if ok else "failed"
        if not results:
            results["status"] = "no backends configured"
        return results


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------

def _send_webhook(url: str, text: str) -> bool:
    """POST a Slack/Discord-compatible webhook payload."""
    try:
        # Slack uses {"text": "..."}, Discord uses {"content": "..."}
        # Send both keys so it works with either platform
        payload = {"text": text, "content": text}
        with httpx.Client(timeout=5) as client:
            resp = client.post(url, json=payload)
        if resp.status_code < 300:
            return True
        logger.warning("Webhook returned %d: %s", resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        logger.warning("Webhook send failed: %s", exc)
        return False


def _send_email(*, to: str, subject: str, body: str, host: str, port: int, user: str, password: str, use_tls: bool) -> bool:
    """Send an email via SMTP."""
    try:
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to

        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls(context=context)
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.login(user, password)
                server.send_message(msg)
        return True
    except Exception as exc:
        logger.warning("Email send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Factory — builds from app settings or a DB config row
# ---------------------------------------------------------------------------

def build_from_settings() -> NotificationService:
    from app.config import get_settings
    s = get_settings()
    return NotificationService(NotificationSettings(
        webhook_url=s.notify_webhook_url,
        email_to=s.notify_email_to,
        smtp_host=s.notify_smtp_host,
        smtp_port=s.notify_smtp_port,
        smtp_user=s.notify_smtp_user,
        smtp_password=s.notify_smtp_password,
        smtp_tls=s.notify_smtp_tls,
    ))


def build_from_db(db) -> NotificationService:
    """Build from DB config row (id=1), falling back to env settings."""
    try:
        from app.models import NotificationConfig
        row = db.query(NotificationConfig).filter(
            NotificationConfig.id == 1, NotificationConfig.is_active == True
        ).first()
        if row:
            return NotificationService(NotificationSettings(
                webhook_url=row.webhook_url or "",
                email_to=row.email_to or "",
                smtp_host=row.smtp_host or "smtp.gmail.com",
                smtp_port=row.smtp_port or 587,
                smtp_user=row.smtp_user or "",
                smtp_password=row.smtp_password or "",
                smtp_tls=row.smtp_tls,
                notify_on_trade=row.notify_on_trade,
                notify_on_error=row.notify_on_error,
                notify_on_kill_switch=row.notify_on_kill_switch,
                notify_on_daily_summary=row.notify_on_daily_summary,
            ))
    except Exception as exc:
        logger.warning("Failed to load notification config from DB: %s", exc)
    return build_from_settings()
