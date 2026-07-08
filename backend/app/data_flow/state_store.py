from __future__ import annotations

import time
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional

from app.core.config import settings
from app.data_flow.data_mapper import (
    normalize_driver_input,
    normalize_power,
    normalize_train,
)
from app.data_flow.schemas import (
    AlarmEvent,
    CommunicationStatus,
    DashboardSnapshot,
    DriverInput,
    PowerSnapshot,
    SignalSnapshot,
    SwitchSnapshot,
    SystemStatus,
    TrackSectionSnapshot,
    TrainSnapshot,
)


class DashboardStateStore:
    """In-memory state cache for the current dashboard snapshot."""

    def __init__(self) -> None:
        now = time.time()
        self._lock = RLock()
        self._websocket_clients = 0
        self._communication = CommunicationStatus(
            source=settings.DATA_SOURCE if settings.DATA_SOURCE in {"mock", "udp", "zmq"} else "unknown",
            last_message_at=now,
        )
        self._driver_inputs: Dict[str, DriverInput] = {}
        self._trains: Dict[str, TrainSnapshot] = {}
        self._sections: Dict[str, TrackSectionSnapshot] = {}
        self._signals: Dict[str, SignalSnapshot] = {}
        self._switches: Dict[str, SwitchSnapshot] = {}
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
            self._trains[normalized["vehicle_id"]] = TrainSnapshot(**normalized)

    def update_ma_limits(self, ma_limits: Iterable[Dict[str, Any]]) -> None:
        with self._lock:
            for item in ma_limits:
                vehicle_id = item.get("vehicle_id") or item.get("train_id")
                if not vehicle_id:
                    continue
                train = self._trains.get(vehicle_id)
                if train:
                    payload = train.model_dump()
                    payload["ma_limit"] = item.get("ma_limit")
                    self._trains[vehicle_id] = TrainSnapshot(**payload)

    def update_signal_state(self, data: Dict[str, Any]) -> None:
        with self._lock:
            for section in data.get("sections", []):
                section_id = section.get("section_id") or section.get("segment_id")
                if not section_id:
                    continue
                payload = dict(section)
                payload["section_id"] = section_id
                self._sections[section_id] = TrackSectionSnapshot(**payload)

            for signal in data.get("signals", data.get("lights", [])):
                signal_id = signal.get("signal_id")
                if not signal_id:
                    continue
                self._signals[signal_id] = SignalSnapshot(**signal)

            for switch in data.get("switches", []):
                switch_id = switch.get("switch_id")
                if not switch_id:
                    continue
                self._switches[switch_id] = SwitchSnapshot(**switch)

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
        payload.setdefault("alarm_id", f"ALM-{int(now * 1000)}")
        payload.setdefault("timestamp", now)
        payload.setdefault("message", "Unknown alarm")
        payload.setdefault("raw_data", dict(data))
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
                data_source=data_source,
                zmq_connected=self._communication.zmq_connected,
                websocket_clients=self._websocket_clients,
            )
            return DashboardSnapshot(
                timestamp=now,
                system=system,
                communication=self._communication,
                driver_inputs=sorted(self._driver_inputs.values(), key=lambda item: item.vehicle_id),
                trains=sorted(trains, key=lambda item: item.vehicle_id),
                sections=sorted(self._sections.values(), key=lambda item: item.section_id),
                signals=sorted(self._signals.values(), key=lambda item: item.signal_id),
                switches=sorted(self._switches.values(), key=lambda item: item.switch_id),
                power=self._power,
                alarms=list(reversed(self._alarms[-20:])),
            )


state_store = DashboardStateStore()

