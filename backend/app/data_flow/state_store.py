from __future__ import annotations

import time
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional

from app.core.config import settings
from app.data_flow.data_mapper import (
    normalize_ato_command,
    normalize_driver_input,
    normalize_ma,
    normalize_power,
    normalize_section,
    normalize_signal,
    normalize_switch,
    normalize_train,
)
from app.data_flow.display_text import (
    alarm_level_label,
    alarm_source_label,
    translate_alarm_message,
)
from app.data_flow.schemas import (
    AtoCommandSnapshot,
    AlarmEvent,
    CommunicationStatus,
    DashboardSnapshot,
    DriverInput,
    MovementAuthoritySnapshot,
    PowerSnapshot,
    RouteResult,
    SignalSnapshot,
    SwitchSnapshot,
    SystemStatus,
    TrackSectionSnapshot,
    TrainSnapshot,
)


MA_TO_TRAIN_FIELDS = (
    "route_id",
    "ma_limit",
    "distance_to_ma",
    "permission",
    "signal_state",
    "speed_limit",
    "target_speed",
    "route_speed_limit",
    "required_stop_distance",
    "emergency_stop_distance",
    "warning_distance",
    "braking_curve_speed_limit",
    "braking_model",
    "front_vehicle_id",
    "front_protection_point",
)


class DashboardStateStore:
    """In-memory state cache for the current dashboard snapshot."""

    def __init__(self) -> None:
        now = time.time()
        self._lock = RLock()
        self._websocket_clients = 0
        self._system_mode = "normal"
        self._communication = CommunicationStatus(
            source=settings.DATA_SOURCE if settings.DATA_SOURCE in {"mock", "udp", "zmq"} else "unknown",
            last_message_at=now,
        )
        self._driver_inputs: Dict[str, DriverInput] = {}
        self._ato_commands: Dict[str, AtoCommandSnapshot] = {}
        self._trains: Dict[str, TrainSnapshot] = {}
        self._ma_limits: Dict[str, MovementAuthoritySnapshot] = {}
        self._sections: Dict[str, TrackSectionSnapshot] = {}
        self._signals: Dict[str, SignalSnapshot] = {}
        self._switches: Dict[str, SwitchSnapshot] = {}
        self._route_results: List[RouteResult] = []
        self._power = PowerSnapshot(updated_at=now)
        self._alarms: List[AlarmEvent] = []

    def set_websocket_clients(self, count: int) -> None:
        with self._lock:
            self._websocket_clients = max(0, count)

    def update_comm(self, data: Dict[str, Any]) -> None:
        with self._lock:
            payload = self._communication.model_dump()
            payload.update(data)
            self._communication = CommunicationStatus(**payload)

    def update_driver_input(self, vehicle_id: str, data: Dict[str, Any]) -> None:
        now = time.time()
        raw_data = dict(data)
        normalized = normalize_driver_input(data)
        normalized.setdefault("vehicle_id", vehicle_id)
        normalized.setdefault("updated_at", now)
        normalized.setdefault("raw_data", raw_data)
        with self._lock:
            self._driver_inputs[normalized["vehicle_id"]] = DriverInput(**normalized)

    def update_ato_command(self, vehicle_id: str, data: Dict[str, Any]) -> None:
        now = time.time()
        raw_data = dict(data)
        normalized = normalize_ato_command(data)
        normalized.setdefault("vehicle_id", vehicle_id)
        normalized.setdefault("updated_at", now)
        normalized.setdefault("raw_data", raw_data)
        with self._lock:
            self._ato_commands[normalized["vehicle_id"]] = AtoCommandSnapshot(**normalized)

    def update_train(self, vehicle_id: str, data: Dict[str, Any]) -> None:
        now = time.time()
        raw_data = dict(data)
        normalized = normalize_train(data)
        normalized.setdefault("vehicle_id", vehicle_id)
        normalized.setdefault("updated_at", now)
        normalized.setdefault("raw_data", raw_data)
        with self._lock:
            existing = self._trains.get(normalized["vehicle_id"])
            if existing:
                payload = existing.model_dump()
                payload.update(normalized)
                normalized = payload
            ma_snapshot = self._ma_limits.get(normalized["vehicle_id"])
            if ma_snapshot:
                ma_payload = ma_snapshot.model_dump()
                for field in MA_TO_TRAIN_FIELDS:
                    if ma_payload.get(field) is not None:
                        normalized[field] = ma_payload[field]
                if normalized.get("stop_distance") is None and ma_payload.get("distance_to_ma") is not None:
                    normalized["stop_distance"] = max(0.0, float(ma_payload["distance_to_ma"]))
            self._trains[normalized["vehicle_id"]] = TrainSnapshot(**normalized)

    def update_ma_limits(self, ma_limits: Iterable[Dict[str, Any]]) -> None:
        now = time.time()
        with self._lock:
            for item in ma_limits:
                raw_data = dict(item)
                normalized_ma = normalize_ma(item)
                vehicle_id = normalized_ma.get("vehicle_id")
                if not vehicle_id:
                    continue
                normalized_ma.setdefault("route_id", "R_MAIN")
                if normalized_ma.get("distance_to_ma") is None and normalized_ma.get("position") is not None:
                    normalized_ma["distance_to_ma"] = max(
                        0.0,
                        float(normalized_ma["ma_limit"]) - float(normalized_ma["position"]),
                    )
                normalized_ma.setdefault("updated_at", now)
                normalized_ma.setdefault("raw_data", raw_data)
                ma_snapshot = MovementAuthoritySnapshot(**normalized_ma)
                self._ma_limits[vehicle_id] = ma_snapshot
                train = self._trains.get(vehicle_id)
                if train:
                    payload = train.model_dump()
                    ma_payload = ma_snapshot.model_dump()
                    for field in MA_TO_TRAIN_FIELDS:
                        if ma_payload.get(field) is not None:
                            payload[field] = ma_payload[field]
                    if ma_payload.get("distance_to_ma") is not None:
                        payload["stop_distance"] = max(0.0, float(ma_payload["distance_to_ma"]))
                    self._trains[vehicle_id] = TrainSnapshot(**payload)

    def update_signal_state(self, data: Dict[str, Any]) -> None:
        with self._lock:
            if data.get("system_mode"):
                self._system_mode = str(data["system_mode"])

            for section in data.get("sections", []):
                payload = normalize_section(section)
                section_id = payload.get("section_id")
                if not section_id:
                    continue
                payload["section_id"] = section_id
                payload.setdefault("line_id", data.get("line_id", "LINE-1"))
                payload.setdefault("occupied", False)
                payload.setdefault("condition", "normal")
                existing = self._sections.get(section_id)
                if existing:
                    merged = existing.model_dump()
                    merged.update({key: value for key, value in payload.items() if value is not None})
                    payload = merged
                self._sections[section_id] = TrackSectionSnapshot(**payload)

            for signal in data.get("signals", data.get("lights", [])):
                payload = normalize_signal(signal)
                signal_id = payload.get("signal_id")
                if not signal_id:
                    continue
                self._signals[signal_id] = SignalSnapshot(**payload)

            for switch in data.get("switches", []):
                payload = normalize_switch(switch)
                switch_id = payload.get("switch_id")
                if not switch_id:
                    continue
                self._switches[switch_id] = SwitchSnapshot(**payload)

            self._route_results = [
                RouteResult(**item) for item in data.get("route_results", [])
            ]

    def update_track_info(self, data: Dict[str, Any]) -> None:
        with self._lock:
            for section in data.get("sections", []):
                payload = normalize_section(section)
                section_id = payload.get("section_id")
                if not section_id:
                    continue
                existing = self._sections.get(section_id)
                if existing:
                    merged = existing.model_dump()
                    merged.update(payload)
                    payload = merged
                payload["section_id"] = section_id
                payload.setdefault("line_id", data.get("line_id", "LINE-1"))
                payload.setdefault("occupied", False)
                payload.setdefault("condition", "normal")
                self._sections[section_id] = TrackSectionSnapshot(**payload)

    def get_track_info_payload(self) -> Dict[str, Any]:
        with self._lock:
            sections = []
            for section in sorted(self._sections.values(), key=lambda item: item.section_id):
                sections.append(
                    {
                        "section_id": section.section_id,
                        "start": section.start,
                        "end": section.end,
                        "gradient": section.gradient if section.gradient is not None else 0.0,
                        "speed_limit": section.speed_limit if section.speed_limit is not None else 60.0,
                        "station_id": section.station_id,
                        "stop_position": section.stop_position,
                    }
                )
            return {
                "line_id": sections and next(iter(self._sections.values())).line_id or "LINE-1",
                "sections": sections,
            }

    def update_power(self, data: Dict[str, Any]) -> None:
        now = time.time()
        raw_data = dict(data)
        normalized = normalize_power(data)
        normalized.setdefault("updated_at", now)
        normalized.setdefault("raw_data", raw_data)
        with self._lock:
            payload = self._power.model_dump()
            payload.update(normalized)
            self._power = PowerSnapshot(**payload)

    def add_alarm(self, data: Dict[str, Any]) -> None:
        now = time.time()
        payload = dict(data)
        raw_data = dict(data)
        payload.setdefault("alarm_id", f"ALM-{int(now * 1000)}")
        payload.setdefault("timestamp", now)
        payload.setdefault("message", "Unknown alarm")
        payload["message"] = translate_alarm_message(payload.get("message"))
        payload["level_label"] = alarm_level_label(payload.get("level"))
        payload["source_label"] = alarm_source_label(payload.get("source"))
        payload.setdefault("raw_data", raw_data)
        with self._lock:
            self._alarms.append(AlarmEvent(**payload))
            self._alarms = self._alarms[-100:]

    def get_snapshot(self) -> DashboardSnapshot:
        now = time.time()
        with self._lock:
            trains = []
            for train in self._trains.values():
                payload = train.model_dump()
                if now - payload["updated_at"] > 2.0:
                    payload["is_running"] = False
                trains.append(TrainSnapshot(**payload))

            data_source = settings.DATA_SOURCE if settings.DATA_SOURCE in {"mock", "udp", "zmq"} else "unknown"
            system = SystemStatus(
                status="running",
                system_mode=self._system_mode,
                data_source=data_source,
                zmq_connected=self._communication.zmq_connected,
                websocket_clients=self._websocket_clients,
            )
            return DashboardSnapshot(
                timestamp=now,
                system=system,
                communication=self._communication,
                driver_inputs=sorted(self._driver_inputs.values(), key=lambda item: item.vehicle_id),
                ato_commands=sorted(self._ato_commands.values(), key=lambda item: item.vehicle_id),
                trains=sorted(trains, key=lambda item: item.vehicle_id),
                ma_limits=sorted(self._ma_limits.values(), key=lambda item: item.vehicle_id),
                sections=sorted(self._sections.values(), key=lambda item: item.section_id),
                signals=sorted(self._signals.values(), key=lambda item: item.signal_id),
                switches=sorted(self._switches.values(), key=lambda item: item.switch_id),
                route_results=list(self._route_results),
                power=self._power,
                alarms=list(reversed(self._alarms[-20:])),
            )


state_store = DashboardStateStore()
