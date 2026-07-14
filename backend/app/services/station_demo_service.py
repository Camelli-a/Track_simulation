from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.data_flow.message_publisher import publish_module_message
from app.data_flow.state_store import state_store
from app.schemas.vehicle import VehicleManagementRequest


ManageVehicleCallback = Callable[[VehicleManagementRequest], Any]
DEMO_TRAIN_TIMEOUT_SEC = 900.0


@dataclass
class StationDemoConfig:
    station_id: str | None = None
    station_name: str | None = None
    headway_sec: float = 10.0
    dwell_sec: float = 4.0
    max_active_trains: int = 4
    approach_distance_m: float = 450.0
    exit_distance_m: float = 1000.0
    min_train_spacing_m: float = 260.0
    cruise_speed_kmh: float = 28.0
    start_index: int = 20


@dataclass
class DemoTrainRuntime:
    vehicle_id: str
    train_index: int
    phase: str
    station_position_m: float
    approach_position_m: float
    exit_position_m: float
    created_at: float
    dwell_started_at: float | None = None
    last_command_at: float = 0.0


class StationDemoService:
    """Backend scenario: continuous station arrival-stop-departure demo."""

    def __init__(self) -> None:
        self.config = StationDemoConfig()
        self.station: dict[str, Any] | None = None
        self.active = False
        self._task: asyncio.Task | None = None
        self._manage_vehicle: ManageVehicleCallback | None = None
        self._trains: dict[str, DemoTrainRuntime] = {}
        self._last_spawn_at = 0.0
        self._next_index = self.config.start_index

    async def start(self, manage_vehicle: ManageVehicleCallback, config: StationDemoConfig | None = None) -> dict[str, Any]:
        self._manage_vehicle = manage_vehicle
        if self._trains:
            for vehicle_id in list(self._trains):
                self._remove_train(vehicle_id)
            self._trains.clear()
            self._last_spawn_at = 0.0
        if config is not None:
            self.config = config
            self._next_index = max(self._next_index, config.start_index)
        self.station = self._resolve_station(self.config)
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
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "station": self.station,
            "config": self.config.__dict__,
            "active_trains": [
                {
                    "vehicle_id": item.vehicle_id,
                    "train_index": item.train_index,
                    "phase": item.phase,
                    "station_position_m": item.station_position_m,
                    "approach_position_m": item.approach_position_m,
                    "exit_position_m": item.exit_position_m,
                    "dwell_started_at": item.dwell_started_at,
                }
                for item in self._trains.values()
            ],
        }

    async def _run_loop(self) -> None:
        while self.active:
            try:
                self._tick()
            except Exception as exc:  # pragma: no cover - defensive background guard
                print(f"[station_demo] tick failed: {exc}")
            await asyncio.sleep(1.0)

    def _tick(self) -> None:
        now = time.time()
        self._spawn_if_needed(now)
        snapshot = state_store.get_snapshot()
        train_by_id = {train.vehicle_id: train for train in snapshot.trains}

        for vehicle_id, runtime in list(self._trains.items()):
            train = train_by_id.get(vehicle_id)
            if train is None:
                continue
            if runtime.phase == "approach":
                self._ensure_onboard_ato_target(runtime, runtime.station_position_m, now)
                if abs(train.position - runtime.station_position_m) <= 2.0 and train.speed <= 1.0:
                    runtime.phase = "dwell"
                    runtime.dwell_started_at = now
            elif runtime.phase == "dwell":
                self._ensure_onboard_ato_target(runtime, runtime.station_position_m, now)
                if runtime.dwell_started_at is not None and now - runtime.dwell_started_at >= self.config.dwell_sec:
                    runtime.phase = "depart"
                    runtime.last_command_at = 0.0
                    self._clear_onboard_stop_target(runtime, now, force=True)
            elif runtime.phase == "depart":
                self._clear_onboard_stop_target(runtime, now)
                if train.position >= runtime.exit_position_m - 10.0:
                    self._remove_train(vehicle_id)
                    self._trains.pop(vehicle_id, None)

            if now - runtime.created_at > DEMO_TRAIN_TIMEOUT_SEC:
                self._remove_train(vehicle_id)
                self._trains.pop(vehicle_id, None)

    def _spawn_if_needed(self, now: float) -> None:
        if self._manage_vehicle is None or self.station is None:
            return
        if len(self._trains) >= self.config.max_active_trains:
            return
        if self._last_spawn_at and now - self._last_spawn_at < self.config.headway_sec:
            return
        if not self._station_area_clear_for_next_train():
            return

        station_position = float(self.station.get("demo_stop_position_m") or self.station["position"])
        approach_position = float(
            self.station.get("demo_approach_position_m")
            or max(0.0, station_position - self.config.approach_distance_m)
        )
        exit_position = float(
            self.station.get("demo_exit_position_m")
            or station_position + self.config.exit_distance_m
        )
        if not self._has_spawn_clearance(approach_position):
            return
        train_index = self._next_index
        self._next_index += 1
        vehicle_id = f"TRAIN-{train_index:03d}"

        response = self._manage_vehicle(
            VehicleManagementRequest(
                type="add_train",
                vehicle_id=vehicle_id,
                train_index=train_index,
                position=approach_position,
                virtual_ato=True,
            )
        )
        if not getattr(response, "ok", False):
            return

        runtime = DemoTrainRuntime(
            vehicle_id=vehicle_id,
            train_index=train_index,
            phase="approach",
            station_position_m=station_position,
            approach_position_m=approach_position,
            exit_position_m=exit_position,
            created_at=now,
        )
        self._trains[vehicle_id] = runtime
        self._last_spawn_at = now
        self._ensure_onboard_ato_target(runtime, station_position, now, force=True)

    def _has_spawn_clearance(self, approach_position: float) -> bool:
        """Avoid visually stacking demo trains at the same station entrance."""

        min_spacing = max(120.0, float(self.config.min_train_spacing_m))
        snapshot = state_store.get_snapshot()
        train_by_id = {train.vehicle_id: train for train in snapshot.trains}
        for runtime in self._trains.values():
            train = train_by_id.get(runtime.vehicle_id)
            position = float(train.position) if train is not None else runtime.approach_position_m
            if abs(position - approach_position) < min_spacing:
                return False
        return True

    def _station_area_clear_for_next_train(self) -> bool:
        if not self._trains:
            return True
        snapshot = state_store.get_snapshot()
        train_by_id = {train.vehicle_id: train for train in snapshot.trains}
        station_position = float(self.station.get("demo_stop_position_m") if self.station else 0.0)
        clear_after_m = 220.0
        for runtime in self._trains.values():
            train = train_by_id.get(runtime.vehicle_id)
            position = float(train.position) if train is not None else runtime.approach_position_m
            if runtime.phase in {"approach", "dwell"}:
                return False
            if runtime.phase == "depart" and position < station_position + clear_after_m:
                return False
        return True

    def _build_visual_context(self, runtime: DemoTrainRuntime, position: float) -> dict[str, Any]:
        """Return station-yard metadata for display only.

        Ground MA is generated by SignalZmqAdapter from train_state. These
        fields only help the frontend project the train onto the selected
        station-yard diagram; they must not be treated as movement authority.
        """

        yard_section = self._yard_section_for_position(position)
        return {
            "route_id": f"DEMO-{self.station['station_id'] if self.station else 'ST'}",
            "station_id": self.station.get("station_id") if self.station else None,
            "station_name": self.station.get("station_name") if self.station else None,
            "station_yard_section_id": yard_section.get("section_id") if yard_section else None,
            "station_yard_track_id": yard_section.get("track_id") if yard_section else None,
            "station_yard_route_section_ids": self.station.get("demo_route_section_ids") if self.station else None,
        }

    def _publish_ma(self, runtime: DemoTrainRuntime, position: float, now: float) -> None:
        """Deprecated compatibility helper.

        The station demo no longer publishes MA. Real MA comes from
        SignalZmqAdapter. Keep this method unused for older tests/tools that may
        inspect the service object.
        """
        ma_limit = runtime.exit_position_m + 300.0
        target_speed = self._target_speed_for_phase(runtime.phase)
        payload = {
            "vehicle_id": runtime.vehicle_id,
            "position": position,
            **self._build_visual_context(runtime, position),
            "ma_limit": ma_limit,
            "distance_to_ma": max(0.0, ma_limit - position),
            "permission": "allow",
            "signal_state": "green",
            "speed_limit": target_speed,
            "target_speed": target_speed,
            "allowed_speed_kmh": target_speed,
            "target_distance_m": max(0.0, ma_limit - position),
            "reason": f"station_demo_{runtime.phase}",
            "updated_at": now,
        }
        state_store.update_ma_limits([payload])
        publish_module_message("ma_state", payload)

    def _target_speed_for_phase(self, phase: str) -> float:
        if phase == "depart":
            return min(float(self.config.cruise_speed_kmh), 26.0)
        if phase == "dwell":
            return 0.0
        return min(float(self.config.cruise_speed_kmh), 28.0)

    def _yard_section_for_position(self, position: float) -> dict[str, Any] | None:
        if self.station is None:
            return None
        yard_station = self._find_yard_station(self.station)
        if yard_station is None:
            return None
        matching_sections: list[dict[str, Any]] = []
        for section in yard_station.get("sections") or []:
            section_range = self._section_range(section)
            if section_range is None:
                continue
            start, end = section_range
            if start <= position <= end:
                matching_sections.append(section)
        if not matching_sections:
            return None
        return min(
            matching_sections,
            key=lambda section: abs(
                position
                - (
                    sum(self._section_range(section) or (position, position))
                    / 2.0
                )
            ),
        )

    def _ensure_onboard_ato_target(
        self,
        runtime: DemoTrainRuntime,
        target_position: float,
        now: float,
        *,
        force: bool = False,
    ) -> None:
        if not force and now - runtime.last_command_at < 3.0:
            return
        visual_context = self._build_visual_context(runtime, target_position)
        publish_module_message(
            "set_train_state",
            {
                "vehicle_id": runtime.vehicle_id,
                "driving_mode": "AM",
                "mode": "ato",
                "stop_target_m": target_position,
                "direction_code": 1,
                **visual_context,
                "reason": f"station_demo_{runtime.phase}",
            },
        )
        runtime.last_command_at = now

    def _clear_onboard_stop_target(
        self,
        runtime: DemoTrainRuntime,
        now: float,
        *,
        force: bool = False,
    ) -> None:
        if not force and now - runtime.last_command_at < 3.0:
            return
        publish_module_message(
            "set_train_state",
            {
                "vehicle_id": runtime.vehicle_id,
                "driving_mode": "AM",
                "mode": "ato",
                "clear_stop_target": True,
                "direction_code": 1,
                **self._build_visual_context(runtime, runtime.station_position_m),
                "reason": f"station_demo_{runtime.phase}",
                "updated_at": now,
            },
        )
        runtime.last_command_at = now

    def _remove_train(self, vehicle_id: str) -> None:
        if self._manage_vehicle is None:
            return
        self._manage_vehicle(VehicleManagementRequest(type="remove_train", vehicle_id=vehicle_id))

    def _resolve_station(self, config: StationDemoConfig) -> dict[str, Any]:
        stations = self._load_stations()
        if not stations:
            return {"station_id": "DEMO-ST", "station_name": "DEMO", "name": "DEMO", "position": 1500.0}

        selected = stations[1] if len(stations) > 1 else stations[0]
        if config.station_id:
            for station in stations:
                if station.get("station_id") == config.station_id:
                    selected = station
                    break
        elif config.station_name:
            for station in stations:
                if station.get("station_name") == config.station_name or station.get("name") == config.station_name:
                    selected = station
                    break
        return self._with_yard_demo_positions(selected, config)

    @staticmethod
    def _load_stations() -> list[dict[str, Any]]:
        project_root = StationDemoService._project_root()
        path = project_root / "frontend" / "public" / "data" / "line-layout.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return list(payload.get("stations") or [])

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2].parent

    @staticmethod
    def _load_station_yards() -> list[dict[str, Any]]:
        project_root = StationDemoService._project_root()
        candidates = (
            project_root / "backend" / "data" / "station-yard-v2.json",
            project_root / "frontend" / "public" / "data" / "station-yard-v2.json",
        )
        for path in candidates:
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                return list(payload.get("stations") or [])
        return []

    @staticmethod
    def _section_range(section: dict[str, Any]) -> tuple[float, float] | None:
        try:
            start = float(section["start"])
            end = float(section["end"])
        except (KeyError, TypeError, ValueError):
            return None
        if start == end:
            return None
        return (min(start, end), max(start, end))

    @classmethod
    def _with_yard_demo_positions(
        cls,
        station: dict[str, Any],
        config: StationDemoConfig,
    ) -> dict[str, Any]:
        """Attach station-yard coordinate positions for the visual station demo.

        line-layout.json uses the logical line mileage used by earlier overview pages.
        StationYardPanel projects trains against station-yard-v2 section start/end
        coordinates, so the demo must spawn and target trains in that same coordinate
        system; otherwise multiple trains collapse onto the same fallback point.
        """

        yard_station = cls._find_yard_station(station)
        if yard_station is None:
            return dict(station)

        ranges: list[tuple[float, float, dict[str, Any]]] = []
        for section in yard_station.get("sections") or []:
            section_range = cls._section_range(section)
            if section_range is not None:
                ranges.append((section_range[0], section_range[1], section))
        if not ranges:
            return dict(station)

        yard_start = min(item[0] for item in ranges)
        yard_end = max(item[1] for item in ranges)
        platform_section = cls._pick_platform_section(yard_station, ranges)
        if platform_section is not None:
            stop_start, stop_end, stop_section = platform_section
        else:
            midpoint = (yard_start + yard_end) / 2.0
            stop_start, stop_end, stop_section = min(
                ranges,
                key=lambda item: abs(((item[0] + item[1]) / 2.0) - midpoint),
            )

        route_ranges = cls._dedupe_route_ranges(cls._route_ranges_for_stop_section(ranges, stop_section))
        route_start = min(item[0] for item in route_ranges)
        route_end = max(item[1] for item in route_ranges)
        visual_exit_extension_m = 650.0
        stop_position = (stop_start + stop_end) / 2.0
        approach_position = max(route_start + 1.0, stop_position - config.approach_distance_m)
        exit_position = min(route_end + visual_exit_extension_m, stop_position + config.exit_distance_m)
        if exit_position <= stop_position:
            exit_position = min(route_end + visual_exit_extension_m, stop_position + max(120.0, (route_end - stop_position) * 0.5))

        result = dict(station)
        result.update(
            {
                "position": stop_position,
                "line_position_m": station.get("position"),
                "demo_coordinate_source": "station-yard-v2",
                "demo_stop_position_m": stop_position,
                "demo_approach_position_m": approach_position,
                "demo_exit_position_m": exit_position,
                "demo_stop_section_id": stop_section.get("section_id"),
                "demo_stop_track_id": stop_section.get("track_id"),
                "demo_route_start_m": route_start,
                "demo_route_end_m": route_end,
                "demo_visual_exit_end_m": route_end + visual_exit_extension_m,
                "demo_route_section_ids": [item[2].get("section_id") for item in route_ranges],
                "demo_route_track_ids": sorted({item[2].get("track_id") for item in route_ranges if item[2].get("track_id")}),
                "yard_start_m": yard_start,
                "yard_end_m": yard_end,
                "yard_section_count": len(ranges),
            }
        )
        return result

    @classmethod
    def _find_yard_station(cls, station: dict[str, Any]) -> dict[str, Any] | None:
        station_id = station.get("station_id")
        station_name = station.get("station_name") or station.get("name")
        for yard_station in cls._load_station_yards():
            if station_id and yard_station.get("station_id") == station_id:
                return yard_station
            if station_name and yard_station.get("station_name") == station_name:
                return yard_station
        return None

    @staticmethod
    def _pick_platform_section(
        yard_station: dict[str, Any],
        ranges: list[tuple[float, float, dict[str, Any]]],
    ) -> tuple[float, float, dict[str, Any]] | None:
        platform_track_ids = {
            platform.get("track_id")
            for platform in yard_station.get("platforms") or []
            if platform.get("track_id")
        }
        if platform_track_ids:
            for item in ranges:
                if item[2].get("track_id") in platform_track_ids:
                    return item
        return None

    @classmethod
    def _route_ranges_for_stop_section(
        cls,
        ranges: list[tuple[float, float, dict[str, Any]]],
        stop_section: dict[str, Any],
    ) -> list[tuple[float, float, dict[str, Any]]]:
        stop_y = cls._section_primary_y(stop_section)
        if stop_y is None:
            return ranges
        route = [
            item
            for item in ranges
            if cls._section_primary_y(item[2]) is not None
            and abs(float(cls._section_primary_y(item[2])) - stop_y) <= 2.0
        ]
        return route or ranges

    @staticmethod
    def _dedupe_route_ranges(
        route_ranges: list[tuple[float, float, dict[str, Any]]],
    ) -> list[tuple[float, float, dict[str, Any]]]:
        kept: list[tuple[float, float, dict[str, Any]]] = []
        for item in route_ranges:
            track_id = item[2].get("track_id")
            if not track_id:
                kept.append(item)
                continue
            overlap_index = next(
                (
                    index
                    for index, existing in enumerate(kept)
                    if existing[2].get("track_id") == track_id
                    and min(existing[1], item[1]) - max(existing[0], item[0]) > 1.0
                ),
                None,
            )
            if overlap_index is None:
                kept.append(item)
                continue
            existing = kept[overlap_index]
            if (item[1] - item[0]) > (existing[1] - existing[0]):
                kept[overlap_index] = item
        return sorted(kept, key=lambda item: (item[0], item[1]))

    @staticmethod
    def _section_primary_y(section: dict[str, Any]) -> float | None:
        points = section.get("geometry", {}).get("points") or section.get("points") or []
        if not points:
            return None
        ys = []
        for point in points:
            try:
                ys.append(float(point[1]))
            except (TypeError, ValueError, IndexError):
                continue
        if not ys:
            return None
        return sum(ys) / len(ys)


station_demo_service = StationDemoService()
