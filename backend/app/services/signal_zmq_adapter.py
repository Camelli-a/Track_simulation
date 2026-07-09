import logging
import threading
import time

from app.communication.message_bus import MessageBus
from app.services.signal_ato_controller import AtoController
from app.services.signal_control import calculate_signal_snapshot
from app.services.signal_route_lifecycle import RouteLifecycleManager

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
        route_lifecycle_manager=None,
        ato_controller=None,
    ):
        self.bus = bus or MessageBus()
        self.publish_interval_seconds = publish_interval_seconds
        self.stale_timeout_seconds = stale_timeout_seconds
        self.publish_on_update = publish_on_update
        self.time_func = time_func
        self.route_lifecycle_manager = route_lifecycle_manager or RouteLifecycleManager(
            time_func=self.time_func
        )
        self.ato_controller = ato_controller or AtoController()
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
        self.bus.subscribe("route_request", self.on_route_request)
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
        if "fault_speed_limit" in data:
            try:
                train_state["fault_speed_limit"] = float(data["fault_speed_limit"])
            except (TypeError, ValueError):
                train_state["fault_speed_limit"] = data["fault_speed_limit"]
        if "emergency_brake" in data:
            train_state["emergency_brake"] = self._to_bool(data["emergency_brake"])

        vehicle_id = train_state["vehicle_id"]
        with self.lock:
            self.train_states_by_id[vehicle_id] = train_state
            self.train_last_update_at[vehicle_id] = self.time_func()
            self.active_alarm_keys.discard(f"train_state_timeout:{vehicle_id}")

        if self.publish_on_update:
            self.publish_signal_outputs()

    def on_route_request(self, topic: str, data: dict) -> None:
        request_type = str(data.get("request_type", "open")).strip().lower()
        normalized_request = None

        if request_type == "open":
            normalized_request = self._open_route_request(data)
        elif request_type == "cancel":
            normalized_request = self._cancel_route_request(data)
        elif request_type == "clear":
            with self.lock:
                self.route_requests.clear()
                train_states = list(self.train_states_by_id.values())
            normalized_request = {"request_type": "clear"}
        else:
            self._publish_invalid_route_request_alarm(
                data,
                "unsupported_request_type",
            )

        if normalized_request is None:
            return

        if request_type != "clear":
            with self.lock:
                train_states = list(self.train_states_by_id.values())

        self.route_lifecycle_manager.handle_route_request(
            normalized_request,
            train_states=train_states,
        )

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

        self.route_lifecycle_manager.update_by_train_states(train_states)
        snapshot = calculate_signal_snapshot(train_states, route_requests)
        snapshot = self.route_lifecycle_manager.apply_locks_to_snapshot(snapshot)
        self._apply_train_state_timeout_fail_safe(snapshot, last_update_by_id, now)

        self.bus.publish(
            "signal_state",
            {
                "system_mode": snapshot.get("system_mode", "normal"),
                "signals": snapshot["signals"],
                "sections": snapshot["sections"],
                "switches": snapshot["switches"],
                "route_results": snapshot["route_results"],
                "route_states": snapshot.get("route_states", []),
            },
        )
        self.bus.publish(
            "ma_state",
            {
                "ma_limits": snapshot["ma_limits"],
            },
        )
        self.bus.publish(
            "ato_command",
            {
                "commands": self.ato_controller.build_ato_commands(
                    train_states,
                    snapshot.get("ma_limits", []),
                    snapshot.get("route_states", []),
                ),
            },
        )

    def _open_route_request(self, data: dict) -> dict | None:
        vehicle_id = data.get("vehicle_id")
        route_id = data.get("route_id")
        if not vehicle_id:
            self._publish_invalid_route_request_alarm(data, "missing_vehicle_id")
            return None
        if not route_id:
            self._publish_invalid_route_request_alarm(data, "missing_route_id")
            return None

        request = {
            "request_id": data.get("request_id") or f"REQ-{vehicle_id}-{route_id}",
            "vehicle_id": vehicle_id,
            "route_id": route_id,
            "request_type": "open",
            "priority": data.get("priority", 0),
            "last_update_at": self.time_func(),
        }

        with self.lock:
            for index, existing_request in enumerate(self.route_requests):
                if (
                    existing_request.get("vehicle_id") == vehicle_id
                    and existing_request.get("route_id") == route_id
                ):
                    self.route_requests[index] = request
                    break
            else:
                self.route_requests.append(request)
        return request

    def _cancel_route_request(self, data: dict) -> dict | None:
        vehicle_id = data.get("vehicle_id")
        route_id = data.get("route_id")
        if not vehicle_id:
            self._publish_invalid_route_request_alarm(data, "missing_vehicle_id")
            return None

        with self.lock:
            if route_id:
                self.route_requests = [
                    request
                    for request in self.route_requests
                    if not (
                        request.get("vehicle_id") == vehicle_id
                        and request.get("route_id") == route_id
                    )
                ]
            else:
                self.route_requests = [
                    request
                    for request in self.route_requests
                    if request.get("vehicle_id") != vehicle_id
                ]
        return {
            "request_id": data.get("request_id"),
            "vehicle_id": vehicle_id,
            "route_id": route_id,
            "request_type": "cancel",
        }

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

    def _publish_invalid_route_request_alarm(self, data: dict, reason: str) -> None:
        self.bus.publish(
            "alarm_event",
            {
                "alarm_id": "SIGNAL-INVALID-ROUTE-REQUEST",
                "source": "SIGNAL",
                "level": "warning",
                "category": "route_request",
                "vehicle_id": data.get("vehicle_id"),
                "message": "Invalid route_request message",
                "occurred_at": self.time_func(),
                "details": {
                    "reason": reason,
                    "request_type": data.get("request_type", "open"),
                    "route_id": data.get("route_id"),
                    "request_id": data.get("request_id"),
                },
            },
        )

    def _to_bool(self, value) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
