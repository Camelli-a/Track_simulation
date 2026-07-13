"""SpeedCurveRecorder — per-vehicle ring buffer that aggregates ZMQ messages.

Data pipeline:
  ZmqDashboardListener  (existing)
      │  driver_input  →  traction_percent / brake_percent / emergency_brake
      │  train_state   →  position / speed_ms / acceleration
      ▼
  SpeedCurveRecorder.on_driver_input()
  SpeedCurveRecorder.on_train_state()
      │  merges latest snapshot → SpeedPoint
      │  appends to ring buffer
      ▼
  /api/v1/speedcurve/{vehicle_id}/history   (REST)
  ws://…/ws/speedcurve/{vehicle_id}         (WebSocket push)

The recorder is intentionally lightweight: it does NOT own ZMQ sockets.
The ZmqListener (or a thin wrapper) calls the public on_* methods.
"""
from __future__ import annotations

import time
from collections import deque
from threading import RLock
from typing import Deque, Dict, List, Optional

from app.speed_curve.schemas import SpeedPoint
from app.speed_curve.track_info import get_gradient_at, get_speed_limit_at
from app.vehicle_sim.dynamics import update_dynamics


# Maximum history points per vehicle (≈300 s at 100 ms tick)
MAX_HISTORY = 3000
# Minimum gap between consecutive recorded points (seconds)
MIN_RECORD_INTERVAL_S = 0.05


class _VehicleState:
    """Mutable state cache for one tracked vehicle."""

    __slots__ = (
        "vehicle_id",
        "position_m",
        "speed_ms",
        "acceleration_mps2",
        "traction_level",
        "brake_level",
        "traction_percent",
        "brake_percent",
        "emergency_brake",
        "control_mode",
        "last_update_at",
        "last_recorded_at",
        "source",
    )

    def __init__(self, vehicle_id: str) -> None:
        self.vehicle_id = vehicle_id
        self.position_m: float = 0.0
        self.speed_ms: float = 0.0
        self.acceleration_mps2: float = 0.0
        self.traction_level: int = 0
        self.brake_level: int = 0
        self.traction_percent: float = 0.0
        self.brake_percent: float = 0.0
        self.emergency_brake: bool = False
        self.control_mode: str = "manual"
        self.last_update_at: Optional[float] = None
        self.last_recorded_at: Optional[float] = None
        self.source: str = "zmq"


class SpeedCurveRecorder:
    """Thread-safe recorder that aggregates driver_input and train_state messages.

    One instance is typically shared for all vehicles.  A per-vehicle ring buffer
    stores historical :class:`SpeedPoint` objects.
    """

    def __init__(self, max_history: int = MAX_HISTORY) -> None:
        self._max_history = max_history
        self._lock = RLock()
        # vehicle_id → ring buffer
        self._history: Dict[str, Deque[SpeedPoint]] = {}
        # vehicle_id → mutable state
        self._states: Dict[str, _VehicleState] = {}

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def on_driver_input(self, vehicle_id: str, data: dict) -> None:
        """Called whenever a *driver_input* message arrives from ZMQ."""
        with self._lock:
            state = self._get_or_create(vehicle_id)
            state.traction_level = int(data.get("traction_level", 0))
            state.brake_level = int(data.get("brake_level", 0))
            state.traction_percent = float(data.get("traction_percent", 0.0))
            state.brake_percent = float(data.get("brake_percent", 0.0))
            state.emergency_brake = bool(data.get("emergency_button", False))
            state.control_mode = str(data.get("control_mode", "manual"))
            state.source = str(data.get("source", "zmq"))
            state.last_update_at = float(data.get("timestamp", time.time()))
            # driver_input alone is not enough to record a point — wait for
            # a matching train_state that gives us the authoritative position/speed.

    def on_train_state(self, vehicle_id: str, data: dict) -> None:
        """Called whenever a *train_state* message arrives from ZMQ."""
        with self._lock:
            state = self._get_or_create(vehicle_id)

            # Speed: prefer m/s field, fall back to km/h ÷ 3.6
            speed_ms: float = 0.0
            if "speed_ms" in data or "speed_mps" in data:
                speed_ms = float(data.get("speed_ms") or data.get("speed_mps") or 0.0)
            elif "speed" in data:
                speed_ms = float(data.get("speed", 0.0)) / 3.6
            elif "speed_kmh" in data:
                speed_ms = float(data.get("speed_kmh", 0.0)) / 3.6

            state.position_m = float(data.get("position") or data.get("position_m") or 0.0)
            state.speed_ms = speed_ms
            state.acceleration_mps2 = float(data.get("acceleration") or data.get("acceleration_mps2") or 0.0)

            # If train_state also carries traction/brake info, update those too
            if "traction_percent" in data:
                state.traction_percent = float(data["traction_percent"])
            if "brake_percent" in data:
                state.brake_percent = float(data["brake_percent"])
            if "traction_level" in data:
                state.traction_level = int(data["traction_level"])
            if "brake_level" in data:
                state.brake_level = int(data["brake_level"])
            if "emergency_brake" in data:
                state.emergency_brake = bool(data["emergency_brake"])

            now = float(data.get("timestamp", time.time()))
            state.last_update_at = now
            state.source = str(data.get("source", state.source))

            self._try_record(vehicle_id, state, now)

    # ------------------------------------------------------------------
    # Public query API
    # ------------------------------------------------------------------

    def get_history(self, vehicle_id: str, limit: int = MAX_HISTORY) -> List[SpeedPoint]:
        """Return the most recent *limit* recorded points for *vehicle_id*."""
        with self._lock:
            buf = self._history.get(vehicle_id)
            if buf is None:
                return []
            points = list(buf)
            if limit < len(points):
                return points[-limit:]
            return points

    def get_status(self, vehicle_id: str) -> dict:
        """Return a status dict (used to build :class:`SpeedCurveStatus`)."""
        with self._lock:
            state = self._states.get(vehicle_id)
            buf = self._history.get(vehicle_id, deque())
            if state is None:
                return {
                    "vehicle_id": vehicle_id,
                    "connected": False,
                    "last_update_at": None,
                    "history_count": 0,
                }
            gradient = get_gradient_at(state.position_m)
            limit = get_speed_limit_at(state.position_m)
            return {
                "vehicle_id": vehicle_id,
                "connected": state.last_update_at is not None,
                "last_update_at": state.last_update_at,
                "history_count": len(buf),
                "current_speed_kmh": round(state.speed_ms * 3.6, 3),
                "current_position_m": round(state.position_m, 3),
                "current_acceleration_mps2": round(state.acceleration_mps2, 3),
                "current_traction_percent": round(state.traction_percent, 2),
                "current_brake_percent": round(state.brake_percent, 2),
                "current_gradient_permille": gradient,
                "current_speed_limit_kmh": limit,
                "emergency_brake": state.emergency_brake,
                "control_mode": state.control_mode,
            }

    def list_vehicles(self) -> List[str]:
        """Return the list of vehicle IDs that have been seen."""
        with self._lock:
            return list(self._states.keys())

    def predict(
        self,
        vehicle_id: str,
        horizon_m: float = 2000.0,
        dt_s: float = 0.5,
    ) -> list:
        """Forward-simulate the current driver command for *horizon_m* metres.

        Returns a list of dicts suitable for :class:`PredictedPoint`.
        """
        with self._lock:
            state = self._states.get(vehicle_id)
            if state is None:
                return []
            speed_ms = state.speed_ms
            position = state.position_m
            traction_level = state.traction_level
            brake_level = state.brake_level
            traction_percent = state.traction_percent
            brake_percent = state.brake_percent
            emergency = state.emergency_brake

        points = []
        start_pos = position
        max_steps = max(1, int(horizon_m / max(0.1, speed_ms * dt_s + 0.1)) + 500)

        for _ in range(max_steps):
            gradient = get_gradient_at(position)
            limit = get_speed_limit_at(position)

            try:
                new_speed_ms, new_pos, accel, trac_f, brake_f = update_dynamics(
                    speed_ms=speed_ms,
                    position=position,
                    traction_level=traction_level,
                    brake_level=brake_level,
                    gradient=gradient,
                    dt=dt_s,
                    emergency_brake=emergency,
                    traction_percent=traction_percent if traction_percent > 0 else None,
                    brake_percent=brake_percent if brake_percent > 0 else None,
                )
            except Exception:
                break

            points.append({
                "position_m": round(new_pos, 3),
                "speed_kmh": round(new_speed_ms * 3.6, 3),
                "speed_ms": round(new_speed_ms, 4),
                "acceleration_mps2": round(accel, 4),
                "gradient_permille": gradient,
                "speed_limit_kmh": limit,
                "traction_force_n": round(trac_f, 1),
                "brake_force_n": round(brake_f, 1),
            })

            speed_ms = new_speed_ms
            position = new_pos

            if abs(new_pos - start_pos) >= horizon_m:
                break
            if new_speed_ms <= 0.0:
                break

        return points

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create(self, vehicle_id: str) -> _VehicleState:
        if vehicle_id not in self._states:
            self._states[vehicle_id] = _VehicleState(vehicle_id)
            self._history[vehicle_id] = deque(maxlen=self._max_history)
        return self._states[vehicle_id]

    def _try_record(self, vehicle_id: str, state: _VehicleState, now: float) -> None:
        """Append a SpeedPoint to the ring buffer if enough time has passed."""
        last = state.last_recorded_at
        if last is not None and (now - last) < MIN_RECORD_INTERVAL_S:
            return

        gradient = get_gradient_at(state.position_m)
        limit = get_speed_limit_at(state.position_m)

        from app.vehicle_sim.dynamics import (
            calc_traction_force_percent,
            calc_brake_force_percent,
        )
        try:
            trac_f = calc_traction_force_percent(state.traction_percent, state.speed_ms)
            brake_f = calc_brake_force_percent(state.brake_percent, state.speed_ms)
        except Exception:
            trac_f = 0.0
            brake_f = 0.0

        point = SpeedPoint(
            timestamp=now,
            position_m=round(state.position_m, 3),
            speed_kmh=round(state.speed_ms * 3.6, 3),
            speed_ms=round(state.speed_ms, 4),
            acceleration_mps2=round(state.acceleration_mps2, 4),
            traction_level=state.traction_level,
            brake_level=state.brake_level,
            traction_percent=round(state.traction_percent, 2),
            brake_percent=round(state.brake_percent, 2),
            traction_force_n=round(trac_f, 1),
            brake_force_n=round(brake_f, 1),
            gradient_permille=gradient,
            speed_limit_kmh=limit,
            emergency_brake=state.emergency_brake,
            control_mode=state.control_mode,  # type: ignore[arg-type]
            source=state.source,
        )

        self._history[vehicle_id].append(point)
        state.last_recorded_at = now


# Module-level singleton shared by the listener and the API router.
speed_curve_recorder = SpeedCurveRecorder()
