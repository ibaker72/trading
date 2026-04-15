from __future__ import annotations

import os

from redis import Redis
from rq import Queue


def get_redis_connection() -> Redis:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(redis_url)


def get_queue(name: str = "reconcile") -> Queue:
    return Queue(name, connection=get_redis_connection())
