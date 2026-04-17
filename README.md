# trading

Phase 1-7 scaffold for a personal trading assistant platform.

## Structure
- `services/api` FastAPI backend (auth + health + market data + strategy scanning + risk guardrails + paper trading)
- `services/worker` queue worker prototype scripts (RQ + Redis)
- `apps/web` frontend placeholder
- `docs` architecture notes
- `.github/workflows` CI for API tests

## Local API run
```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Worker run
```bash
cd services/worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python worker.py
# in another shell
python scheduler.py
```

## Run tests
```bash
cd services/api
pytest -q
```

## API endpoints
- `GET /health/live`
- `GET /health/ready`
- `POST /auth/signup`
- `POST /auth/login`
- `GET /auth/me`
- `GET /markets/assets`
- `GET /markets/quote`
- `GET /markets/candles`
- `GET /markets/candles/quality`
- `POST /strategies`
- `GET /strategies`
- `POST /strategies/{strategy_id}/scan`
- `GET /strategies/signals`
- `POST /risk/policies`
- `GET /risk/policies/{user_id}`
- `POST /risk/kill-switch/global`
- `POST /risk/kill-switch/user/{user_id}`
- `POST /risk/check-intent`
- `GET /risk/events/{user_id}`
- `POST /paper/accounts`
- `GET /paper/accounts/{user_id}`
- `POST /paper/orders/market`
- `POST /paper/orders/{order_id}/cancel`
- `GET /paper/orders/{user_id}`
- `GET /paper/positions/{user_id}`
- `GET /paper/pnl/{user_id}`
- `POST /paper/reconcile/{user_id}`

## Docker compose
```bash
docker compose up --build
docker compose watch
```

`docker compose watch` is configured for the `api`, `web`, `worker`, and `scheduler` services.
Python service code changes are synced into the container and the service restarts automatically.
Frontend changes trigger a rebuild of the `web` image because that container currently runs the production Next.js server.
