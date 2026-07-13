from __future__ import annotations

import math
import random
import time
from typing import Dict, List

from app.data_flow.state_store import DashboardStateStore, state_store


class MockDashboardService:
    """Generate continuous demo data before real UDP/ZMQ inputs are ready."""

    MIN_TICK_INTERVAL_S = 0.18

    def __init__(self, store: DashboardStateStore = state_store) -> None:
        self.store = store
        self.start_time = time.time()
        self._last_tick_wall_time = 0.0
        self.line_length = 5000.0
        self.section_length = 500.0
        self.vehicle_offsets = {
            "TRAIN-001": 0.0,
            "TRAIN-002": 950.0,
            "TRAIN-003": 1800.0,
        }
        self.stations = [
            {"station_id": "STA-01", "name": "中心站", "position": 1250.0, "platform_id": "PF-01"},
            {"station_id": "STA-02", "name": "东环站", "position": 3750.0, "platform_id": "PF-02"},
        ]
        self._last_alarm_second = -1

    def tick(self) -> bool:
        now = time.time()
        if (
            self._last_tick_wall_time
            and now - self._last_tick_wall_time < self.MIN_TICK_INTERVAL_S
        ):
            return False

        self._last_tick_wall_time = now
        elapsed = now - self.start_time
        train_positions: Dict[str, float] = {}

        for index, (vehicle_id, offset) in enumerate(self.vehicle_offsets.items(), start=1):
            speed = 42.0 + index * 8.0 + 5.0 * math.sin(elapsed / 5.0 + index)
            position = (offset + elapsed * (speed / 3.6)) % self.line_length
            acceleration = 0.15 * math.cos(elapsed / 4.0 + index)
            ma_limit = min(self.line_length, position + 650.0)
            emergency = speed > 80.0
            mode = "ato" if index != 2 else "manual"
            route_id = "R_MAIN" if index != 3 else "R_BRANCH"
            permission = "stop" if emergency else ("restricted" if ma_limit - position < 700 else "allow")
            signal_state = "red" if permission == "stop" else ("yellow" if permission == "restricted" else "green")
            speed_limit = 30.0 if permission == "restricted" else 60.0
            target_speed = min(speed_limit, max(0.0, speed + acceleration * 10.0))
            station = self._nearest_station(position)
            stop_distance = abs(station["position"] - position)
            parking_phase = self._parking_phase(stop_distance, speed)
            stop_error_cm = self._stop_error_cm(stop_distance, parking_phase)
            current_section = self._section_for_position(position)

            train_positions[vehicle_id] = position
            self.store.update_train(
                vehicle_id,
                {
                    "vehicle_id": vehicle_id,
                    "line_id": "LINE-1",
                    "route_id": route_id,
                    "position": round(position, 2),
                    "speed": round(speed, 2),
                    "acceleration": round(acceleration, 3),
                    "mode": "emergency" if emergency else mode,
                    "is_running": True,
                    "emergency_brake": emergency,
                    "ma_limit": round(ma_limit, 2),
                    "permission": permission,
                    "signal_state": signal_state,
                    "speed_limit": speed_limit,
                    "target_speed": round(target_speed, 2),
                    "energy_kwh": round(45.0 + index * 7.5 + elapsed * (0.02 + index * 0.004), 2),
                    "stop_distance": round(stop_distance, 2),
                    "station_name": station["name"],
                    "parking_phase": parking_phase,
                    "stop_error_cm": stop_error_cm,
                    "platform_id": station["platform_id"],
                    "section_id": current_section["section_id"] if current_section else None,
                    "track_id": current_section["track_id"] if current_section else None,
                    "station_id": current_section["station_id"] if current_section else None,
                    "updated_at": now,
                },
            )
            self.store.update_ma_limits(
                [
                    {
                        "vehicle_id": vehicle_id,
                        "position": round(position, 2),
                        "route_id": route_id,
                        "ma_limit": round(ma_limit, 2),
                        "permission": permission,
                        "signal_state": signal_state,
                        "speed_limit": speed_limit,
                        "target_speed": round(target_speed, 2),
                        "reason": "front_train" if index != 1 else "route_end",
                        "front_vehicle_id": f"TRAIN-{index + 1:03d}" if index != 3 else None,
                        "safe_distance": 120.0,
                        "updated_at": now,
                    }
                ]
            )
            if mode == "ato":
                self.store.update_ato_command(
                    vehicle_id,
                    {
                        "vehicle_id": vehicle_id,
                        "line_id": "LINE-1",
                        "control_mode": "ato",
                        "target_speed": round(target_speed, 2),
                        "target_position": None if target_speed > 5 else round(position + 100.0, 2),
                        "traction_level": 2 if target_speed > speed else 0,
                        "brake_level": 1 if target_speed < speed else 0,
                        "reason": "cruise" if target_speed > 5 else "station_stop",
                        "updated_at": now,
                    },
                )
            self.store.update_driver_input(
                vehicle_id,
                {
                    "vehicle_id": vehicle_id,
                    "line_id": "LINE-1",
                    "source": "mock",
                    "traction_level": 2 + index,
                    "brake_level": 0 if speed < 70 else 1,
                    "direction": "forward",
                    "control_mode": mode if mode in {"manual", "ato"} else "manual",
                    "emergency_button": emergency,
                    "updated_at": now,
                },
            )

        self.store.update_track_info(
            {
                "line_id": "LINE-1",
                "sections": self._build_track_info(),
            }
        )
        self.store.update_yard_layout(self._build_yard_layout())
        self.store.update_signal_state(
            {
                "system_mode": "normal",
                "sections": self._build_sections(train_positions),
                "signals": self._build_signals(train_positions),
                "switches": self._build_switches(elapsed),
                "route_results": self._build_route_results(elapsed),
            }
        )
        voltage = 1500.0 + 35.0 * math.sin(elapsed / 3.0)
        current = 260.0 + 45.0 * math.cos(elapsed / 4.0)
        self.store.update_power(
            {
                "substation_id": "SS-01",
                "voltage": round(voltage, 2),
                "current": round(current, 2),
                "power": round(voltage * current / 1000.0, 2),
                "is_fault": voltage < 1450.0 or voltage > 1550.0,
                "updated_at": now,
            }
        )
        self.store.update_comm(
            {
                "source": "mock",
                "driver_console_connected": True,
                "udp_connected": False,
                "zmq_connected": False,
                "latency_ms": round(8.0 + random.random() * 6.0, 2),
                "packet_loss_count": 0,
                "last_message_at": now,
            }
        )
        self._maybe_add_alarm(now, voltage)
        return True

    def _build_sections(self, train_positions: Dict[str, float]) -> List[dict]:
        sections = []
        for index in range(int(self.line_length / self.section_length)):
            start = index * self.section_length
            end = start + self.section_length
            occupying = [
                vehicle_id
                for vehicle_id, position in train_positions.items()
                if start <= position < end
            ]
            sections.append(
                {
                    "section_id": f"SEG-{index + 1:02d}",
                    "start": start,
                    "end": end,
                    "station_id": self._station_id_for_section(index),
                    "track_id": self._track_id_for_section(index),
                    "occupied": bool(occupying),
                    "vehicle_id": occupying[0] if occupying else None,
                    "occupied_by": occupying[0] if occupying else None,
                    "aspect": "red" if occupying else ("yellow" if index % 4 == 1 else "green"),
                    "locked": bool(occupying),
                    "locked_by_route_id": "R_MAIN" if occupying else None,
                    "condition": "normal",
                }
            )
        return sections

    def _build_signals(self, train_positions: Dict[str, float]) -> List[dict]:
        signals = []
        occupied_indexes = {
            int(position // self.section_length)
            for position in train_positions.values()
        }
        for index in range(10):
            if index in occupied_indexes:
                state = "red"
            elif index - 1 in occupied_indexes:
                state = "yellow"
            else:
                state = "green"
            signals.append(
                {
                    "signal_id": f"SIG-{index + 1:02d}",
                    "position": index * self.section_length,
                    "state": state,
                    "station_id": self._station_id_for_section(index),
                    "track_id": self._track_id_for_section(index),
                    "section_id": f"SEG-{index + 1:02d}",
                    "direction": "up",
                    "protects_switch_id": "SW-01" if index == 3 else ("SW-02" if index == 6 else None),
                    "protects_section_id": f"SEG-{min(index + 2, 10):02d}",
                    "signal_type": "出站" if index in {2, 7} else "区间",
                    "route_id": "R_MAIN",
                    "signal_state": state,
                    "permission": "stop" if state == "red" else ("restricted" if state == "yellow" else "allow"),
                }
            )
        return signals

    def _build_track_info(self) -> List[dict]:
        sections = []
        for index in range(int(self.line_length / self.section_length)):
            start = index * self.section_length
            end = start + self.section_length
            has_station = index in {2, 7}
            sections.append(
                {
                    "section_id": f"SEG-{index + 1:02d}",
                    "line_id": "LINE-1",
                    "track_seg_id": f"T{index + 1:02d}",
                    "start": start,
                    "end": end,
                    "gradient": 8.0 if index in {1, 5} else 0.0,
                    "speed_limit": 45.0 if has_station else 60.0,
                    "station_id": "STA-01" if index == 2 else ("STA-02" if index == 7 else None),
                    "track_id": self._track_id_for_section(index),
                    "stop_position": end - 50.0 if has_station else None,
                }
            )
        return sections

    def _build_switches(self, elapsed: float) -> List[dict]:
        reverse = int(elapsed // 20) % 2 == 0
        return [
            {
                "switch_id": "SW-01",
                "station_id": "STA-01",
                "switch_type": "single",
                "connects": ["STA-01-T1", "STA-01-T2", "STA-01-T3"],
                "normal_to": "STA-01-T1",
                "reverse_to": "STA-01-T2",
                "active_to": "STA-01-T2" if reverse else "STA-01-T1",
                "position": "reverse" if reverse else "normal",
                "turnout_id": "SW-01",
                "routing": "reverse" if reverse else "normal",
                "state": "reverse" if reverse else "normal",
                "locked": True,
                "locked_by_route_id": "R_MAIN",
                "related_section": "SEG-04",
                "reason": "route_locked",
            },
            {
                "switch_id": "SW-02",
                "station_id": "STA-02",
                "switch_type": "single",
                "connects": ["STA-02-T1", "STA-02-T2", "STA-02-T3"],
                "normal_to": "STA-02-T1",
                "reverse_to": "STA-02-T2",
                "active_to": "STA-02-T1" if reverse else "STA-02-T2",
                "position": "normal" if reverse else "reverse",
                "turnout_id": "SW-02",
                "routing": "normal" if reverse else "reverse",
                "state": "normal" if reverse else "reverse",
                "locked": True,
                "locked_by_route_id": "R_BRANCH",
                "related_section": "SEG-07",
                "reason": "route_locked",
            },
        ]

    def _build_route_results(self, elapsed: float) -> List[dict]:
        reverse = int(elapsed // 20) % 2 == 0
        return [
            {
                "vehicle_id": "TRAIN-003",
                "route_id": "R_BRANCH",
                "allowed": reverse,
                "reason": None if reverse else "switch_locked_conflict",
                "required_switch_id": "SW-01",
                "required_position": "reverse",
                "current_position": "reverse" if reverse else "normal",
                "locked_by_route_id": "R_MAIN" if not reverse else None,
            }
        ]

    def _station_id_for_section(self, index: int) -> str | None:
        if index in {1, 2, 3}:
            return "STA-01"
        if index in {6, 7, 8}:
            return "STA-02"
        return None

    def _track_id_for_section(self, index: int) -> str:
        station_id = self._station_id_for_section(index)
        if station_id is None:
            return "LINE-1-UP"
        if index in {2, 7}:
            return f"{station_id}-T1"
        if index in {3, 8}:
            return f"{station_id}-T2"
        return f"{station_id}-T3"

    def _section_for_position(self, position: float) -> dict | None:
        for index in range(int(self.line_length / self.section_length)):
            start = index * self.section_length
            end = start + self.section_length
            if start <= position < end:
                return {
                    "section_id": f"SEG-{index + 1:02d}",
                    "track_id": self._track_id_for_section(index),
                    "station_id": self._station_id_for_section(index),
                }
        return None

    def _build_yard_layout(self) -> dict:
        stations = []
        yard_tracks = []
        yard_switches = []
        yard_signals = []
        yard_sections = []
        for station_index, station in enumerate(self.stations):
            station_id = station["station_id"]
            station_name = "Central Station" if station_id == "STA-01" else "East Loop Station"
            y_base = 120 + station_index * 180
            section_ids = [
                f"SEG-{index + 1:02d}"
                for index in range(int(self.line_length / self.section_length))
                if self._station_id_for_section(index) == station_id
            ]
            tracks = [
                {
                    "track_id": f"{station_id}-T1",
                    "track_name": "Track 1",
                    "station_id": station_id,
                    "track_type": "main",
                    "direction": "up",
                    "section_ids": [item for item in section_ids if item.endswith("03") or item.endswith("08")],
                    "geometry": {"type": "polyline", "points": [[0, y_base], [280, y_base]]},
                },
                {
                    "track_id": f"{station_id}-T2",
                    "track_name": "Track 2",
                    "station_id": station_id,
                    "track_type": "arrival_departure",
                    "direction": "down",
                    "section_ids": [item for item in section_ids if item.endswith("04") or item.endswith("09")],
                    "geometry": {"type": "polyline", "points": [[26, y_base + 40], [250, y_base + 40]]},
                },
                {
                    "track_id": f"{station_id}-T3",
                    "track_name": "Lead track",
                    "station_id": station_id,
                    "track_type": "siding",
                    "direction": "bidirectional",
                    "section_ids": [item for item in section_ids if item.endswith("02") or item.endswith("07")],
                    "geometry": {"type": "polyline", "points": [[34, y_base - 40], [214, y_base - 40]]},
                },
            ]
            reverse_branch_active = station_id == "STA-01"
            branch_geometries = [
                {
                    "branch_id": "main",
                    "branch_type": "straight",
                    "from_track_id": f"{station_id}-T1",
                    "to_track_id": f"{station_id}-T1",
                    "geometry": {
                        "type": "polyline",
                        "points": [[108, y_base], [140, y_base], [212, y_base]],
                    },
                },
                {
                    "branch_id": "reverse",
                    "branch_type": "diverging",
                    "from_track_id": f"{station_id}-T1",
                    "to_track_id": f"{station_id}-T2",
                    "geometry": {
                        "type": "polyline",
                        "points": [[140, y_base], [164, y_base + 8], [194, y_base + 22], [224, y_base + 40]],
                    },
                },
                {
                    "branch_id": "siding",
                    "branch_type": "diverging",
                    "from_track_id": f"{station_id}-T1",
                    "to_track_id": f"{station_id}-T3",
                    "geometry": {
                        "type": "polyline",
                        "points": [[140, y_base], [120, y_base - 8], [96, y_base - 24], [70, y_base - 40]],
                    },
                },
            ]
            switch = {
                "switch_id": f"SW-{station_index + 1:02d}",
                "station_id": station_id,
                "switch_type": "single",
                "connects": [track["track_id"] for track in tracks],
                "approach_track_id": f"{station_id}-T1",
                "normal_to": f"{station_id}-T1",
                "reverse_to": f"{station_id}-T2",
                "active_to": f"{station_id}-T2" if reverse_branch_active else f"{station_id}-T1",
                "geometry": {"type": "point", "x": 140, "y": y_base},
                "branch_geometries": branch_geometries,
            }
            signals = [
                {
                    "signal_id": f"SIG-{3 if station_id == 'STA-01' else 8:02d}",
                    "station_id": station_id,
                    "track_id": f"{station_id}-T1",
                    "direction": "up",
                    "protects_switch_id": switch["switch_id"],
                    "protects_section_id": section_ids[-1] if section_ids else None,
                    "geometry": {"type": "point", "x": 30, "y": y_base - 24},
                }
            ]
            sections = [
                {
                    "section_id": section_id,
                    "station_id": station_id,
                    "track_id": self._track_id_for_section(int(section_id.split("-")[-1]) - 1),
                    "geometry": {"type": "polyline", "points": [[0, y_base], [280, y_base]]},
                }
                for section_id in section_ids
            ]
            station_payload = {
                "station_id": station_id,
                "station_name": station_name,
                "track_ids": [track["track_id"] for track in tracks],
                "switch_ids": [switch["switch_id"]],
                "signal_ids": [signal["signal_id"] for signal in signals],
                "section_ids": section_ids,
                "tracks": tracks,
                "switches": [switch],
                "signals": signals,
                "sections": sections,
            }
            stations.append(station_payload)
            yard_tracks.extend(tracks)
            yard_switches.append(switch)
            yard_signals.extend(signals)
            yard_sections.extend(sections)
        return {
            "line_id": "LINE-1",
            "stations": stations,
            "yard_tracks": yard_tracks,
            "yard_switches": yard_switches,
            "yard_signals": yard_signals,
            "yard_sections": yard_sections,
            "updated_at": time.time(),
        }

    def build_yard_layout_seed(self) -> dict:
        return self._build_yard_layout()

    def _nearest_station(self, position: float) -> dict:
        return min(self.stations, key=lambda station: abs(station["position"] - position))

    @staticmethod
    def _parking_phase(stop_distance: float, speed: float) -> str:
        if stop_distance <= 2.0 and speed < 0.5:
            return "stopped"
        if stop_distance <= 20.0:
            return "docking"
        if stop_distance <= 120.0:
            return "braking"
        if stop_distance <= 450.0:
            return "approaching"
        return "cruising"

    @staticmethod
    def _stop_error_cm(stop_distance: float, parking_phase: str) -> float:
        if parking_phase == "stopped":
            return round(min(50.0, stop_distance * 100.0), 1)
        if parking_phase == "docking":
            return round(stop_distance * 100.0, 1)
        return round(min(500.0, stop_distance * 12.0), 1)

    def _maybe_add_alarm(self, now: float, voltage: float) -> None:
        current_second = int(now)
        if current_second == self._last_alarm_second:
            return
        if current_second % 17 == 0:
            self._last_alarm_second = current_second
            self.store.add_alarm(
                {
                    "alarm_id": f"ALM-{current_second}",
                    "level": "warning",
                    "source": "POWER" if voltage < 1470 else "SIGNAL",
                    "message": "Mock warning: check voltage or section occupancy",
                    "timestamp": now,
                }
            )


mock_dashboard_service = MockDashboardService()
