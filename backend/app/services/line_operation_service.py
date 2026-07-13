from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from app.data_flow.message_publisher import publish_module_message
from app.data_flow.state_store import state_store
from app.schemas.vehicle import VehicleManagementRequest


ManageVehicleCallback = Callable[[VehicleManagementRequest], Any]
Direction = Literal["up", "down"]


@dataclass
class LineOperationConfig:
    headway_sec: float = 6.0
    max_active_trains: int = 12
    dwell_sec: float = 2.0
    min_train_spacing_m: float = 550.0
    start_index_up: int = 2000
    start_index_down: int = 3000


@dataclass
class LineTrainRuntime:
    vehicle_id: str
    train_index: int
    direction: Direction
    route_id: str
    start_position_m: float
    target_station_index: int | None
    created_at: float
    last_command_at: float = 0.0
    initial_state_until: float = 0.0
    dwell_station_index: int | None = None
    dwell_started_at: float | None = None
    last_departed_station_index: int | None = None


@dataclass
class PendingLineTrain:
    vehicle_id: str | None
    train_index: int | None
    direction: Direction
    requested_at: float


class LineOperationService:
    """Continuous full-line operation: endpoint departure, station stop sequence, exit."""

    def __init__(self) -> None:
        self.config = LineOperationConfig()
        self.active = False
        self._task: asyncio.Task | None = None
        self._manage_vehicle: ManageVehicleCallback | None = None
        self._trains: dict[str, LineTrainRuntime] = {}
        self._last_spawn_at = 0.0
        self._next_direction: Direction = "up"
        self._next_up_index = self.config.start_index_up
        self._next_down_index = self.config.start_index_down
        self._pending_trains: list[PendingLineTrain] = []
        self._line: dict[str, Any] = {}
        self._stations: list[dict[str, Any]] = []

    async def start(
        self,
        manage_vehicle: ManageVehicleCallback,
        config: LineOperationConfig | None = None,
    ) -> dict[str, Any]:
        self._manage_vehicle = manage_vehicle
        if config is not None:
            self.config = config
            self._next_up_index = max(self._next_up_index, config.start_index_up)
            self._next_down_index = max(self._next_down_index, config.start_index_down)
        self._line = self._load_line_layout()
        self._stations = sorted(
            list(self._line.get("stations") or []),
            key=lambda item: float(item.get("position", 0.0) or 0.0),
        )
        self.active = True
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())
        return self.status()

    async def stop(self) -> dict[str, Any]:
        self.active = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        for vehicle_id in list(self._trains):
            self._remove_train(vehicle_id)
        self._trains.clear()
        self._pending_trains.clear()
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "config": self.config.__dict__,
            "line_id": self._line.get("line_id", "LINE-1"),
            "total_length_m": self._operation_end_m(),
            "station_count": len(self._stations),
            "active_trains": [
                {
                    "vehicle_id": item.vehicle_id,
                    "train_index": item.train_index,
                    "direction": item.direction,
                    "route_id": item.route_id,
                    "target_station_index": item.target_station_index,
                    "target_station": self._station_name(item.target_station_index),
                }
                for item in self._trains.values()
            ],
            "pending_trains": [
                {
                    "vehicle_id": item.vehicle_id,
                    "train_index": item.train_index,
                    "direction": item.direction,
                    "requested_at": item.requested_at,
                }
                for item in self._pending_trains
            ],
        }

    def enqueue_train(
        self,
        *,
        vehicle_id: str | None = None,
        train_index: int | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        if not self.active:
            return {
                "ok": False,
                "reason": "line_operation_not_active",
                "vehicle_id": vehicle_id,
                "train_index": train_index,
            }
        if len(self._trains) + len(self._pending_trains) >= self.config.max_active_trains:
            return {
                "ok": False,
                "reason": "line_operation_queue_full",
                "vehicle_id": vehicle_id,
                "train_index": train_index,
            }

        direction = self._next_direction
        self._next_direction = "down" if self._next_direction == "up" else "up"
        pending = PendingLineTrain(
            vehicle_id=vehicle_id,
            train_index=train_index,
            direction=direction,
            requested_at=now,
        )
        if self._endpoint_clear(direction):
            runtime = self._spawn_train(
                direction,
                now,
                vehicle_id=vehicle_id,
                train_index=train_index,
            )
            if runtime is not None:
                self._last_spawn_at = now
                return {
                    "ok": True,
                    "queued": False,
                    "vehicle_id": runtime.vehicle_id,
                    "train_index": runtime.train_index,
                    "direction": runtime.direction,
                    "route_id": runtime.route_id,
                }

        self._pending_trains.append(pending)
        return {
            "ok": True,
            "queued": True,
            "vehicle_id": vehicle_id,
            "train_index": train_index,
            "direction": direction,
            "reason": "endpoint_not_clear_waiting_for_ato_queue",
        }

    def forget_train(self, vehicle_id: str) -> None:
        self._trains.pop(str(vehicle_id), None)
        self._pending_trains = [
            item
            for item in self._pending_trains
            if item.vehicle_id != str(vehicle_id)
        ]

    async def _run_loop(self) -> None:
        while self.active:
            try:
                self._tick()
            except Exception as exc:  # pragma: no cover - defensive background guard
                print(f"[line_operation] tick failed: {exc}")
            await asyncio.sleep(0.5)

    def _tick(self) -> None:
        now = time.time()
        self._spawn_if_needed(now)
        snapshot = state_store.get_snapshot()
        train_by_id = {train.vehicle_id: train for train in snapshot.trains}

        for vehicle_id, runtime in list(self._trains.items()):
            train = train_by_id.get(vehicle_id)
            if train is None:
                continue
            position = float(train.position)
            if now <= runtime.initial_state_until and self._position_looks_uninitialized(position, runtime):
                position = runtime.start_position_m

            target_index = self._select_target_station(runtime, train, position, now)
            runtime.target_station_index = target_index
            if target_index is None:
                if now <= runtime.initial_state_until:
                    fallback_index = self._resolve_next_station_index(
                        runtime.start_position_m,
                        runtime.direction,
                    )
                    if fallback_index is not None:
                        runtime.target_station_index = fallback_index
                        self._publish_stop_target(
                            runtime,
                            fallback_index,
                            now,
                            include_position=True,
                        )
                        continue
                if self._past_terminal(position, runtime.direction):
                    self._remove_train(vehicle_id)
                    self._trains.pop(vehicle_id, None)
                else:
                    self._publish_clear_stop_target(runtime, now)
                continue
            self._publish_stop_target(
                runtime,
                target_index,
                now,
                include_position=now <= runtime.initial_state_until,
            )

    def _select_target_station(
        self,
        runtime: LineTrainRuntime,
        train: Any,
        position: float,
        now: float,
    ) -> int | None:
        current_target = runtime.target_station_index
        if current_target is None:
            current_target = self._resolve_next_station_index(
                position,
                runtime.direction,
                after_index=runtime.last_departed_station_index,
            )

        if current_target is None:
            runtime.dwell_station_index = None
            runtime.dwell_started_at = None
            return None

        if self._is_at_station_target(train, position, runtime.direction, current_target):
            if runtime.dwell_station_index != current_target:
                runtime.dwell_station_index = current_target
                runtime.dwell_started_at = now
                return current_target

            dwell_started_at = runtime.dwell_started_at or now
            if now - dwell_started_at < max(0.0, float(self.config.dwell_sec)):
                return current_target

            runtime.last_departed_station_index = current_target
            runtime.dwell_station_index = None
            runtime.dwell_started_at = None
            return self._resolve_next_station_index(
                position,
                runtime.direction,
                after_index=current_target,
            )

        if runtime.dwell_station_index is not None:
            runtime.dwell_station_index = None
            runtime.dwell_started_at = None

        return self._resolve_next_station_index(
            position,
            runtime.direction,
            after_index=runtime.last_departed_station_index,
        )

    def _is_at_station_target(
        self,
        train: Any,
        position: float,
        direction: Direction,
        station_index: int,
    ) -> bool:
        if station_index < 0 or station_index >= len(self._stations):
            return False
        station_position = float(self._stations[station_index].get("position", 0.0) or 0.0)
        speed_kmh = self._train_speed_kmh(train)
        signed_distance = (station_position - position) * self._direction_sign(direction)
        return abs(signed_distance) <= 8.0 and speed_kmh <= 1.5

    def _spawn_if_needed(self, now: float) -> None:
        if self._manage_vehicle is None or not self._stations:
            return
        if len(self._trains) >= self.config.max_active_trains:
            return

        if self._pending_trains:
            pending = self._pending_trains[0]
            if self._endpoint_clear(pending.direction):
                runtime = self._spawn_train(
                    pending.direction,
                    now,
                    vehicle_id=pending.vehicle_id,
                    train_index=pending.train_index,
                )
                if runtime is not None:
                    self._pending_trains.pop(0)
                    self._last_spawn_at = now
                return

        if self._last_spawn_at and now - self._last_spawn_at < self.config.headway_sec:
            return

        for _ in range(2):
            direction = self._next_direction
            self._next_direction = "down" if self._next_direction == "up" else "up"
            if self._endpoint_clear(direction):
                if self._spawn_train(direction, now) is not None:
                    self._last_spawn_at = now
                return

    def _spawn_train(
        self,
        direction: Direction,
        now: float,
        *,
        vehicle_id: str | None = None,
        train_index: int | None = None,
    ) -> LineTrainRuntime | None:
        if self._manage_vehicle is None:
            return None
        if direction == "up":
            if train_index is None:
                train_index = self._next_up_index
                self._next_up_index += 1
            else:
                self._next_up_index = max(self._next_up_index, int(train_index) + 1)
            start_position = self._operation_start_m()
            route_id = "LINE-UP"
        else:
            if train_index is None:
                train_index = self._next_down_index
                self._next_down_index += 1
            else:
                self._next_down_index = max(self._next_down_index, int(train_index) + 1)
            start_position = self._operation_end_m()
            route_id = "LINE-DOWN"

        vehicle_id = vehicle_id or f"TRAIN-{train_index}"
        response = self._manage_vehicle(
            VehicleManagementRequest(
                type="add_train",
                vehicle_id=vehicle_id,
                train_index=train_index,
                position=start_position,
            )
        )
        if not getattr(response, "ok", False):
            return None

        runtime = LineTrainRuntime(
            vehicle_id=vehicle_id,
            train_index=train_index,
            direction=direction,
            route_id=route_id,
            start_position_m=start_position,
            target_station_index=self._resolve_next_station_index(start_position, direction),
            created_at=now,
            initial_state_until=now + 5.0,
        )
        self._trains[vehicle_id] = runtime
        if runtime.target_station_index is not None:
            self._publish_stop_target(
                runtime,
                runtime.target_station_index,
                now,
                force=True,
                include_position=True,
            )
        return runtime

    def _endpoint_clear(self, direction: Direction) -> bool:
        endpoint = self._operation_start_m() if direction == "up" else self._operation_end_m()
        route_id = "LINE-UP" if direction == "up" else "LINE-DOWN"
        snapshot = state_store.get_snapshot()
        train_by_id = {train.vehicle_id: train for train in snapshot.trains}
        min_spacing = max(200.0, float(self.config.min_train_spacing_m))
        for runtime in self._trains.values():
            if runtime.direction != direction:
                continue
            train = train_by_id.get(runtime.vehicle_id)
            position = (
                runtime.start_position_m
                if train is None
                else float(train.position)
            )
            if direction == "up" and position < endpoint + min_spacing:
                return False
            if direction == "down" and position > endpoint - min_spacing:
                return False
        for train in snapshot.trains:
            if getattr(train, "route_id", None) != route_id:
                continue
            if abs(float(train.position) - endpoint) < min_spacing:
                return False
        return True

    def _publish_stop_target(
        self,
        runtime: LineTrainRuntime,
        station_index: int,
        now: float,
        *,
        force: bool = False,
        include_position: bool = False,
    ) -> None:
        if not force and now - runtime.last_command_at < 1.0:
            return
        station = self._stations[station_index]
        payload = {
            "vehicle_id": runtime.vehicle_id,
            "driving_mode": "AM",
            "mode": "ato",
            "direction_code": 1 if runtime.direction == "up" else -1,
            "route_id": runtime.route_id,
            "stop_target_m": float(station.get("position", 0.0) or 0.0),
            "line_id": self._line.get("line_id", "LINE-1"),
            "target_station_id": station.get("station_id"),
            "target_station_name": station.get("station_name") or station.get("name"),
            "operation_direction": runtime.direction,
            "reason": "line_operation_stop_sequence",
            "updated_at": now,
        }
        if include_position:
            payload["position"] = runtime.start_position_m
        publish_module_message("set_train_state", payload)
        runtime.last_command_at = now

    def _position_looks_uninitialized(
        self,
        position: float,
        runtime: LineTrainRuntime,
    ) -> bool:
        if runtime.direction == "down":
            return position <= self._operation_start_m() - 20.0
        return position >= self._operation_end_m() + 20.0

    def _publish_clear_stop_target(self, runtime: LineTrainRuntime, now: float) -> None:
        if now - runtime.last_command_at < 1.0:
            return
        publish_module_message(
            "set_train_state",
            {
                "vehicle_id": runtime.vehicle_id,
                "driving_mode": "AM",
                "mode": "ato",
                "direction_code": 1 if runtime.direction == "up" else -1,
                "route_id": runtime.route_id,
                "clear_stop_target": True,
                "reason": "line_operation_between_targets",
                "updated_at": now,
            },
        )
        runtime.last_command_at = now

    def _resolve_next_station_index(
        self,
        position: float,
        direction: Direction,
        *,
        after_index: int | None = None,
    ) -> int | None:
        margin_m = 5.0
        if direction == "up":
            start_index = 0 if after_index is None else max(0, after_index + 1)
            for index in range(start_index, len(self._stations)):
                station = self._stations[index]
                if float(station.get("position", 0.0) or 0.0) > position + margin_m:
                    return index
            return None

        start_index = (
            len(self._stations) - 1
            if after_index is None
            else min(len(self._stations) - 1, after_index - 1)
        )
        for index in range(start_index, -1, -1):
            station_position = float(self._stations[index].get("position", 0.0) or 0.0)
            if station_position < position - margin_m:
                return index
        return None

    def _train_speed_kmh(self, train: Any) -> float:
        for attr in ("speed_kmh", "vehicle_speed_kmh"):
            value = getattr(train, attr, None)
            if value is not None:
                try:
                    return abs(float(value))
                except (TypeError, ValueError):
                    pass
        return abs(float(getattr(train, "speed", 0.0) or 0.0)) * 3.6

    def _direction_sign(self, direction: Direction) -> int:
        return 1 if direction == "up" else -1

    def _past_terminal(self, position: float, direction: Direction) -> bool:
        if direction == "up":
            return position >= self._operation_end_m() + 20.0
        return position <= self._operation_start_m() - 20.0

    def _remove_train(self, vehicle_id: str) -> None:
        if self._manage_vehicle is None:
            return
        self._manage_vehicle(VehicleManagementRequest(type="remove_train", vehicle_id=vehicle_id))

    def _station_name(self, index: int | None) -> str | None:
        if index is None or index < 0 or index >= len(self._stations):
            return None
        station = self._stations[index]
        return station.get("station_name") or station.get("name")

    def _line_end_m(self) -> float:
        value = self._line.get("total_length_m")
        if value is not None:
            return float(value)
        if self._stations:
            return max(float(item.get("position", 0.0) or 0.0) for item in self._stations)
        return 0.0

    def _operation_start_m(self) -> float:
        if self._stations:
            return min(float(item.get("position", 0.0) or 0.0) for item in self._stations)
        return 0.0

    def _operation_end_m(self) -> float:
        if self._stations:
            return max(float(item.get("position", 0.0) or 0.0) for item in self._stations)
        return self._line_end_m()

    @staticmethod
    def _load_line_layout() -> dict[str, Any]:
        path = LineOperationService._project_root() / "frontend" / "public" / "data" / "line-layout.json"
        if not path.exists():
            return {"line_id": "LINE-1", "total_length_m": 0.0, "stations": []}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2].parent


line_operation_service = LineOperationService()
