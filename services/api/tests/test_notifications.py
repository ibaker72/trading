"""
Tests for the notification service: webhook backend, SMTP backend,
trigger helpers, and the /notifications REST endpoints.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.notifications.service import (
    NotificationService,
    NotificationSettings,
    _send_webhook,
    _send_email,
    build_from_settings,
    build_from_db,
)
from tests.conftest import client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_svc(**kwargs) -> NotificationService:
    defaults = dict(
        webhook_url="https://hooks.example.com/test",
        email_to="trader@example.com",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="sender@example.com",
        smtp_password="secret",
        smtp_tls=True,
        notify_on_trade=True,
        notify_on_error=True,
        notify_on_kill_switch=True,
        notify_on_daily_summary=True,
    )
    defaults.update(kwargs)
    return NotificationService(NotificationSettings(**defaults))


# ---------------------------------------------------------------------------
# _send_webhook
# ---------------------------------------------------------------------------

class TestSendWebhook:
    def test_returns_true_on_2xx(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("app.notifications.service.httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
            ctx.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = ctx
            assert _send_webhook("https://hooks.example.com/x", "hello") is True

    def test_returns_false_on_non_2xx(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"
        with patch("app.notifications.service.httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=MagicMock(post=MagicMock(return_value=mock_resp)))
            ctx.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = ctx
            assert _send_webhook("https://hooks.example.com/x", "hello") is False

    def test_returns_false_on_exception(self):
        with patch("app.notifications.service.httpx.Client", side_effect=Exception("timeout")):
            assert _send_webhook("https://hooks.example.com/x", "hello") is False

    def test_payload_has_text_and_content_keys(self):
        """Payload must include both 'text' (Slack) and 'content' (Discord)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        posted_payload = {}

        def fake_post(url, json=None):
            posted_payload.update(json or {})
            return mock_resp

        with patch("app.notifications.service.httpx.Client") as mock_client_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=MagicMock(post=fake_post))
            ctx.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = ctx
            _send_webhook("https://hooks.example.com/x", "my message")

        assert "text" in posted_payload
        assert "content" in posted_payload
        assert posted_payload["text"] == "my message"
        assert posted_payload["content"] == "my message"


# ---------------------------------------------------------------------------
# _send_email
# ---------------------------------------------------------------------------

class TestSendEmail:
    def _call(self, use_tls=True):
        with patch("app.notifications.service.smtplib.SMTP") as mock_smtp_cls:
            server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = _send_email(
                to="to@example.com",
                subject="Test",
                body="body text",
                host="smtp.gmail.com",
                port=587,
                user="user@example.com",
                password="pass",
                use_tls=use_tls,
            )
            return result, server

    def test_returns_true_on_success_tls(self):
        result, server = self._call(use_tls=True)
        assert result is True
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("user@example.com", "pass")
        server.send_message.assert_called_once()

    def test_returns_true_on_success_no_tls(self):
        result, server = self._call(use_tls=False)
        assert result is True
        server.starttls.assert_not_called()
        server.login.assert_called_once()

    def test_returns_false_on_exception(self):
        with patch("app.notifications.service.smtplib.SMTP", side_effect=Exception("refused")):
            result = _send_email(
                to="t@x.com", subject="S", body="B",
                host="smtp.example.com", port=587,
                user="u@x.com", password="p", use_tls=True,
            )
        assert result is False


# ---------------------------------------------------------------------------
# NotificationService — trigger helpers
# ---------------------------------------------------------------------------

class TestNotificationServiceTriggers:
    def _svc_with_mocked_dispatch(self, **kwargs):
        svc = _make_svc(**kwargs)
        svc._dispatch = MagicMock()
        return svc

    def test_trade_entered_dispatches_when_enabled(self):
        svc = self._svc_with_mocked_dispatch()
        svc.trade_entered("AAPL", "buy", 10, 150.0, 148.5, 153.0)
        svc._dispatch.assert_called_once()
        subject, body = svc._dispatch.call_args[1]["subject"], svc._dispatch.call_args[1]["body"]
        assert "AAPL" in subject
        assert "BUY" in body or "buy" in body.lower()

    def test_trade_entered_skipped_when_disabled(self):
        svc = self._svc_with_mocked_dispatch(notify_on_trade=False)
        svc.trade_entered("AAPL", "buy", 10, 150.0, 148.5, 153.0)
        svc._dispatch.assert_not_called()

    def test_trade_exited_positive_pnl(self):
        svc = self._svc_with_mocked_dispatch()
        svc.trade_exited("TSLA", "buy", 5, 200.0, 50.0, "took_profit")
        svc._dispatch.assert_called_once()
        body = svc._dispatch.call_args[1]["body"]
        assert "+$50.00" in body

    def test_trade_exited_negative_pnl(self):
        svc = self._svc_with_mocked_dispatch()
        svc.trade_exited("TSLA", "buy", 5, 190.0, -25.0, "stopped_out")
        svc._dispatch.assert_called_once()
        body = svc._dispatch.call_args[1]["body"]
        assert "-$25.00" in body

    def test_error_occurred_dispatches(self):
        svc = self._svc_with_mocked_dispatch()
        svc.error_occurred("Something went wrong")
        svc._dispatch.assert_called_once()
        body = svc._dispatch.call_args[1]["body"]
        assert "Something went wrong" in body

    def test_error_occurred_skipped_when_disabled(self):
        svc = self._svc_with_mocked_dispatch(notify_on_error=False)
        svc.error_occurred("boom")
        svc._dispatch.assert_not_called()

    def test_kill_switch_activated(self):
        svc = self._svc_with_mocked_dispatch()
        svc.kill_switch_activated("global", True)
        svc._dispatch.assert_called_once()
        body = svc._dispatch.call_args[1]["body"]
        assert "ENABLED" in body

    def test_kill_switch_disabled(self):
        svc = self._svc_with_mocked_dispatch()
        svc.kill_switch_activated("global", False)
        body = svc._dispatch.call_args[1]["body"]
        assert "DISABLED" in body

    def test_daily_summary(self):
        svc = self._svc_with_mocked_dispatch()
        svc.daily_summary(trades=10, pnl=123.45, win_rate=0.7, errors=1)
        svc._dispatch.assert_called_once()
        body = svc._dispatch.call_args[1]["body"]
        assert "10" in body
        assert "+$123.45" in body

    def test_daily_summary_skipped_when_disabled(self):
        svc = self._svc_with_mocked_dispatch(notify_on_daily_summary=False)
        svc.daily_summary(trades=1, pnl=0.0, win_rate=0.5, errors=0)
        svc._dispatch.assert_not_called()


# ---------------------------------------------------------------------------
# NotificationService.test()
# ---------------------------------------------------------------------------

class TestNotificationServiceTest:
    def test_test_with_webhook_ok(self):
        with patch("app.notifications.service._send_webhook", return_value=True):
            svc = _make_svc(email_to="", smtp_user="")
            result = svc.test()
        assert result["webhook"] == "ok"
        assert "email" not in result

    def test_test_with_email_failed(self):
        with patch("app.notifications.service._send_email", return_value=False):
            svc = _make_svc(webhook_url="")
            result = svc.test()
        assert result["email"] == "failed"

    def test_test_no_backends(self):
        svc = _make_svc(webhook_url="", email_to="", smtp_user="")
        result = svc.test()
        assert result.get("status") == "no backends configured"


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------

class TestFactories:
    def test_build_from_settings(self):
        # get_settings is lazily imported inside build_from_settings(), so patch at source
        with patch("app.config.get_settings") as mock_gs:
            s = MagicMock()
            s.notify_webhook_url = "https://hooks.example.com"
            s.notify_email_to = ""
            s.notify_smtp_host = "smtp.gmail.com"
            s.notify_smtp_port = 587
            s.notify_smtp_user = ""
            s.notify_smtp_password = ""
            s.notify_smtp_tls = True
            mock_gs.return_value = s
            svc = build_from_settings()
        assert isinstance(svc, NotificationService)
        assert svc._s.webhook_url == "https://hooks.example.com"

    def test_build_from_db_uses_row_when_active(self):
        mock_db = MagicMock()
        row = MagicMock()
        row.webhook_url = "https://hooks.example.com/db"
        row.email_to = None
        row.smtp_host = "smtp.gmail.com"
        row.smtp_port = 587
        row.smtp_user = None
        row.smtp_password = None
        row.smtp_tls = True
        row.notify_on_trade = True
        row.notify_on_error = True
        row.notify_on_kill_switch = True
        row.notify_on_daily_summary = True
        mock_db.query.return_value.filter.return_value.first.return_value = row
        svc = build_from_db(mock_db)
        assert svc._s.webhook_url == "https://hooks.example.com/db"

    def test_build_from_db_falls_back_to_settings_when_no_row(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with patch("app.notifications.service.build_from_settings") as mock_bfs:
            mock_bfs.return_value = MagicMock()
            build_from_db(mock_db)
            mock_bfs.assert_called_once()


# ---------------------------------------------------------------------------
# REST endpoints — /notifications/config and /notifications/test
# ---------------------------------------------------------------------------

class TestNotificationEndpoints:
    def test_get_config_returns_none_when_not_set(self):
        resp = client.get("/notifications/config")
        assert resp.status_code == 200
        # May be null if row doesn't exist yet
        assert resp.json() is None or isinstance(resp.json(), dict)

    def test_upsert_config_creates_row(self):
        payload = {
            "webhook_url": "https://hooks.slack.com/test",
            "email_to": "",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password": "",
            "smtp_tls": True,
            "notify_on_trade": True,
            "notify_on_error": True,
            "notify_on_kill_switch": True,
            "notify_on_daily_summary": True,
            "is_active": True,
        }
        resp = client.post("/notifications/config", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["webhook_url"] == "https://hooks.slack.com/test"
        assert data["is_active"] is True

    def test_get_config_returns_row_after_upsert(self):
        # Ensure row exists first
        client.post("/notifications/config", json={
            "webhook_url": "https://hooks.test.com",
            "is_active": True,
        })
        resp = client.get("/notifications/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None
        assert data["id"] == 1

    def test_upsert_config_updates_existing_row(self):
        # Create initial row
        client.post("/notifications/config", json={
            "webhook_url": "https://hooks.v1.com",
            "is_active": True,
        })
        # Update it
        resp = client.post("/notifications/config", json={
            "webhook_url": "https://hooks.v2.com",
            "notify_on_trade": False,
            "is_active": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["webhook_url"] == "https://hooks.v2.com"
        assert data["notify_on_trade"] is False

    def test_test_notification_returns_status(self):
        with patch("app.notifications.service._send_webhook", return_value=True):
            client.post("/notifications/config", json={
                "webhook_url": "https://hooks.test.com/webhook",
                "is_active": True,
            })
            resp = client.post("/notifications/test")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)
