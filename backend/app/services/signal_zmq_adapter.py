import logging
import threading
import time

from app.communication.message_bus import MessageBus
from app.services.signal_control import calculate_signal_snapshot

logger = logging.getLogger(__name__)

PUBLISH_INTERVAL_SECONDS = 0.25
TRAIN_STATE_STALE_TIMEOUT_SECONDS = 1.6


class SignalZmqAdapter:
    def __init__(
        self,
        bus=None,
        publish_interval_seconds=PUBLISH_INTERVAL_SECONDS,
        stale_timeout_seconds=TRAIN_STATE_STALE_TIMEOUT_SECONDS,
        publish_on_update=True,
        time_func=time.time,
    ):
        self.bus = bus or MessageBus()
        self.publish_interval_seconds = publish_interval_seconds
        self.stale_timeout_seconds = stale_timeout_seconds
        self.publish_on_update = publish_on_update
        self.time_func = time_func
        self.train_states_by_id = {}
        self.train_last_update_at = {}
        self.route_requests = []
        self.active_alarm_keys = set()
        self.stop_event = threading.Event()
        self.publish_thread = None
        self.lock = threading.Lock()

    def start(self):
        self.bus.start()
        self.bus.subscribe("train_state", self.on_train_state)
        self.stop_event.clear()
        if self.publish_thread is None or not self.publish_thread.is_alive():
            self.publish_thread = threading.Thread(
                target=self._publish_loop,
                daemon=True,
            )
            self.publish_thread.start()
        logger.info("SignalZmqAdapter started")

    def stop(self):
        self.stop_event.set()
        if self.publish_thread is not None:
            self.publish_thread.join(timeout=2.0)
        self.bus.stop()
        logger.info("SignalZmqAdapter stopped")

    def on_train_state(self, topic: str, data: dict):
        train_state = {
            "vehicle_id": data["vehicle_id"],
            "position": data["position"],
            "speed": data["speed"],
            "route_id": data.get("route_id", "R_MAIN"),
        }
        if "train_length" in data:
            train_state["train_length"] = data["train_length"]

        vehicle_id = train_state["vehicle_id"]
        with self.lock:
            self.train_states_by_id[vehicle_id] = train_state
            self.train_last_update_at[vehicle_id] = self.time_func()
            self.active_alarm_keys.discard(f"train_state_timeout:{vehicle_id}")

        if self.publish_on_update:
            self.publish_signal_outputs()

    def publish_signal_outputs(self, now=None):
        if now is None:
            now = self.time_func()
        with self.lock:
            train_states = list(self.train_states_by_id.values())
            route_requests = list(self.route_requests)
            last_update_by_id = dict(self.train_last_update_at)

        if not train_states:
            return

        snapshot = calculate_signal_snapshot(train_states, route_requests)
        self._apply_train_state_timeout_fail_safe(snapshot, last_update_by_id, now)

        self.bus.publish(
            "signal_state",
            {
                "system_mode": snapshot.get("system_mode", "normal"),
                "signals": snapshot["signals"],
                "sections": snapshot["sections"],
                "switches": snapshot["switches"],
                "route_results": snapshot["route_results"],
            },
        )
        self.bus.publish(
            "ma_state",
            {
                "ma_limits": snapshot["ma_limits"],
            },
        )

    def _publish_loop(self):
        while not self.stop_event.wait(self.publish_interval_seconds):
            self.publish_signal_outputs()

    def _apply_train_state_timeout_fail_safe(self, snapshot, last_update_by_id, now):
        signals = snapshot.get("signals", [])
        for index, ma_limit in enumerate(snapshot.get("ma_limits", [])):
            vehicle_id = ma_limit["vehicle_id"]
            last_update_at = last_update_by_id.get(vehicle_id)
            if last_update_at is None:
                ma_limit["communication_lost"] = False
                ma_limit["stale_duration"] = 0.0
                continue

            stale_duration = now - last_update_at
            if stale_duration <= self.stale_timeout_seconds:
                ma_limit["communication_lost"] = False
                ma_limit["stale_duration"] = 0.0
                continue

            rounded_stale_duration = round(stale_duration, 3)
            ma_limit["communication_lost"] = True
            ma_limit["stale_duration"] = rounded_stale_duration
            ma_limit["permission"] = "stop"
            ma_limit["signal_state"] = "red"
            ma_limit["speed_limit"] = 0.0
            ma_limit["target_speed"] = 0.0
            ma_limit["reason"] = "train_state_timeout"

            if index < len(signals):
                signals[index]["state"] = "red"
                signals[index]["signal_state"] = "red"
                signals[index]["permission"] = "stop"

            self._publish_train_state_timeout_alarm(
                vehicle_id,
                rounded_stale_duration,
                now,
            )

    def _publish_train_state_timeout_alarm(self, vehicle_id, stale_duration, now):
        alarm_key = f"train_state_timeout:{vehicle_id}"
        with self.lock:
            if alarm_key in self.active_alarm_keys:
                return
            self.active_alarm_keys.add(alarm_key)

        self.bus.publish(
            "alarm_event",
            {
                "alarm_id": f"SIGNAL-{vehicle_id}-TIMEOUT",
                "source": "SIGNAL",
                "level": "critical",
                "category": "communication",
                "vehicle_id": vehicle_id,
                "message": "Train state timeout, applying fail-safe stop permission",
                "occurred_at": now,
                "details": {
                    "stale_duration": round(stale_duration, 3),
                    "timeout_seconds": self.stale_timeout_seconds,
                },
            },
        )
