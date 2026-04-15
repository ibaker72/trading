from __future__ import annotations

import os

from worker_queue import get_queue


def parse_user_ids(raw: str) -> list[int]:
    return [int(value.strip()) for value in raw.split(",") if value.strip()]


def enqueue_reconcile_jobs() -> list[str]:
    user_ids_raw = os.getenv("RECONCILE_USER_IDS", "1")
    user_ids = parse_user_ids(user_ids_raw)
    queue = get_queue("reconcile")
    job_ids: list[str] = []

    for user_id in user_ids:
        job = queue.enqueue("jobs.reconcile_user", user_id)
        job_ids.append(job.id)

    return job_ids


if __name__ == "__main__":
    print(enqueue_reconcile_jobs())
