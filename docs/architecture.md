# Trading Assistant Architecture (Phase 6)

## Services
- `services/api`: FastAPI backend for auth, health checks, market data APIs, deterministic strategy scanning, risk guardrails, and paper trading.
- `services/worker`: Prototype reconciliation worker.
- `apps/web`: Placeholder for Next.js frontend.

## Core boundaries
- API handles request validation, auth, and orchestration.
- Data access isolated in SQLAlchemy models.
- Market provider contracts live in `app/market_data/providers`.
- Strategy/rule evaluation lives in `app/strategy/engine.py`.
- Risk policy + decisioning lives in `app/risk/service.py`.
- Paper trading lifecycle logic lives in `app/paper/service.py`.

## Implemented in Phase 6
- Paper order lifecycle expanded with statuses:
  - `created`
  - `partially_filled`
  - `filled`
  - `canceled`
  - `rejected`
- Partial fill simulation for larger market orders.
- Cancel endpoint for cancellable paper orders.
- Reconciliation endpoint to correct paper account equity drift.
- Worker prototype script (`services/worker/reconcile_worker.py`) to trigger account reconciliation calls.

## Next
- Replace prototype worker with queue/scheduler-backed jobs.
- Build frontend dashboard for paper account, orders, reconciliation state, and trade journal.
- Add real provider adapters with caching and failure metrics.
