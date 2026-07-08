import json


class ZmqPublisher:
    def __init__(self, address: str = "tcp://localhost:5555"):
        try:
            import zmq
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pyzmq is required for ZMQ publishing. Install backend requirements first."
            ) from exc

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.connect(address)

    def publish(self, message: dict):
        self.socket.send_string(json.dumps(message, ensure_ascii=False))

    def close(self):
        self.socket.close(linger=0)
        self.context.term()
