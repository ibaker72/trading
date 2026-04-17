"""
WebSocket router — real-time market price feed for the dashboard.

GET  /ws/market  — upgrades to WebSocket; client receives JSON tick messages
                   while connected.  Falls back to mock ticks when Alpaca is
                   not configured.
GET  /ws/status  — REST endpoint returning stream connectivity info.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.market_data.stream import register_queue, unregister_queue, build_tick_mock

router = APIRouter(tags=["ws"])
logger = logging.getLogger(__name__)

# Background stream task (started lazily on first WS connection)
_stream_task: asyncio.Task | None = None
_stream_running = False


async def _ensure_stream_running() -> None:
    global _stream_task, _stream_running
    if _stream_running:
        return
    settings = get_settings()
    if not settings.alpaca_enabled:
        return  # no Alpaca — mock mode only

    stocks = [s.strip() for s in settings.watchlist_stocks.split(",") if s.strip()]
    cryptos = [s.strip() for s in settings.watchlist_crypto.split(",") if s.strip()]

    from app.market_data.stream import run_stream
    _stream_task = asyncio.create_task(
        run_stream(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            symbols_stocks=stocks,
            symbols_crypto=cryptos,
            feed=settings.alpaca_feed,
        )
    )
    _stream_running = True
    logger.info("Alpaca WebSocket stream task started")


async def _mock_tick_loop(queue: asyncio.Queue) -> None:
    """Send synthetic ticks every 5 seconds when Alpaca is not configured."""
    import random
    from app.market_data.providers.mock import MockMarketDataProvider
    provider = MockMarketDataProvider()
    while True:
        for asset in provider.list_assets():
            quote = provider.get_quote(asset.symbol, asset.asset_class)
            tick = build_tick_mock(asset.symbol, quote.price, asset.asset_class)
            try:
                queue.put_nowait(tick)
            except asyncio.QueueFull:
                pass
        await asyncio.sleep(5)


@router.websocket("/ws/market")
async def market_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = get_settings()
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    register_queue(queue)

    mock_task = None
    if not settings.alpaca_enabled:
        # Start mock tick loop for this client
        mock_task = asyncio.create_task(_mock_tick_loop(queue))
    else:
        await _ensure_stream_running()

    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(msg)
            except asyncio.TimeoutError:
                # Send a keepalive ping
                await websocket.send_json({"type": "ping"})
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        unregister_queue(queue)
        if mock_task:
            mock_task.cancel()


@router.get("/ws/status")
def ws_status() -> dict:
    settings = get_settings()
    return {
        "alpaca_configured": settings.alpaca_enabled,
        "stream_running": _stream_running,
        "connected_clients": len(
            __import__("app.market_data.stream", fromlist=["_queues"])._queues
        ),
    }
