"""
Alpaca WebSocket market-data stream.

Connects to wss://stream.data.alpaca.markets/v2/{feed} (stocks) or
wss://stream.data.alpaca.markets/v1beta3/crypto/us (crypto), subscribes to
the configured watchlist, and fans live price ticks out to all registered
WebSocket client queues.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Registry of active asyncio queues — one per connected browser client
_queues: list[asyncio.Queue] = []


def register_queue(q: asyncio.Queue) -> None:
    _queues.append(q)


def unregister_queue(q: asyncio.Queue) -> None:
    try:
        _queues.remove(q)
    except ValueError:
        pass


async def _broadcast(msg: dict) -> None:
    dead: list[asyncio.Queue] = []
    for q in list(_queues):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        unregister_queue(q)


async def run_stream(api_key: str, secret_key: str, symbols_stocks: list[str], symbols_crypto: list[str], feed: str = "iex") -> None:
    """
    Long-running coroutine that connects to Alpaca WebSocket and re-fans ticks.
    Designed to be run as a background asyncio task.
    Reconnects automatically on disconnect.
    """
    import websockets

    tasks = []
    if symbols_stocks:
        tasks.append(_stream_feed(api_key, secret_key, symbols_stocks, feed, "stock"))
    if symbols_crypto:
        tasks.append(_stream_feed(api_key, secret_key, symbols_crypto, "crypto", "crypto"))

    if tasks:
        await asyncio.gather(*tasks)


async def _stream_feed(api_key: str, secret_key: str, symbols: list[str], feed: str, asset_class: str) -> None:
    if asset_class == "crypto":
        url = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"
    else:
        url = f"wss://stream.data.alpaca.markets/v2/{feed}"

    backoff = 2
    while True:
        try:
            import websockets
            async with websockets.connect(url, ping_interval=20) as ws:
                backoff = 2  # reset on successful connect

                # Authenticate
                await ws.send(json.dumps({"action": "auth", "key": api_key, "secret": secret_key}))
                auth_resp = json.loads(await ws.recv())
                logger.info("Alpaca WS auth: %s", auth_resp)

                # Subscribe to quotes
                await ws.send(json.dumps({"action": "subscribe", "quotes": symbols}))
                sub_resp = json.loads(await ws.recv())
                logger.info("Alpaca WS subscribed: %s", sub_resp)

                async for raw in ws:
                    messages = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode())
                    if not isinstance(messages, list):
                        messages = [messages]
                    for msg in messages:
                        if msg.get("T") == "q":  # quote update
                            bid = float(msg.get("bp", 0) or 0)
                            ask = float(msg.get("ap", 0) or 0)
                            price = round((bid + ask) / 2, 6) if bid > 0 and ask > 0 else max(bid, ask)
                            tick = {
                                "type": "tick",
                                "symbol": msg.get("S", ""),
                                "asset_class": asset_class,
                                "price": price,
                                "bid": bid,
                                "ask": ask,
                                "timestamp": datetime.now(UTC).isoformat(),
                            }
                            await _broadcast(tick)

        except Exception as exc:
            logger.warning("Alpaca WS disconnected (%s), retrying in %ds", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)


def build_tick_mock(symbol: str, price: float, asset_class: str = "stock") -> dict:
    """Build a synthetic tick for testing."""
    return {
        "type": "tick",
        "symbol": symbol,
        "asset_class": asset_class,
        "price": price,
        "bid": round(price - 0.01, 4),
        "ask": round(price + 0.01, 4),
        "timestamp": datetime.now(UTC).isoformat(),
    }
