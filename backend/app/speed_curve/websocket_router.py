"""Standalone WebSocket router for speed curve streaming.

Registered at app-level (not under /api/v1) to keep the WS path consistent
with the existing dashboard WS pattern:
    ws://host:8000/ws/speedcurve/{vehicle_id}
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket

from app.speed_curve.websocket import speed_curve_ws_handler

router = APIRouter()


@router.websocket("/ws/speedcurve/{vehicle_id}")
async def speed_curve_websocket(websocket: WebSocket, vehicle_id: str) -> None:
    """Real-time speed curve stream for *vehicle_id*."""
    await speed_curve_ws_handler(websocket, vehicle_id)
