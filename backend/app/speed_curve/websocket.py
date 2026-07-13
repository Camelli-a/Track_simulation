"""WebSocket endpoint for real-time speed curve streaming.

Clients connect to:
    ws://host:8000/ws/speedcurve/{vehicle_id}

Every *push_interval_s* seconds the server sends the latest SpeedPoint as JSON.
On connect, it first sends the last *initial_history* points as a batch so the
client can render the existing curve immediately.

Message types sent to the client:
    {"type": "history",  "vehicle_id": "...", "points": [...]}   — on connect
    {"type": "point",    "vehicle_id": "...", "point": {...}}     — each tick
    {"type": "ping",     "ts": <float>}                          — keepalive
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from app.speed_curve.recorder import speed_curve_recorder
from app.speed_curve.zmq_listener import feed_from_state_store

logger = logging.getLogger(__name__)

PUSH_INTERVAL_S: float = 0.2      # 5 Hz
INITIAL_HISTORY_COUNT: int = 300  # send last N points on connect
KEEPALIVE_INTERVAL_S: float = 10.0


async def speed_curve_ws_handler(
    websocket: WebSocket,
    vehicle_id: str,
    push_interval_s: float = PUSH_INTERVAL_S,
    initial_history: int = INITIAL_HISTORY_COUNT,
) -> None:
    """Handle one WebSocket connection for *vehicle_id*."""
    await websocket.accept()
    logger.info("SpeedCurve WS connected: vehicle_id=%s", vehicle_id)

    # Send historical batch first
    history = speed_curve_recorder.get_history(vehicle_id, limit=initial_history)
    await websocket.send_text(json.dumps({
        "type": "history",
        "vehicle_id": vehicle_id,
        "count": len(history),
        "points": [p.model_dump() for p in history],
    }))

    last_ts: Optional[float] = history[-1].timestamp if history else None
    last_ping = time.time()

    try:
        while True:
            await asyncio.sleep(push_interval_s)

            # Pull latest data into recorder (helps in mock mode)
            feed_from_state_store(vehicle_id)

            now = time.time()

            # Keepalive ping
            if now - last_ping >= KEEPALIVE_INTERVAL_S:
                await websocket.send_text(json.dumps({"type": "ping", "ts": now}))
                last_ping = now

            # Get new points since last sent
            all_points = speed_curve_recorder.get_history(vehicle_id, limit=initial_history)
            new_points = [
                p for p in all_points
                if last_ts is None or p.timestamp > last_ts
            ]

            for point in new_points:
                await websocket.send_text(json.dumps({
                    "type": "point",
                    "vehicle_id": vehicle_id,
                    "point": point.model_dump(),
                }))
                last_ts = point.timestamp

    except WebSocketDisconnect:
        logger.info("SpeedCurve WS disconnected: vehicle_id=%s", vehicle_id)
    except Exception:
        logger.exception("SpeedCurve WS error: vehicle_id=%s", vehicle_id)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
