"""FastAPI router for the speed curve module.

Endpoints
---------
GET  /api/v1/speedcurve/vehicles
    List all vehicle IDs that have been seen.

GET  /api/v1/speedcurve/{vehicle_id}/status
    Current speed / position / gradient / limits snapshot.

GET  /api/v1/speedcurve/{vehicle_id}/history?limit=300
    Historical speed curve points (ring buffer).

GET  /api/v1/speedcurve/{vehicle_id}/predict?horizon_m=2000&dt_s=0.5
    Forward-simulated curve using the current driver command.

WS   /ws/speedcurve/{vehicle_id}
    Real-time streaming — see websocket.py for message format.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from app.speed_curve.recorder import speed_curve_recorder
from app.speed_curve.schemas import (
    SpeedCurveHistory,
    SpeedCurveListResponse,
    SpeedCurvePrediction,
    SpeedCurveStatus,
)
from app.speed_curve.zmq_listener import feed_from_state_store

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper — ensure recorder has data in mock mode before responding
# ---------------------------------------------------------------------------

def _ensure_data(vehicle_id: str | None = None) -> None:
    feed_from_state_store(vehicle_id)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/vehicles",
    response_model=SpeedCurveListResponse,
    summary="List tracked vehicles",
)
def list_vehicles() -> SpeedCurveListResponse:
    """Return vehicle IDs that have appeared on driver_input or train_state."""
    _ensure_data()
    vehicles = speed_curve_recorder.list_vehicles()
    return SpeedCurveListResponse(vehicles=vehicles, count=len(vehicles))


@router.get(
    "/{vehicle_id}/status",
    response_model=SpeedCurveStatus,
    summary="Current speed curve status for a vehicle",
)
def get_status(vehicle_id: str) -> SpeedCurveStatus:
    """Return the latest speed, position, gradient and control snapshot."""
    _ensure_data(vehicle_id)
    data = speed_curve_recorder.get_status(vehicle_id)
    return SpeedCurveStatus(**data)


@router.get(
    "/{vehicle_id}/history",
    response_model=SpeedCurveHistory,
    summary="Historical speed curve points",
)
def get_history(
    vehicle_id: str,
    limit: int = Query(default=300, ge=1, le=3000, description="Max points to return"),
) -> SpeedCurveHistory:
    """Return up to *limit* recent speed curve points (newest last)."""
    _ensure_data(vehicle_id)
    points = speed_curve_recorder.get_history(vehicle_id, limit=limit)
    return SpeedCurveHistory(
        vehicle_id=vehicle_id,
        count=len(points),
        points=points,
    )


@router.get(
    "/{vehicle_id}/predict",
    response_model=SpeedCurvePrediction,
    summary="Forward-simulated speed curve",
)
def get_prediction(
    vehicle_id: str,
    horizon_m: float = Query(
        default=2000.0,
        ge=10.0,
        le=10000.0,
        description="Simulation horizon in metres",
    ),
    dt_s: float = Query(
        default=0.5,
        ge=0.05,
        le=5.0,
        description="Integration step in seconds",
    ),
) -> SpeedCurvePrediction:
    """Forward-simulate the current driver command for *horizon_m* metres.

    Uses the DKZ33 motor curves, Davis running resistance, and the static
    gradient profile from ``signal_track_config``.
    """
    _ensure_data(vehicle_id)
    points_raw = speed_curve_recorder.predict(vehicle_id, horizon_m=horizon_m, dt_s=dt_s)

    from app.speed_curve.schemas import PredictedPoint
    predicted = [PredictedPoint(**p) for p in points_raw]

    logger.info(
        "SpeedCurve predict: vehicle_id=%s horizon_m=%.0f dt_s=%.2f steps=%d",
        vehicle_id,
        horizon_m,
        dt_s,
        len(predicted),
    )
    return SpeedCurvePrediction(
        vehicle_id=vehicle_id,
        horizon_m=horizon_m,
        dt_s=dt_s,
        step_count=len(predicted),
        points=predicted,
    )


# ---------------------------------------------------------------------------
# WebSocket endpoint — registered via websocket_router.py at app level
# (see backend/app/speed_curve/websocket_router.py and backend/main.py)
# ---------------------------------------------------------------------------
# The WS route is:  ws://host:8000/ws/speedcurve/{vehicle_id}
