import logging
import time

from app.services.signal_zmq_adapter import SignalZmqAdapter


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    adapter = SignalZmqAdapter()
    adapter.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        adapter.stop()


if __name__ == "__main__":
    main()
