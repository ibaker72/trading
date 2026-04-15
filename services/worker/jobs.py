from __future__ import annotations

import os

import httpx


def reconcile_user(user_id: int) -> dict:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    url = f"{base_url}/paper/reconcile/{user_id}"

    with httpx.Client(timeout=15) as client:
        response = client.post(url)

    return {
        "user_id": user_id,
        "status_code": response.status_code,
        "body": response.text,
    }
