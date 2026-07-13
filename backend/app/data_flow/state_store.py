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
    normalize_route_request,
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
    CommandAckSnapshot,
    CommunicationStatus,
    DashboardSceneStateSnapshot,
    DashboardSnapshot,
    DriverInput,
    ExternalConnections,
    IntegrationStatus,
    MovementAuthoritySnapshot,
    PowerSnapshot,
    RouteResult,
    RouteRequestSnapshot,
    ScenarioConfig,
    SceneStateItem,
    SignalSnapshot,
    SwitchSnapshot,
    SystemStatus,
    TrackSectionSnapshot,
    TrainSnapshot,
    YardLayoutSnapshot,
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

MANAGEMENT_TRAIN_FIELDS = (
    "vehicle_id",
    "line_id",
    "route_id",
    "train_length",
    "platform_id",
    "station_name",
    "raw_data",
)


KNOWN_SOURCES = {
    "mock",
    "udp",
    "zmq",
    "frontend",
    "vehicle_udp",
    "vehicle_api",
    "driver_tcp",
    "signal_zmq",
    "power_adapter",
    "track_adapter",
    "unknown",
}

SOURCE_ALIASES = {
    "vehicle_algo": "zmq",
    "vehicle_sim": "zmq",
    "signal": "signal_zmq",
    "signal_worker": "signal_zmq",
    "driver_desk": "driver_tcp",
    "driver_plc": "driver_tcp",
    "plc": "driver_tcp",
    "udp_placeholder": "udp",
}

PROTOCOL_BY_SOURCE = {
    "mock": "mock",
    "udp": "udp_compat",
    "zmq": "internal_zmq",
    "frontend": "rest",
    "vehicle_udp": "formal_vehicle_udp",
    "vehicle_api": "formal_vehicle_api",
    "driver_tcp": "formal_driver_plc_tcp",
    "signal_zmq": "internal_signal_zmq",
    "power_adapter": "power_adapter",
    "track_adapter": "track_adapter",
}

ADAPTER_BY_SOURCE = {
    "vehicle_udp": "vehicle_udp_codec",
    "vehicle_api": "vehicle_api_codec",
    "driver_tcp": "driver_desk_source",
    "signal_zmq": "signal_zmq_adapter",
    "power_adapter": "power_adapter",
    "track_adapter": "track_adapter",
}

STALE_AFTER_SECONDS = {
    "driver_input": 1.0,
    "ato_command": 1.0,
    "train": 1.6,
    "ma": 1.6,
    "section": 1.0,
    "signal": 1.0,
    "switch": 1.0,
    "power": 1.0,
}

ZMQ_HEALTH_TIMEOUT_SECONDS = 3.0
ALARM_STATUS_WINDOW_SECONDS = 5.0
MA_SCENE_SHRINK_THRESHOLD = 150.0
RECENT_SCENE_WINDOW_SECONDS = 45.0
PARKING_SCENE_PHASES = {"approaching", "braking", "docking", "stopped"}

SCENARIO_CONFIGS = [
    ScenarioConfig(
        scenario_id="normal_stop",
        name="Normal station stop",
        description="Train approaches a station and stops at the target platform.",
        page_config={
            "hero_panel": "target_vehicle_summary",
            "primary_chart": "speed_distance",
            "secondary_chart": "speed_time",
            "panels": ["stop_target", "control_output", "stop_result"],
            "key_metrics": ["speed_kmh", "target_speed_kmh", "remaining_distance_m", "stop_error_cm"],
            "highlight_events": ["approach_started", "service_brake_started", "stop_completed"],
        },
    ),
    ScenarioConfig(
        scenario_id="red_signal_stop",
        name="Red signal stop",
        description="Signal changes to stop, MA is shortened, and the train brakes before the boundary.",
        page_config={
            "hero_panel": "target_vehicle_summary",
            "primary_chart": "speed_distance",
            "secondary_chart": "event_timeline",
            "panels": ["signal_status", "ma_status", "control_output", "stop_result"],
            "key_metrics": ["signal_state", "ma_limit_m", "distance_to_ma_m", "recommended_speed_kmh"],
            "highlight_events": ["signal_red", "ma_updated", "brake_command_sent", "stop_completed"],
        },
    ),
    ScenarioConfig(
        scenario_id="ma_shrink",
        name="MA shrink",
        description="Movement authority shrinks while a train is running.",
        page_config={
            "hero_panel": "target_vehicle_summary",
            "primary_chart": "speed_distance",
            "secondary_chart": "atp_margin_chart",
            "panels": ["ma_status", "atp_status", "control_output", "stop_result"],
            "key_metrics": ["old_ma_limit_m", "new_ma_limit_m", "distance_to_ma_m", "recommended_speed_kmh", "atp_triggered"],
            "highlight_events": ["ma_shrink", "recommended_speed_drop", "atp_warning", "atp_triggered", "stop_completed"],
        },
    ),
    ScenarioConfig(
        scenario_id="section_block_stop",
        name="Section block stop",
        description="A blocked station or section prevents route authorization.",
        page_config={
            "hero_panel": "network_impact_summary",
            "primary_chart": "line_overview",
            "secondary_chart": "speed_distance",
            "panels": ["blocked_section", "affected_vehicles", "signal_status", "stop_result"],
            "key_metrics": ["blocked_section_id", "affected_vehicle_count", "target_vehicle_id", "remaining_distance_m"],
            "highlight_events": ["section_blocked", "route_denied", "ma_updated", "stop_completed"],
        },
    ),
    ScenarioConfig(
        scenario_id="manual_overspeed_atp",
        name="Manual overspeed ATP intervention",
        description="Manual driving ignores recommended speed and ATP applies emergency braking.",
        page_config={
            "hero_panel": "target_vehicle_summary",
            "primary_chart": "speed_distance",
            "secondary_chart": "driver_input_timeline",
            "panels": ["driver_input", "recommended_speed", "atp_status", "stop_result"],
            "key_metrics": ["speed_kmh", "recommended_speed_kmh", "driver_brake_level", "atp_triggered", "emergency_brake"],
            "highlight_events": ["recommended_speed_drop", "driver_no_response", "atp_triggered", "emergency_brake_applied", "stop_completed"],
        },
    ),
    ScenarioConfig(
        scenario_id="external_event_stop",
        name="External event stop",
        description="External disturbance updates signal or MA constraints and the train stops safely.",
        page_config={
            "hero_panel": "network_impact_summary",
            "primary_chart": "line_overview",
            "secondary_chart": "event_timeline",
            "panels": ["external_system_status", "signal_status", "ma_status", "stop_result"],
            "key_metrics": ["blocked_section_id", "affected_vehicle_count", "distance_to_ma_m", "atp_triggered"],
            "highlight_events": ["external_event", "ma_updated", "brake_command_sent", "stop_completed"],
        },
    ),
]

SCENARIO_PAGE_CONFIG_BY_ID = {
    item.scenario_id: item.page_config
    for item in SCENARIO_CONFIGS
}


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
        self._route_requests: Dict[str, RouteRequestSnapshot] = {}
        self._route_results: List[RouteResult] = []
        self._command_acks: List[CommandAckSnapshot] = []
        self._power = PowerSnapshot(updated_at=now)
        self._alarms: List[AlarmEvent] = []
        self._yard_layout = YardLayoutSnapshot(updated_at=now)
        self._recent_ma_shrink_events: Dict[str, Dict[str, Any]] = {}

    def set_websocket_clients(self, count: int) -> None:
        with self._lock:
            self._websocket_clients = max(0, count)

    def update_comm(self, data: Dict[str, Any]) -> None:
        with self._lock:
            payload = self._communication.model_dump()
            payload.update(data)
            payload["source"] = self._normalize_source(payload.get("source"))
            self._communication = CommunicationStatus(**payload)

    def mark_real_message_received(self, source: str = "zmq") -> None:
        now = time.time()
        self.update_comm(
            {
                "source": source,
                "zmq_connected": True,
                "last_message_at": now,
                "last_real_message_at": now,
                "no_message_seconds": 0.0,
            }
        )

    def update_driver_input(self, vehicle_id: str, data: Dict[str, Any]) -> None:
        now = time.time()
        raw_data = dict(data)
        normalized = normalize_driver_input(data)
        normalized.setdefault("vehicle_id", vehicle_id)
        normalized.setdefault("updated_at", now)
        normalized.setdefault("raw_data", raw_data)
        self._apply_protocol_metadata(normalized, raw_data, now, "driver_input")
        with self._lock:
            self._driver_inputs[normalized["vehicle_id"]] = DriverInput(**normalized)

    def update_ato_command(self, vehicle_id: str, data: Dict[str, Any]) -> None:
        now = time.time()
        raw_data = dict(data)
        normalized = normalize_ato_command(data)
        normalized.setdefault("vehicle_id", vehicle_id)
        normalized.setdefault("updated_at", now)
        normalized.setdefault("raw_data", raw_data)
        self._apply_protocol_metadata(normalized, raw_data, now, "ato_command")
        with self._lock:
            self._ato_commands[normalized["vehicle_id"]] = AtoCommandSnapshot(**normalized)

    def update_train(self, vehicle_id: str, data: Dict[str, Any]) -> None:
        now = time.time()
        raw_data = dict(data)
        normalized = normalize_train(data)
        normalized.setdefault("vehicle_id", vehicle_id)
        normalized.setdefault("updated_at", now)
        normalized.setdefault("raw_data", raw_data)
        if normalized.get("mileage") is not None and normalized.get("position") in {None, 0.0}:
            normalized["position"] = float(normalized["mileage"])
        self._apply_protocol_metadata(normalized, raw_data, now, "train")
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
            normalized = self._enrich_train_topology(normalized)
            self._trains[normalized["vehicle_id"]] = TrainSnapshot(**normalized)

    def register_vehicle(self, data: Dict[str, Any]) -> Optional[str]:
        normalized = normalize_train(data)
        vehicle_id = normalized.get("vehicle_id") or normalized.get("train_id") or normalized.get("id")
        if not vehicle_id:
            return None
        normalized.setdefault("vehicle_id", str(vehicle_id))
        normalized.setdefault("line_id", "LINE-1")
        normalized.setdefault("route_id", "R_MAIN")
        normalized.setdefault("position", 0.0)
        normalized.setdefault("speed", 0.0)
        normalized.setdefault("acceleration", 0.0)
        normalized.setdefault("mode", "manual")
        normalized.setdefault("is_running", float(normalized.get("speed") or 0.0) > 0.0)
        normalized.setdefault("emergency_brake", False)
        self._apply_protocol_metadata(normalized, data, time.time(), "train")
        self.update_train(str(vehicle_id), normalized)
        return str(vehicle_id)

    def replace_trains(self, trains: Iterable[Dict[str, Any]]) -> None:
        """Merge a managed TrainManager list without overwriting live runtime state."""

        now = time.time()
        snapshots: Dict[str, TrainSnapshot] = {}
        for item in trains:
            raw_data = dict(item)
            normalized = normalize_train(item)
            vehicle_id = normalized.get("vehicle_id")
            if not vehicle_id:
                continue
            normalized.setdefault("vehicle_id", vehicle_id)
            normalized.setdefault("updated_at", now)
            normalized.setdefault("raw_data", raw_data)
            normalized.setdefault("is_running", bool(normalized.get("speed", 0.0)))
            self._apply_protocol_metadata(normalized, raw_data, now, "train")
            snapshots[vehicle_id] = TrainSnapshot(**normalized)

        with self._lock:
            for vehicle_id, managed_snapshot in snapshots.items():
                existing = self._trains.get(vehicle_id)
                if not existing:
                    self._trains[vehicle_id] = managed_snapshot
                    continue
                payload = existing.model_dump()
                managed_payload = managed_snapshot.model_dump()
                for field in MANAGEMENT_TRAIN_FIELDS:
                    if managed_payload.get(field) is not None:
                        payload[field] = managed_payload[field]
                self._trains[vehicle_id] = TrainSnapshot(**payload)

            active_ids = set(self._trains)
            self._driver_inputs = {
                vehicle_id: item
                for vehicle_id, item in self._driver_inputs.items()
                if vehicle_id in active_ids
            }
            self._ato_commands = {
                vehicle_id: item
                for vehicle_id, item in self._ato_commands.items()
                if vehicle_id in active_ids
            }
            self._ma_limits = {
                vehicle_id: item
                for vehicle_id, item in self._ma_limits.items()
                if vehicle_id in active_ids
            }
            self._recent_ma_shrink_events = {
                vehicle_id: item
                for vehicle_id, item in self._recent_ma_shrink_events.items()
                if vehicle_id in active_ids
            }

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
                self._apply_protocol_metadata(normalized_ma, raw_data, now, "ma")
                previous_ma = self._ma_limits.get(vehicle_id)
                if previous_ma and previous_ma.ma_limit is not None and normalized_ma.get("ma_limit") is not None:
                    shrink_amount = float(previous_ma.ma_limit) - float(normalized_ma["ma_limit"])
                    if shrink_amount >= MA_SCENE_SHRINK_THRESHOLD:
                        self._recent_ma_shrink_events[vehicle_id] = {
                            "vehicle_id": vehicle_id,
                            "amount": round(shrink_amount, 1),
                            "at": now,
                            "old_ma_limit": float(previous_ma.ma_limit),
                            "new_ma_limit": float(normalized_ma["ma_limit"]),
                        }
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
                raw_section = dict(section)
                payload = normalize_section(section)
                section_id = payload.get("section_id")
                if not section_id:
                    continue
                payload["section_id"] = section_id
                payload.setdefault("line_id", data.get("line_id", "LINE-1"))
                payload.setdefault("occupied", False)
                payload.setdefault("condition", "normal")
                self._apply_protocol_metadata(payload, raw_section, time.time(), "section", parent=data)
                existing = self._sections.get(section_id)
                if existing:
                    merged = existing.model_dump()
                    merged.update({key: value for key, value in payload.items() if value is not None})
                    payload = merged
                self._sections[section_id] = TrackSectionSnapshot(**payload)
            self._refresh_train_topology_locked()

            for signal in data.get("signals", data.get("lights", [])):
                raw_signal = dict(signal)
                payload = normalize_signal(signal)
                signal_id = payload.get("signal_id")
                if not signal_id:
                    continue
                self._apply_protocol_metadata(payload, raw_signal, time.time(), "signal", parent=data)
                self._signals[signal_id] = SignalSnapshot(**payload)

            for switch in data.get("switches", []):
                raw_switch = dict(switch)
                payload = normalize_switch(switch)
                switch_id = payload.get("switch_id")
                if not switch_id:
                    continue
                self._apply_protocol_metadata(payload, raw_switch, time.time(), "switch", parent=data)
                self._switches[switch_id] = SwitchSnapshot(**payload)

            self._route_results = [
                RouteResult(**item) for item in data.get("route_results", [])
            ]

    def update_route_result(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self._route_results.append(RouteResult(**data))
            self._route_results = self._route_results[-50:]

    def update_command_ack(self, data: Dict[str, Any]) -> None:
        now = time.time()
        payload = dict(data)
        payload.setdefault("updated_at", now)
        payload.setdefault("raw_data", dict(data))
        payload.setdefault("topic", payload.get("command_topic") or payload.get("type") or "unknown")
        if "accepted" not in payload:
            payload["accepted"] = str(payload.get("status", "")).lower() in {"ok", "accepted", "success", "applied"}
        with self._lock:
            self._command_acks.append(CommandAckSnapshot(**payload))
            self._command_acks = self._command_acks[-50:]

    def update_route_request(self, data: Dict[str, Any]) -> Optional[str]:
        now = time.time()
        raw_data = dict(data)
        normalized = normalize_route_request(data)
        vehicle_id = normalized.get("vehicle_id")
        if not vehicle_id:
            return None
        normalized.setdefault("route_id", "R_MAIN")
        normalized.setdefault("priority", 0)
        normalized.setdefault("status", "pending")
        if normalized["status"] not in {"pending", "accepted", "rejected", "unknown"}:
            normalized["status"] = "unknown"
        normalized.setdefault("updated_at", now)
        normalized.setdefault("raw_data", raw_data)
        request_key = (
            normalized.get("request_id")
            or f"{normalized['vehicle_id']}:{normalized['route_id']}"
        )
        with self._lock:
            self._route_requests[request_key] = RouteRequestSnapshot(**normalized)
        return str(request_key)

    def update_track_info(self, data: Dict[str, Any]) -> None:
        with self._lock:
            for section in data.get("sections", []):
                raw_section = dict(section)
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
                self._apply_protocol_metadata(payload, raw_section, time.time(), "section", parent=data)
                self._sections[section_id] = TrackSectionSnapshot(**payload)
            self._refresh_train_topology_locked()
            if data.get("yard_layout") or data.get("stations"):
                self.update_yard_layout(data)

    def update_yard_layout(self, data: Dict[str, Any]) -> None:
        payload = dict(data.get("yard_layout") or data)
        payload.setdefault("line_id", data.get("line_id", "LINE-1"))
        payload.setdefault("updated_at", time.time())
        with self._lock:
            self._yard_layout = YardLayoutSnapshot(**payload)

    def get_track_info_payload(self) -> Dict[str, Any]:
        with self._lock:
            sections = []
            for section in sorted(self._sections.values(), key=lambda item: item.section_id):
                sections.append(
                    {
                        "section_id": section.section_id,
                        "track_seg_id": section.track_seg_id,
                        "track_id": section.track_id,
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

    def get_yard_layout(self) -> YardLayoutSnapshot:
        with self._lock:
            return self._yard_layout

    def _refresh_train_topology_locked(self) -> None:
        if not self._trains or not self._sections:
            return
        for vehicle_id, train in list(self._trains.items()):
            enriched = self._enrich_train_topology(train.model_dump())
            self._trains[vehicle_id] = TrainSnapshot(**enriched)

    def _enrich_train_topology(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not payload:
            return payload
        section = self._resolve_train_section(payload)
        if not section:
            return payload
        enriched = dict(payload)
        enriched["section_id"] = enriched.get("section_id") or section.section_id
        enriched["track_id"] = enriched.get("track_id") or section.track_id
        enriched["station_id"] = enriched.get("station_id") or section.station_id
        return enriched

    def _resolve_train_section(self, payload: Dict[str, Any]) -> Optional[TrackSectionSnapshot]:
        if not self._sections:
            return None

        section_id = payload.get("section_id")
        if section_id:
            exact = self._sections.get(str(section_id))
            if exact:
                return exact

        vehicle_id = payload.get("vehicle_id")
        track_id = payload.get("track_id")
        position = payload.get("position")

        occupied_matches = [
            section for section in self._sections.values()
            if vehicle_id and (section.occupied_by == vehicle_id or section.vehicle_id == vehicle_id)
        ]
        if track_id:
            exact_track = next((section for section in occupied_matches if section.track_id == track_id), None)
            if exact_track:
                return exact_track
        if len(occupied_matches) == 1:
            return occupied_matches[0]

        if position is None:
            return occupied_matches[0] if occupied_matches else None

        position_matches = [
            section for section in self._sections.values()
            if section.start <= float(position) < section.end
        ]
        if track_id:
            exact_track = next((section for section in position_matches if section.track_id == track_id), None)
            if exact_track:
                return exact_track
        if len(position_matches) == 1:
            return position_matches[0]
        if position_matches:
            return min(
                position_matches,
                key=lambda section: abs(((section.start + section.end) / 2) - float(position)),
            )
        return occupied_matches[0] if occupied_matches else None

    def get_scenarios(self) -> List[ScenarioConfig]:
        return list(SCENARIO_CONFIGS)

    def get_scenario(self, scenario_id: str) -> Optional[ScenarioConfig]:
        return next((item for item in SCENARIO_CONFIGS if item.scenario_id == scenario_id), None)

    def get_scene_state(self) -> DashboardSceneStateSnapshot:
        snapshot = self.get_snapshot()
        now = snapshot.timestamp
        recent_shrink_events = self._get_recent_ma_shrink_events(now)

        vehicle_scenes = [
            self._build_vehicle_scene(
                train=train,
                now=now,
                recent_shrink=recent_shrink_events.get(train.vehicle_id),
                blocked_route=self._find_blocked_route_for_vehicle(snapshot.route_results, train.vehicle_id),
            )
            for train in snapshot.trains
        ]

        emergency_scene = next((scene for scene in vehicle_scenes if scene.scenario_id == "manual_overspeed_atp"), None)
        shrink_scene = next((scene for scene in vehicle_scenes if scene.scenario_id == "ma_shrink"), None)
        blocked_route = next((result for result in snapshot.route_results if not result.allowed), None)
        red_signal_scene = next((scene for scene in vehicle_scenes if scene.scenario_id == "red_signal_stop"), None)
        normal_stop_scene = next((scene for scene in vehicle_scenes if scene.scenario_id == "normal_stop"), None)

        if emergency_scene:
            active_scene = emergency_scene
        elif shrink_scene:
            active_scene = shrink_scene
        elif blocked_route:
            active_scene = self._build_network_scene(
                scenario_id="section_block_stop",
                now=now,
                target_vehicle_id=blocked_route.vehicle_id,
                summary=(
                    f"{blocked_route.vehicle_id} 进路未通过，当前需要重点关注约束停车。"
                    if blocked_route.vehicle_id
                    else "当前存在未通过进路申请，系统处于进路 / 区段约束场景。"
                ),
                reason=blocked_route.reason or "route_denied",
            )
        elif self._is_external_event_scene(snapshot, now):
            active_scene = self._build_network_scene(
                scenario_id="external_event_stop",
                now=now,
                target_vehicle_id=None,
                summary="当前存在外部系统或供电扰动，列车需要按新的约束边界安全运行或停车。",
                reason="external_constraint",
            )
        elif red_signal_scene:
            active_scene = red_signal_scene
        elif normal_stop_scene:
            active_scene = normal_stop_scene
        else:
            active_scene = self._build_network_scene(
                scenario_id="line_run",
                now=now,
                target_vehicle_id=None,
                summary="当前全线没有显著异常，系统处于区间运行监视状态。",
                reason="line_run",
            )

        return DashboardSceneStateSnapshot(
            timestamp=now,
            active_scene=active_scene,
            vehicle_scene_map=vehicle_scenes,
        )

    def get_signal_input_payload(self) -> Dict[str, Any]:
        with self._lock:
            train_states = [
                {
                    "vehicle_id": train.vehicle_id,
                    "position": train.position,
                    "speed": train.speed,
                    "route_id": train.route_id,
                    **({"train_length": train.train_length} if train.train_length is not None else {}),
                }
                for train in sorted(self._trains.values(), key=lambda item: item.vehicle_id)
            ]
            route_requests = [
                {
                    key: value
                    for key, value in request.model_dump().items()
                    if key not in {"updated_at", "raw_data"} and value is not None
                }
                for request in sorted(
                    self._route_requests.values(),
                    key=lambda item: item.request_id or f"{item.vehicle_id}:{item.route_id}",
                )
            ]
            return {
                "train_states": train_states,
                "route_requests": route_requests,
            }

    def update_power(self, data: Dict[str, Any]) -> None:
        now = time.time()
        raw_data = dict(data)
        normalized = normalize_power(data)
        normalized.setdefault("updated_at", now)
        normalized.setdefault("raw_data", raw_data)
        self._apply_protocol_metadata(normalized, raw_data, now, "power")
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

    def _get_recent_ma_shrink_events(self, now: float) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            filtered = {
                vehicle_id: item
                for vehicle_id, item in self._recent_ma_shrink_events.items()
                if now - float(item.get("at") or 0.0) <= RECENT_SCENE_WINDOW_SECONDS
            }
            self._recent_ma_shrink_events = filtered
            return dict(filtered)

    @staticmethod
    def _find_blocked_route_for_vehicle(route_results: List[RouteResult], vehicle_id: str) -> Optional[RouteResult]:
        return next(
            (result for result in route_results if not result.allowed and result.vehicle_id == vehicle_id),
            None,
        )

    def _build_vehicle_scene(
        self,
        *,
        train: TrainSnapshot,
        now: float,
        recent_shrink: Optional[Dict[str, Any]],
        blocked_route: Optional[RouteResult],
    ) -> SceneStateItem:
        vehicle_id = train.vehicle_id
        if train.emergency_brake:
            return self._build_scene_item(
                scenario_id="manual_overspeed_atp",
                now=now,
                scope="vehicle",
                vehicle_id=vehicle_id,
                summary=f"{vehicle_id} 已进入 ATP / 紧急制动场景，当前重点是确认触发原因和停车结果。",
                reason="emergency_brake",
            )
        if recent_shrink:
            amount = recent_shrink.get("amount")
            summary = (
                f"{vehicle_id} 最近发生 MA 收缩，当前需要重点关注剩余授权距离与制动响应。"
                if amount is None
                else f"{vehicle_id} 最近发生 MA 收缩 {amount:.0f} m，当前需要重点关注剩余授权距离与制动响应。"
            )
            return self._build_scene_item(
                scenario_id="ma_shrink",
                now=now,
                scope="vehicle",
                vehicle_id=vehicle_id,
                summary=summary,
                reason="ma_shrink",
            )
        if blocked_route:
            return self._build_scene_item(
                scenario_id="section_block_stop",
                now=now,
                scope="vehicle",
                vehicle_id=vehicle_id,
                summary=f"{vehicle_id} 当前存在未通过进路或区段约束，需要等待放行或执行约束停车。",
                reason=blocked_route.reason or "route_denied",
            )
        if train.permission == "stop" and train.signal_state == "red":
            return self._build_scene_item(
                scenario_id="red_signal_stop",
                now=now,
                scope="vehicle",
                vehicle_id=vehicle_id,
                summary=f"{vehicle_id} 当前受前方红灯约束，正在等待或执行安全停车。",
                reason="red_signal",
            )
        if train.parking_phase in PARKING_SCENE_PHASES:
            station_name = f"{train.station_name} " if train.station_name else ""
            return self._build_scene_item(
                scenario_id="normal_stop",
                now=now,
                scope="vehicle",
                vehicle_id=vehicle_id,
                summary=f"{vehicle_id} 正在{station_name}执行正常进站停车流程。",
                reason=train.parking_phase or "normal_stop",
            )
        return self._build_scene_item(
            scenario_id="line_run",
            now=now,
            scope="vehicle",
            vehicle_id=vehicle_id,
            summary=f"{vehicle_id} 当前处于区间运行阶段，暂未进入重点停车场景。",
            reason="line_run",
        )

    def _build_network_scene(
        self,
        *,
        scenario_id: str,
        now: float,
        target_vehicle_id: Optional[str],
        summary: str,
        reason: Optional[str],
    ) -> SceneStateItem:
        return self._build_scene_item(
            scenario_id=scenario_id,
            now=now,
            scope="vehicle" if target_vehicle_id else "network",
            vehicle_id=target_vehicle_id,
            summary=summary,
            reason=reason,
        )

    @staticmethod
    def _is_external_event_scene(snapshot: DashboardSnapshot, now: float) -> bool:
        if snapshot.power.is_fault:
            return True
        return any(
            alarm.level == "critical"
            and now - float(alarm.timestamp) <= ALARM_STATUS_WINDOW_SECONDS
            and alarm.source in {"POWER", "COMM", "SIGNAL", "BACKEND"}
            for alarm in snapshot.alarms
        )

    def _build_scene_item(
        self,
        *,
        scenario_id: str,
        now: float,
        scope: str,
        vehicle_id: Optional[str],
        summary: str,
        reason: Optional[str],
    ) -> SceneStateItem:
        page_config = SCENARIO_PAGE_CONFIG_BY_ID.get(scenario_id)
        key_metrics = list(page_config.key_metrics) if page_config else []
        highlight_events = list(page_config.highlight_events) if page_config else []
        if scenario_id == "line_run" and not key_metrics:
            key_metrics = ["speed_kmh", "mode", "current_section_id"] if vehicle_id else ["affected_vehicle_count"]
        return SceneStateItem(
            scenario_id=scenario_id,
            scope=scope,
            vehicle_id=vehicle_id,
            target_vehicle_id=vehicle_id,
            summary=summary,
            reason=reason,
            key_metrics=key_metrics,
            highlight_events=highlight_events,
            updated_at=now,
        )

    def get_snapshot(self) -> DashboardSnapshot:
        now = time.time()
        with self._lock:
            trains = []
            for train in self._trains.values():
                payload = train.model_dump()
                payload = self._with_stale_status(payload, now, "train")
                if payload["is_stale"]:
                    payload["is_running"] = False
                trains.append(TrainSnapshot(**payload))

            driver_inputs = [
                DriverInput(**self._with_stale_status(item.model_dump(), now, "driver_input"))
                for item in self._driver_inputs.values()
            ]
            ato_commands = [
                AtoCommandSnapshot(**self._with_stale_status(item.model_dump(), now, "ato_command"))
                for item in self._ato_commands.values()
            ]
            ma_limits = [
                MovementAuthoritySnapshot(**self._with_stale_status(item.model_dump(), now, "ma"))
                for item in self._ma_limits.values()
            ]
            sections = [
                TrackSectionSnapshot(**self._with_stale_status(item.model_dump(), now, "section"))
                for item in self._sections.values()
            ]
            signals = [
                SignalSnapshot(**self._with_stale_status(item.model_dump(), now, "signal"))
                for item in self._signals.values()
            ]
            switches = [
                SwitchSnapshot(**self._with_stale_status(item.model_dump(), now, "switch"))
                for item in self._switches.values()
            ]
            power = PowerSnapshot(**self._with_stale_status(self._power.model_dump(), now, "power"))

            data_source = settings.DATA_SOURCE if settings.DATA_SOURCE in {"mock", "udp", "zmq"} else "unknown"
            communication = self._communication.model_dump()
            last_real_message_at = communication.get("last_real_message_at") or communication.get("last_message_at")
            if last_real_message_at is not None:
                communication["no_message_seconds"] = max(0.0, now - float(last_real_message_at))
            if data_source == "zmq" and (
                last_real_message_at is None
                or now - float(last_real_message_at) > ZMQ_HEALTH_TIMEOUT_SECONDS
            ):
                communication["zmq_connected"] = False
            comm_status = CommunicationStatus(**communication)
            system_status, degraded_reasons = self._derive_system_status(
                data_source=data_source,
                communication=comm_status,
                trains=trains,
                ma_limits=ma_limits,
                signals=signals,
                power=power,
                now=now,
            )
            system = SystemStatus(
                status=system_status,
                system_mode=self._system_mode,
                data_source=data_source,
                zmq_connected=comm_status.zmq_connected,
                websocket_clients=self._websocket_clients,
                degraded_reasons=degraded_reasons,
            )
            integration = IntegrationStatus(
                integration_mode="simulation" if data_source == "mock" else ("realtime" if data_source == "zmq" else "hybrid"),
                realtime_channel="websocket",
                driver_desk_connected=comm_status.driver_console_connected,
                external_connections=ExternalConnections(
                    power=not power.is_stale,
                    signal_screen=bool(signals),
                    cab_screen=bool(driver_inputs or ato_commands),
                    viewer_3d=False,
                    driver_desk=comm_status.driver_console_connected,
                ),
                degraded=system_status != "running",
                last_realtime_message_at=comm_status.last_real_message_at or comm_status.last_message_at,
            )
            return DashboardSnapshot(
                timestamp=now,
                system=system,
                communication=comm_status,
                integration=integration,
                scenarios=list(SCENARIO_CONFIGS),
                driver_inputs=sorted(driver_inputs, key=lambda item: item.vehicle_id),
                ato_commands=sorted(ato_commands, key=lambda item: item.vehicle_id),
                trains=sorted(trains, key=lambda item: item.vehicle_id),
                ma_limits=sorted(ma_limits, key=lambda item: item.vehicle_id),
                sections=sorted(sections, key=lambda item: item.section_id),
                signals=sorted(signals, key=lambda item: item.signal_id),
                switches=sorted(switches, key=lambda item: item.switch_id),
                route_requests=sorted(
                    self._route_requests.values(),
                    key=lambda item: item.request_id or f"{item.vehicle_id}:{item.route_id}",
                ),
                route_results=list(self._route_results),
                command_acks=list(reversed(self._command_acks[-20:])),
                power=power,
                alarms=list(reversed(self._alarms[-20:])),
            )

    def _derive_system_status(
        self,
        data_source: str,
        communication: CommunicationStatus,
        trains: List[TrainSnapshot],
        ma_limits: List[MovementAuthoritySnapshot],
        signals: List[SignalSnapshot],
        power: PowerSnapshot,
        now: float,
    ) -> tuple[str, List[str]]:
        emergency_reasons: List[str] = []
        degraded_reasons: List[str] = []

        recent_critical_alarm = any(
            alarm.level == "critical" and now - alarm.timestamp <= ALARM_STATUS_WINDOW_SECONDS
            for alarm in self._alarms
        )
        if recent_critical_alarm:
            emergency_reasons.append("最近存在 critical 告警")
        if any(train.emergency_brake for train in trains):
            emergency_reasons.append("列车触发紧急制动")
        if power.is_fault:
            emergency_reasons.append("供电状态故障")

        if data_source == "zmq" and not communication.zmq_connected:
            degraded_reasons.append("ZMQ 最近无真实消息")
        if power.is_stale:
            degraded_reasons.append("供电数据超时")
        if any(train.is_stale for train in trains):
            degraded_reasons.append("列车状态超时")
        if any(ma.is_stale for ma in ma_limits):
            degraded_reasons.append("移动授权数据超时")
        if any(signal.is_stale for signal in signals):
            degraded_reasons.append("信号状态超时")

        if emergency_reasons:
            return "emergency", emergency_reasons + degraded_reasons
        if degraded_reasons:
            return "degraded", degraded_reasons
        return "running", []

    def _apply_protocol_metadata(
        self,
        payload: Dict[str, Any],
        raw_data: Dict[str, Any],
        now: float,
        category: str,
        parent: Dict[str, Any] | None = None,
    ) -> None:
        source = (
            payload.get("source")
            or raw_data.get("source")
            or raw_data.get("_source")
            or (parent or {}).get("source")
            or settings.DATA_SOURCE
        )
        normalized_source = self._normalize_source(source)
        payload["source"] = normalized_source
        payload.setdefault("received_at", now)
        payload.setdefault("protocol", raw_data.get("protocol") or raw_data.get("protocol_source") or PROTOCOL_BY_SOURCE.get(normalized_source))
        payload.setdefault("adapter", raw_data.get("adapter") or raw_data.get("source_adapter") or ADAPTER_BY_SOURCE.get(normalized_source))
        payload.setdefault("stale_after_seconds", STALE_AFTER_SECONDS.get(category))
        payload.setdefault("is_stale", False)

    @staticmethod
    def _normalize_source(value: Any, fallback: str = "unknown") -> str:
        source = str(value or fallback).strip()
        source = SOURCE_ALIASES.get(source, source)
        return source if source in KNOWN_SOURCES else fallback

    @staticmethod
    def _with_stale_status(payload: Dict[str, Any], now: float, category: str) -> Dict[str, Any]:
        result = dict(payload)
        updated_at = result.get("updated_at")
        stale_after = result.get("stale_after_seconds") or STALE_AFTER_SECONDS.get(category)
        result["stale_after_seconds"] = stale_after
        if updated_at is None or stale_after is None:
            result["is_stale"] = False
            return result
        result["is_stale"] = now - float(updated_at) > float(stale_after)
        return result


state_store = DashboardStateStore()
