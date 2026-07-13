from __future__ import annotations

import asyncio
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.data_flow.mock_service import mock_dashboard_service
from app.data_flow.state_store import state_store

router = APIRouter()
_active_connections: Set[WebSocket] = set()


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    _active_connections.add(websocket)
    state_store.set_websocket_clients(len(_active_connections))
    try:
        while True:
            if settings.ENABLE_DASHBOARD_MOCK:
                mock_dashboard_service.tick()
            snapshot = state_store.get_snapshot()
            await websocket.send_json(snapshot.model_dump(mode="json"))
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.discard(websocket)
        state_store.set_websocket_clients(len(_active_connections))

