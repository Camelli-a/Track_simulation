"""Thin ZMQ subscriber that feeds driver_input / train_state into SpeedCurveRecorder.

Design rationale
----------------
The project already has a ``ZmqDashboardListener`` (data_flow/zmq_listener.py)
that handles all incoming ZMQ messages.  Rather than opening a second socket
(which would require a separate SUB connection and risk missed messages on a
non-broker setup), this listener extends the existing dispatch mechanism by
hooking into the ``ZmqDashboardListener.dispatch`` method via monkey-patching
its ``dispatch`` method at startup.

If the application is running in mock/udp mode (no ZMQ broker), the listener
still registers the hook but never receives live data; history is then populated
by :func:`feed_from_state_store` called on each API request.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict

from app.speed_curve.recorder import speed_curve_recorder

logger = logging.getLogger(__name__)

_hooked = False


def _vehicle_id_from_data(data: Dict[str, Any]) -> str | None:
    value = (
        data.get("vehicle_id")
        or data.get("train_id")
        or data.get("id")
        or data.get("vehicleId")
    )
    return str(value) if value else None


def attach_to_zmq_listener() -> None:
    """Monkey-patch the existing ZmqDashboardListener to also feed the recorder.

    Safe to call multiple times — only patches once.
    """
    global _hooked
    if _hooked:
        return

    try:
        from app.data_flow.zmq_listener import zmq_dashboard_listener

        _original_dispatch = zmq_dashboard_listener.dispatch

        def _patched_dispatch(message_type: str, data: Dict[str, Any]) -> None:
            # Forward to the original handler first.
            _original_dispatch(message_type, data)

            # Then feed the speed curve recorder.
            if message_type == "driver_input":
                vehicle_id = _vehicle_id_from_data(data)
                if vehicle_id:
                    speed_curve_recorder.on_driver_input(vehicle_id, data)

            elif message_type == "train_state":
                vehicle_id = _vehicle_id_from_data(data)
                if vehicle_id:
                    speed_curve_recorder.on_train_state(vehicle_id, data)

        zmq_dashboard_listener.dispatch = _patched_dispatch  # type: ignore[method-assign]
        _hooked = True
        logger.info("SpeedCurve ZMQ listener hooked into ZmqDashboardListener.dispatch")

    except Exception:
        logger.exception("Failed to attach SpeedCurve ZMQ listener — no live data will be recorded")


def feed_from_state_store(vehicle_id: str | None = None) -> None:
    """One-shot sync from state_store → recorder (used in mock/polling mode).

    This ensures the REST endpoints return useful data even when no ZMQ
    messages have been dispatched yet (e.g., mock mode driven by the
    dashboard snapshot).
    """
    try:
        from app.data_flow.state_store import state_store

        snapshot = state_store.get_snapshot()
        now = time.time()

        for train in snapshot.trains:
            vid = train.vehicle_id
            if vehicle_id is not None and vid != vehicle_id:
                continue

            train_data: Dict[str, Any] = {
                "vehicle_id": vid,
                "position": train.position,
                "speed": train.speed,          # km/h in snapshot
                "speed_ms": train.speed / 3.6 if train.speed else 0.0,
                "acceleration": train.acceleration,
                "traction_level": train.traction_level or 0,
                "brake_level": train.brake_level or 0,
                "traction_percent": train.traction_percent or 0.0,
                "brake_percent": train.brake_percent or 0.0,
                "emergency_brake": train.emergency_brake,
                "timestamp": now,
                "source": "mock",
            }
            speed_curve_recorder.on_train_state(vid, train_data)

        for di in snapshot.driver_inputs:
            vid = di.vehicle_id
            if vehicle_id is not None and vid != vehicle_id:
                continue

            driver_data: Dict[str, Any] = {
                "vehicle_id": vid,
                "traction_level": di.traction_level,
                "brake_level": di.brake_level,
                "traction_percent": di.traction_percent,
                "brake_percent": di.brake_percent,
                "emergency_button": di.emergency_button,
                "control_mode": di.control_mode,
                "timestamp": now,
                "source": "mock",
            }
            speed_curve_recorder.on_driver_input(vid, driver_data)

    except Exception:
        logger.debug("feed_from_state_store failed (non-critical)", exc_info=True)
