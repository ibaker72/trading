from conftest import client


def test_signup_login_and_me() -> None:
    signup_response = client.post(
        "/auth/signup",
        json={
            "email": "user@example.com",
            "full_name": "Test User",
            "password": "StrongPassword123",
            "role": "trader",
        },
    )
    assert signup_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        data={"username": "user@example.com", "password": "StrongPassword123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"
