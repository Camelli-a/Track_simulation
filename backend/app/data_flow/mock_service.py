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

            train_positions[vehicle_id] = position
            self.store.update_train(
                vehicle_id,
                {
                    "vehicle_id": vehicle_id,
                    "line_id": "LINE-1",
                    "position": round(position, 2),
                    "speed": round(speed, 2),
                    "acceleration": round(acceleration, 3),
                    "mode": "emergency" if emergency else mode,
                    "is_running": True,
                    "emergency_brake": emergency,
                    "ma_limit": round(ma_limit, 2),
                    "updated_at": now,
                },
            )
            self.store.update_driver_input(
                vehicle_id,
                {
                    "vehicle_id": vehicle_id,
                    "source": "mock",
                    "traction_level": 2 + index,
                    "brake_level": 0 if speed < 70 else 1,
                    "direction": "forward",
                    "control_mode": mode if mode in {"manual", "ato"} else "manual",
                    "emergency_button": emergency,
                    "updated_at": now,
                },
            )

        self.store.update_signal_state(
            {
                "sections": self._build_sections(train_positions),
                "signals": self._build_signals(train_positions),
                "switches": self._build_switches(elapsed),
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
                }
            )
        return signals

    def _build_switches(self, elapsed: float) -> List[dict]:
        reverse = int(elapsed // 20) % 2 == 0
        return [
            {
                "switch_id": "SW-01",
                "position": "reverse" if reverse else "normal",
                "locked": True,
                "related_section": "SEG-04",
            },
            {
                "switch_id": "SW-02",
                "position": "normal" if reverse else "reverse",
                "locked": True,
                "related_section": "SEG-07",
            },
        ]

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

