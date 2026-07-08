"""
ZMQ mock publisher used when hardware or algorithm processes are not ready.

It publishes a small multi-train scenario so the dashboard can demonstrate
vehicle tracking, section occupancy, MA boundaries, power data, and alarms.
"""

import logging
import random
import threading
import time
from typing import Dict, List, Optional

from app.communication.message_bus import MessageBus

logger = logging.getLogger(__name__)


class MockPublisher:
    """Publish multi-module mock data to the MessageBus."""

    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self.bus = MessageBus()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.start_time = time.time()
        self.line_length = 5000.0
        self.vehicles = [
            {"vehicle_id": "TRAIN-001", "offset": 180.0, "base_speed": 48.0, "route_id": "R_MAIN", "mode": "ato"},
            {"vehicle_id": "TRAIN-002", "offset": 1180.0, "base_speed": 42.0, "route_id": "R_MAIN", "mode": "manual"},
            {"vehicle_id": "TRAIN-003", "offset": 2360.0, "base_speed": 36.0, "route_id": "R_BRANCH", "mode": "atp"},
        ]

    def start(self):
        self.bus.start()
        self._running = True
        self._thread = threading.Thread(
            target=self._publish_loop,
            daemon=True,
            name="MockPublisher",
        )
        self._thread.start()
        logger.info("MockPublisher started (interval=%ss, vehicles=%s)", self.interval, len(self.vehicles))

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self.bus.stop()
        logger.info("MockPublisher stopped")

    def _publish_loop(self):
        while self._running:
            try:
                train_states = self._build_train_states()
                self._publish_train_states(train_states)
                self._publish_signal_state(train_states)
                self._publish_ma_state(train_states)
                self._publish_power_state()
                self._publish_comm_state()

                if random.random() < 0.18:
                    self._publish_alarm()

                time.sleep(self.interval)
            except Exception as exc:
                logger.error("Error in mock publish loop: %s", exc, exc_info=True)

    def _build_train_states(self) -> List[Dict[str, object]]:
        """Generate smooth multi-train states instead of random jumping points."""

        elapsed = time.time() - self.start_time
        train_states: List[Dict[str, object]] = []
        for index, spec in enumerate(self.vehicles, start=1):
            speed = float(spec["base_speed"]) + 5.0 * random.uniform(-1.0, 1.0)
            position = (float(spec["offset"]) + elapsed * (speed / 3.6)) % self.line_length
            acceleration = random.uniform(-0.35, 0.35)
            emergency = speed > 90.0
            train_states.append(
                {
                    "vehicle_id": spec["vehicle_id"],
                    "line_id": "LINE-1",
                    "position": round(position, 1),
                    "speed": round(speed, 1),
                    "acceleration": round(acceleration, 2),
                    "mode": "emergency" if emergency else spec["mode"],
                    "is_running": True,
                    "emergency_brake": emergency,
                    "route_id": spec["route_id"],
                    "train_length": 120.0,
                    "energy_kwh": round(40.0 + index * 8.0 + elapsed * 0.03, 2),
                }
            )
        return train_states

    def _publish_train_states(self, train_states: List[Dict[str, object]]) -> None:
        for data in train_states:
            self.bus.publish("train_state", data)

    def _publish_signal_state(self, train_states: List[Dict[str, object]]) -> None:
        states = ["red", "yellow", "green"]
        data = {
            "system_mode": "normal",
            "signals": [
                {
                    "signal_id": f"SIG-{index:02d}",
                    "position": index * 500.0,
                    "state": random.choice(states),
                }
                for index in range(1, 11)
            ],
            "sections": [self._build_section(index, train_states) for index in range(10)],
            "switches": [
                {
                    "switch_id": f"SW-{index:02d}",
                    "position": random.choice(["normal", "reverse"]),
                    "locked": random.choice([True, False]),
                    "related_section": f"SEG-{index:02d}",
                }
                for index in range(1, 4)
            ],
        }
        self.bus.publish("signal_state", data)

    def _build_section(self, index: int, train_states: List[Dict[str, object]]) -> Dict[str, object]:
        start = index * 500.0
        end = (index + 1) * 500.0
        occupying = [
            str(train["vehicle_id"])
            for train in train_states
            if start <= float(train["position"]) < end
        ]
        return {
            "section_id": f"SEG-{index:02d}",
            "start": start,
            "end": end,
            "occupied": bool(occupying),
            "vehicle_id": occupying[0] if occupying else None,
            "condition": "normal",
        }

    def _publish_ma_state(self, train_states: List[Dict[str, object]]) -> None:
        ordered = sorted(train_states, key=lambda item: float(item["position"]))
        front_by_id = {}
        for index, train in enumerate(ordered):
            front_by_id[train["vehicle_id"]] = ordered[index + 1] if index + 1 < len(ordered) else None

        data = {
            "ma_limits": [
                self._build_ma_limit(train, front_by_id[train["vehicle_id"]])
                for train in train_states
            ]
        }
        self.bus.publish("ma_state", data)

    def _build_ma_limit(
        self,
        train: Dict[str, object],
        front_train: Optional[Dict[str, object]],
    ) -> Dict[str, object]:
        position = float(train["position"])
        if front_train:
            ma_limit = max(position, float(front_train["position"]) - 180.0)
            reason = "front_train"
            front_vehicle_id = str(front_train["vehicle_id"])
        else:
            ma_limit = self.line_length
            reason = "route_end"
            front_vehicle_id = None

        distance_to_ma = max(0.0, ma_limit - position)
        speed_limit = 35.0 if distance_to_ma < 300.0 else 80.0
        return {
            "vehicle_id": train["vehicle_id"],
            "position": round(position, 1),
            "route_id": train["route_id"],
            "ma_limit": round(ma_limit, 1),
            "distance_to_ma": round(distance_to_ma, 1),
            "permission": "restricted" if distance_to_ma < 300.0 else "allow",
            "signal_state": "yellow" if distance_to_ma < 300.0 else "green",
            "speed_limit": speed_limit,
            "target_speed": min(float(train["speed"]), speed_limit),
            "reason": reason,
            "front_vehicle_id": front_vehicle_id,
            "safe_distance": 180.0,
        }

    def _publish_power_state(self) -> None:
        voltage = round(random.uniform(1450, 1550), 2)
        current = round(random.uniform(220, 420), 2)
        data = {
            "substation_id": "SS-01",
            "voltage": voltage,
            "current": current,
            "power": round(voltage * current / 1000.0, 2),
            "is_fault": voltage < 1460.0 or voltage > 1540.0,
        }
        self.bus.publish("power_state", data)

    def _publish_comm_state(self) -> None:
        data = {
            "source": "mock",
            "driver_console_connected": True,
            "zmq_connected": True,
            "last_message_at": time.time(),
        }
        self.bus.publish("comm_state", data)

    def _publish_alarm(self) -> None:
        data = {
            "alarm_id": f"ALM-{random.randint(1, 999):03d}",
            "level": random.choice(["info", "warning", "critical"]),
            "source": random.choice(["ATP", "ATO", "SIGNAL", "POWER", "COMM"]),
            "vehicle_id": random.choice([str(vehicle["vehicle_id"]) for vehicle in self.vehicles]),
            "message": random.choice(
                [
                    "Train is close to MA limit",
                    "Signal timeout detected",
                    "Power voltage drop",
                    "Communication latency high",
                ]
            ),
        }
        self.bus.publish("alarm_event", data)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    publisher = MockPublisher(interval=2.0)
    publisher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        publisher.stop()
