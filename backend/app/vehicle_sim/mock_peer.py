import argparse
import time

from .zmq_bus import ZmqPublisher


def send(publisher: ZmqPublisher, message: dict):
    publisher.publish(message)
    print("MOCK SEND:", message)


def main():
    parser = argparse.ArgumentParser(description="Publish mock vehicle input messages.")
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--zmq-pub-address", default=None)
    parser.add_argument("--cycles", type=int, default=None)
    args = parser.parse_args()

    publisher = ZmqPublisher(args.zmq_pub_address)
    start = time.time()

    try:
        cycle = 0
        while args.cycles is None or cycle < args.cycles:
            now = time.time()
            elapsed = now - start

            send(
                publisher,
                {
                    "type": "comm_state",
                    "timestamp": now,
                    "source": "mock",
                    "driver_console_connected": True,
                    "zmq_connected": True,
                    "last_message_at": now,
                },
            )
            send(
                publisher,
                {
                    "type": "power_state",
                    "timestamp": now,
                    "substation_id": "SS-01",
                    "voltage": 1500.0,
                    "current": 300.0,
                    "power": 450.0,
                    "is_fault": False,
                },
            )
            send(
                publisher,
                {
                    "type": "ma_state",
                    "timestamp": now,
                    "ma_limits": [
                        {
                            "vehicle_id": "TRAIN-001",
                            "ma_limit": 120.0,
                            "target_speed": 30.0,
                            "reason": "front_train",
                        },
                        {
                            "vehicle_id": "TRAIN-002",
                            "ma_limit": 650.0,
                            "target_speed": 30.0,
                            "reason": "front_train",
                        },
                        {
                            "vehicle_id": "TRAIN-003",
                            "ma_limit": 1200.0,
                            "target_speed": 35.0,
                            "reason": "station_stop",
                        },
                    ],
                },
            )

            if elapsed < 8:
                send(
                    publisher,
                    {
                        "type": "driver_input",
                        "timestamp": now,
                        "vehicle_id": "TRAIN-001",
                        "line_id": "LINE-1",
                        "source": "mock",
                        "control_mode": "manual",
                        "traction_level": 3,
                        "brake_level": 0,
                        "direction": "forward",
                        "emergency_button": False,
                    },
                )
            else:
                send(
                    publisher,
                    {
                        "type": "ato_command",
                        "timestamp": now,
                        "vehicle_id": "TRAIN-001",
                        "line_id": "LINE-1",
                        "control_mode": "ato",
                        "target_speed": 0.0,
                        "target_position": 150.0,
                        "traction_level": 0,
                        "brake_level": 2,
                        "reason": "station_stop",
                    },
                )

            time.sleep(args.interval)
            cycle += 1
    finally:
        publisher.close()


if __name__ == "__main__":
    main()
