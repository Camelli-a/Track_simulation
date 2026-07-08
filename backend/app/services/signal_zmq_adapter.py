import logging
import threading

from app.communication.message_bus import MessageBus
from app.services.signal_control import calculate_signal_snapshot

logger = logging.getLogger(__name__)


class SignalZmqAdapter:
    def __init__(self):
        self.bus = MessageBus()
        self.train_states_by_id = {}
        self.route_requests = []
        self.lock = threading.Lock()

    def start(self):
        self.bus.start()
        self.bus.subscribe("train_state", self.on_train_state)
        logger.info("SignalZmqAdapter started")

    def stop(self):
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

        with self.lock:
            self.train_states_by_id[train_state["vehicle_id"]] = train_state

        self.publish_signal_outputs()

    def publish_signal_outputs(self):
        with self.lock:
            train_states = list(self.train_states_by_id.values())
            route_requests = list(self.route_requests)

        if not train_states:
            return

        snapshot = calculate_signal_snapshot(train_states, route_requests)

        self.bus.publish(
            "signal_state",
            {
                "system_mode": "normal",
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
