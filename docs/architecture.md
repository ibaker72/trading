# Trading Assistant Architecture (Phase 7)

## Services
- `services/api`: FastAPI backend for auth, health checks, market data APIs, deterministic strategy scanning, risk guardrails, and paper trading.
- `services/worker`: Queue-based reconciliation worker prototype (RQ + Redis).
- `apps/web`: Placeholder for Next.js frontend.

## Core boundaries
- API handles request validation, auth, and orchestration.
- Data access isolated in SQLAlchemy models.
- Market provider contracts live in `app/market_data/providers`.
- Strategy/rule evaluation lives in `app/strategy/engine.py`.
- Risk policy + decisioning lives in `app/risk/service.py`.
- Paper trading lifecycle logic lives in `app/paper/service.py`.
- Worker jobs and scheduling live in `services/worker`.

## Implemented in Phase 7
- Added worker queue bootstrap (`worker_queue.py`) with Redis-backed queues.
- Added async-style job function `reconcile_user` in `jobs.py`.
- Added scheduler script to enqueue reconcile jobs for configurable user IDs.
- Added worker runner script to process `reconcile` queue.
- Updated docker-compose with `worker` and `scheduler` services.

## Next
- Replace script scheduler with interval-based scheduler/cron service.
- Add robust retry policies, dead-letter queue, and job observability.
- Build frontend dashboard for paper account, orders, reconciliation state, and trade journal.
- Add real provider adapters with caching and failure metrics.
