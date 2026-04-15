from conftest import client


def _create_user(email: str) -> int:
    signup_response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "full_name": "Risk User",
            "password": "StrongPassword123",
            "role": "trader",
        },
    )
    assert signup_response.status_code == 201
    return signup_response.json()["id"]


def test_risk_policy_and_approval_flow() -> None:
    user_id = _create_user("risk1@example.com")

    policy_response = client.post(
        "/risk/policies",
        json={
            "user_id": user_id,
            "max_risk_per_trade_pct": 1.0,
            "max_daily_loss": 500,
            "max_open_positions": 3,
            "consecutive_loss_limit": 2,
            "allowed_symbols": ["ETHUSD", "BTCUSD"],
            "live_trading_enabled": True,
        },
    )
    assert policy_response.status_code == 201

    decision_response = client.post(
        "/risk/check-intent",
        json={
            "user_id": user_id,
            "symbol": "ETHUSD",
            "account_equity": 10000,
            "entry_price": 2500,
            "stop_price": 2475,
            "daily_pnl": -100,
            "open_positions": 1,
            "consecutive_losses_today": 0,
        },
    )
    assert decision_response.status_code == 200
    decision = decision_response.json()
    assert decision["approved"] is True
    assert decision["position_sizing"]["suggested_quantity"] > 0


def test_risk_blocks_when_daily_limit_exceeded_and_global_kill_switch_on() -> None:
    user_id = _create_user("risk2@example.com")

    client.post(
        "/risk/policies",
        json={
            "user_id": user_id,
            "max_risk_per_trade_pct": 1.0,
            "max_daily_loss": 200,
            "max_open_positions": 2,
            "consecutive_loss_limit": 2,
            "allowed_symbols": ["BTCUSD"],
            "live_trading_enabled": True,
        },
    )

    daily_loss_block = client.post(
        "/risk/check-intent",
        json={
            "user_id": user_id,
            "symbol": "BTCUSD",
            "account_equity": 5000,
            "entry_price": 50000,
            "stop_price": 49500,
            "daily_pnl": -300,
            "open_positions": 1,
            "consecutive_losses_today": 0,
        },
    )
    assert daily_loss_block.status_code == 200
    assert daily_loss_block.json()["approved"] is False
    assert "DAILY_LOSS_LIMIT_REACHED" in daily_loss_block.json()["reason_codes"]

    global_switch_response = client.post("/risk/kill-switch/global", json={"enabled": True})
    assert global_switch_response.status_code == 200

    blocked_by_global = client.post(
        "/risk/check-intent",
        json={
            "user_id": user_id,
            "symbol": "BTCUSD",
            "account_equity": 5000,
            "entry_price": 50000,
            "stop_price": 49500,
            "daily_pnl": 0,
            "open_positions": 0,
            "consecutive_losses_today": 0,
        },
    )
    assert blocked_by_global.status_code == 200
    assert blocked_by_global.json()["approved"] is False
    assert blocked_by_global.json()["reason_codes"] == ["GLOBAL_KILL_SWITCH_ON"]

    events_response = client.get(f"/risk/events/{user_id}")
    assert events_response.status_code == 200
    assert len(events_response.json()) >= 2
