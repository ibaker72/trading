"""Simple reconciliation worker placeholder.

This script is a local, synchronous worker prototype for Phase 6.
It calls paper reconcile endpoints for a list of user IDs.
"""

from __future__ import annotations

import os

import httpx


def run(user_ids: list[int]) -> None:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    with httpx.Client(timeout=10) as client:
        for user_id in user_ids:
            response = client.post(f"{base_url}/paper/reconcile/{user_id}")
            print(f"user={user_id} status={response.status_code} body={response.text}")


if __name__ == "__main__":
    run([1])
