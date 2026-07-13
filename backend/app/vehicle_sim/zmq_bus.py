import queue
from typing import Iterable, Optional

from app.communication.message_bus import MessageBus


DEFAULT_TOPICS = [
    "driver_input",
    "driver_desk_binding",
    "ato_command",
    "ma_state",
    "speed_constraint",
    "signal_state",
    "interlocking_state",
    "power_state",
    "comm_state",
    "track_info",
    "fault_event",
    "set_train_state",
    "add_train",
    "remove_train",
    "clear_trains",
    "reset_trains",
]


def normalize_message(message: dict) -> dict:
    if "topic" in message and "data" in message:
        return {
            **message.get("data", {}),
            "type": message["topic"],
            "timestamp": message.get("timestamp"),
        }
    return message


class ZmqPublisher:
    def __init__(self, pub_address: Optional[str] = None):
        self.bus = MessageBus(pub_address=pub_address)
        self.bus.start()

    def publish(self, message: dict):
        message = normalize_message(message)
        topic = message.get("type")
        if not topic:
            raise ValueError("message must include 'type' or 'topic'")

        data = {
            key: value
            for key, value in message.items()
            if key not in {"type", "timestamp"}
        }
        self.bus.publish(topic, data)

    def close(self):
        self.bus.stop()


class ZmqSubscriber:
    def __init__(
        self,
        sub_address: Optional[str] = None,
        topics: Optional[Iterable[str]] = None,
    ):
        self.bus = MessageBus(sub_address=sub_address)
        self.messages: queue.Queue[dict] = queue.Queue()
        self.topics = list(topics or DEFAULT_TOPICS)
        self.bus.start()

        for topic in self.topics:
            self.bus.subscribe(topic, self._enqueue)

    def _enqueue(self, topic: str, data: dict):
        self.messages.put(
            {
                "type": topic,
                **data,
            }
        )

    def receive_nowait(self):
        try:
            return self.messages.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self.bus.stop()
