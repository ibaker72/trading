from conftest import client


def _create_user(email: str) -> int:
    response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "full_name": "Paper User",
            "password": "StrongPassword123",
            "role": "trader",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_risk_policy(user_id: int) -> None:
    response = client.post(
        "/risk/policies",
        json={
            "user_id": user_id,
            "max_risk_per_trade_pct": 2.0,
            "max_daily_loss": 500,
            "max_open_positions": 5,
            "consecutive_loss_limit": 3,
            "allowed_symbols": ["BTCUSD", "ETHUSD"],
            "live_trading_enabled": True,
        },
    )
    assert response.status_code == 201


def test_paper_account_partial_fill_cancel_and_reconcile_flow() -> None:
    user_id = _create_user("paper1@example.com")
    _create_risk_policy(user_id)

    account_response = client.post("/paper/accounts", json={"user_id": user_id, "starting_balance": 10000})
    assert account_response.status_code == 201

    order_response = client.post(
        "/paper/orders/market",
        json={"user_id": user_id, "symbol": "BTCUSD", "side": "buy", "quantity": 2},
    )
    assert order_response.status_code == 200
    order = order_response.json()
    assert order["status"] == "partially_filled"
    assert order["filled_quantity"] == 1

    cancel_response = client.post(f"/paper/orders/{order['id']}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "canceled"

    reconcile_response = client.post(f"/paper/reconcile/{user_id}")
    assert reconcile_response.status_code == 200
    assert "drift" in reconcile_response.json()

    positions_response = client.get(f"/paper/positions/{user_id}")
    assert positions_response.status_code == 200
    assert len(positions_response.json()) >= 1

    pnl_response = client.get(f"/paper/pnl/{user_id}")
    assert pnl_response.status_code == 200
    assert "total_pnl" in pnl_response.json()


def test_paper_order_rejected_without_policy() -> None:
    user_id = _create_user("paper2@example.com")
    account_response = client.post("/paper/accounts", json={"user_id": user_id, "starting_balance": 5000})
    assert account_response.status_code == 201

    order_response = client.post(
        "/paper/orders/market",
        json={"user_id": user_id, "symbol": "BTCUSD", "side": "buy", "quantity": 1},
    )
    assert order_response.status_code == 200
    assert order_response.json()["status"] == "rejected"
    assert "POLICY_MISSING" in order_response.json()["rejection_reason"]
