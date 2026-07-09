from __future__ import annotations

import math
import random
import time
from typing import Dict, List

from app.data_flow.state_store import DashboardStateStore, state_store


class MockDashboardService:
    """Generate continuous demo data before real UDP/ZMQ inputs are ready."""

    def __init__(self, store: DashboardStateStore = state_store) -> None:
        self.store = store
        self.start_time = time.time()
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

    def tick(self) -> None:
        now = time.time()
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
                    "stop_position": end - 50.0 if has_station else None,
                }
            )
        return sections

    def _build_switches(self, elapsed: float) -> List[dict]:
        reverse = int(elapsed // 20) % 2 == 0
        return [
            {
                "switch_id": "SW-01",
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
