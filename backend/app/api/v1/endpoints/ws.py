"""WebSocket 实时推送：协议 v1.0 dashboard_snapshot + 旧版 tick 兼容。"""
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.simulation_service import simulation_service

router = APIRouter()
TICK_INTERVAL = 0.2
_active_dashboard_clients = 0


@router.websocket("/dashboard")
async def dashboard_ws(websocket: WebSocket) -> None:
    global _active_dashboard_clients
    await websocket.accept()
    _active_dashboard_clients += 1
    try:
        while True:
            snapshot = simulation_service.next_dashboard_snapshot(
                TICK_INTERVAL,
                websocket_clients=_active_dashboard_clients,
            )
            await websocket.send_json(snapshot.model_dump())
            await asyncio.sleep(TICK_INTERVAL)
    except WebSocketDisconnect:
        pass
    finally:
        _active_dashboard_clients = max(0, _active_dashboard_clients - 1)


@router.websocket("/simulation")
async def simulation_ws(websocket: WebSocket) -> None:
    """旧版 tick 格式，过渡期保留。"""
    await websocket.accept()
    try:
        while True:
            tick = simulation_service.next_tick(TICK_INTERVAL)
            await websocket.send_json(tick.model_dump())
            await asyncio.sleep(TICK_INTERVAL)
    except WebSocketDisconnect:
        pass
