# Trading Bot Platform — Summary

A fully autonomous intraday day-trading bot for US Stocks and Crypto, built in 12 phases on FastAPI + Next.js.

---

## Architecture

```
apps/web          → Next.js 14 (App Router, TypeScript, Tailwind) trading dashboard
services/api      → FastAPI backend — all logic, data, and broker integration
docker-compose    → postgres, redis, api (port 8000), web (port 3000)
```

---

## Phase-by-Phase Overview

| Phase | Feature |
|---|---|
| 1–6 | Auth, paper trading, risk engine, strategy rules, market data schemas |
| 7 | Real Alpaca broker + market data provider (REST); `/broker` endpoints |
| 8 | Multi-timeframe signal scanner (EMA cross, VWAP cross, gap up/down, RSI, volume spike) |
| 9 | APScheduler execution loop (`TradingBotEngine`) with kill switch + bot state |
| 10 | Next.js dark terminal dashboard — equity chart, scanner table, positions, orders |
| 11 | Exit mechanics: bracket orders (SL/TP), `TradeJournal` DB model, `/analytics` endpoints |
| 12 | Real-time WebSocket price feed, persistent `BotSession` DB state, notification service |

---

## Key Components

### Backend (`services/api/app/`)

| Module | Purpose |
|---|---|
| `broker/alpaca.py` | Alpaca REST client — account, positions, orders, bracket orders |
| `market_data/providers/alpaca.py` | Quotes, candles, asset listing from Alpaca Data API |
| `market_data/stream.py` | Alpaca WebSocket stream → fan-out to browser clients via asyncio queues |
| `strategy/engine.py` | Signal evaluation — EMA cross, VWAP cross, gap up/down, RSI, volume spike |
| `strategy/scanner.py` | Multi-timeframe watchlist scanner; scores and suggests trade side |
| `bot/engine.py` | Main `TradingBotEngine.run_cycle()` — scan → risk check → bracket order → journal |
| `bot/monitor.py` | `PositionMonitor.check_exits()` — reconciles Alpaca closed orders with journal |
| `bot/scheduler.py` | APScheduler background job calling `run_cycle` every N seconds |
| `bot/state.py` | DB-backed `BotState` singleton (BotSession table) with in-memory cache |
| `analytics/service.py` | Pure analytics: win rate, Sharpe ratio, max drawdown, P&L series |
| `notifications/service.py` | Webhook (Slack/Discord) + SMTP email notifications; fire-and-forget |
| `risk/service.py` | `evaluate_order_intent()` — position sizing + kill-switch enforcement |
| `models.py` | SQLAlchemy models: User, RiskPolicy, PaperAccount, PaperOrder, TradeJournal, BotSession, NotificationConfig |

### API Routers

| Prefix | Description |
|---|---|
| `/auth` | JWT login / token refresh |
| `/broker` | Alpaca account, positions, orders, portfolio history |
| `/scanner` | Manual watchlist scan trigger |
| `/bot` | Start / stop / pause bot; status; trade history |
| `/analytics` | Performance metrics, trade journal, P&L series |
| `/notifications` | Get/set notification config; send test notification |
| `/ws/market` | WebSocket — live price tick feed from Alpaca |
| `/ws/status` | Stream health: connected clients, Alpaca configured |
| `/risk` | Kill switches (global + user); risk policy CRUD |
| `/strategies` | Strategy rule templates |
| `/paper` | Paper-trade order history |
| `/markets` | Asset listing and quotes |

### Frontend (`apps/web/app/page.tsx`)

- **Header**: bot status badge, live/offline WS indicator, Start/Pause/Stop/Kill-Switch controls
- **Metric cards**: equity, trades today, errors today, last scan time
- **Performance cards**: win rate, Sharpe ratio, max drawdown, win/loss ratio
- **Portfolio equity chart**: Recharts line chart from Alpaca portfolio history
- **Watchlist scanner table**: symbol, class, live price (WebSocket), score, timeframes, side, trade?
- **Open positions**: symbol, qty, avg entry, current price, unrealised P&L
- **Recent bot orders**: symbol, side, qty, fill price, timestamp
- **Trade journal**: entry/exit/SL/TP/realised P&L/status, colour-coded by outcome
- **Toast notifications**: auto-dismiss toasts when trades close (green=profit, red=stopped out)

---

## Signal Rules

| Rule | Trigger |
|---|---|
| `ema_cross` | Fast EMA crosses above slow EMA (default 9/21) |
| `vwap_cross` | Price crosses above VWAP from below |
| `gap_up` | Open ≥ 1% above previous close |
| `gap_down` | Open ≤ −1% below previous close |
| `rsi_threshold` | RSI crosses threshold (default: above 50) |
| `volume_spike` | Current volume > N × average volume (default 1.5×) |

Trade signal fires when `aggregate_score ≥ 0.6` AND `fired_timeframes ≥ 2`.

---

## Order Flow

```
WatchlistScanner.scan_watchlist()
  └─► signal found (should_trade=True)
       └─► RiskPolicy.evaluate_order_intent()  ← kill switch, max positions, etc.
            └─► AlpacaBroker.place_bracket_order()  ← entry + SL + TP in one call
                 ├─► TradeJournal row created (status=open)
                 ├─► NotificationService.trade_entered()
                 └─► PositionMonitor.check_exits()  (next cycle)
                      └─► TradeJournal updated (status=took_profit / stopped_out / closed)
                           └─► NotificationService.trade_exited()
```

---

## Notifications

Two backends, configured via DB or environment variables:

| Backend | Config vars |
|---|---|
| Webhook (Slack/Discord) | `NOTIFY_WEBHOOK_URL` |
| SMTP email | `NOTIFY_EMAIL_TO`, `NOTIFY_SMTP_*` |

Triggered on: trade entered, trade exited, bot error, kill switch toggled, daily summary.
All sends are fire-and-forget — failures are logged but never propagate to the trading loop.

---

## Environment Variables (`.env.example`)

```
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_URL=https://data.alpaca.markets
ALPACA_FEED=iex
WATCHLIST_STOCKS=AAPL,NVDA,TSLA,SPY,QQQ
WATCHLIST_CRYPTO=BTC/USD,ETH/USD
SCAN_INTERVAL_SECONDS=60
STOP_LOSS_PCT=1.0
TAKE_PROFIT_PCT=2.0
NOTIFY_WEBHOOK_URL=
NOTIFY_EMAIL_TO=
NOTIFY_SMTP_HOST=smtp.gmail.com
NOTIFY_SMTP_PORT=587
NOTIFY_SMTP_USER=
NOTIFY_SMTP_PASSWORD=
NOTIFY_SMTP_TLS=true
```

---

## Running Locally

```bash
# Backend
cd services/api
pip install -r requirements.txt
cp .env.example .env   # fill in Alpaca keys
uvicorn app.main:app --reload

# Frontend
cd apps/web
npm install
npm run dev
```

Or via Docker Compose:
```bash
docker-compose up --build
```

---

## Tests

```bash
cd services/api
pytest -q
```

92+ tests covering: broker, scanner, bot engine, analytics, notifications, stream, WS endpoints, risk, paper trading, auth.

---

## Paper vs Live Trading

The bot defaults to **paper trading** (`ALPACA_BASE_URL=https://paper-api.alpaca.markets`). Switch to live by changing to `https://api.alpaca.markets` and setting `live_trading_enabled=True` in the user's `RiskPolicy`.
