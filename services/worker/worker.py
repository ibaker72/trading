from __future__ import annotations

from redis import Redis
from rq import Worker

from worker_queue import get_redis_connection


def run() -> None:
    connection: Redis = get_redis_connection()
    worker = Worker(["reconcile"], connection=connection)
    worker.work()


if __name__ == "__main__":
    run()
