import argparse
import json
import time
from typing import Optional

from .mock_data import DEFAULT_TRACK
from .models import DriverInput
from .track_map import TrackMap
from .train import Train
from .zmq_publisher import ZmqPublisher


def build_driver_input(train: Train, step_index: int) -> DriverInput:
    return DriverInput(
        vehicle_id=train.state.vehicle_id,
        line_id=train.state.line_id,
        source="mock",
        control_mode="manual",
        traction_level=3 if step_index < 50 else 0,
        brake_level=0 if step_index < 50 else 2,
        direction="forward",
        emergency_button=False,
    )


def main():
    parser = argparse.ArgumentParser(description="Run local multi-train simulation.")
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--dt", type=float, default=0.1)
    parser.add_argument("--sleep", action="store_true")
    parser.add_argument("--use-zmq", action="store_true")
    parser.add_argument("--zmq-address", default="tcp://localhost:5555")
    args = parser.parse_args()

    track = TrackMap(DEFAULT_TRACK)
    trains = [
        Train("TRAIN-001", "LINE-1", track),
        Train("TRAIN-002", "LINE-1", track),
        Train("TRAIN-003", "LINE-1", track),
    ]

    publisher: Optional[ZmqPublisher] = (
        ZmqPublisher(args.zmq_address) if args.use_zmq else None
    )

    try:
        for i in range(args.steps):
            for train in trains:
                train.step_manual(build_driver_input(train, i), args.dt)
                message = train.state.to_protocol()
                print(json.dumps(message, ensure_ascii=False))

                if publisher is not None:
                    publisher.publish(message)

            if args.sleep:
                time.sleep(args.dt)
    finally:
        if publisher is not None:
            publisher.close()


if __name__ == "__main__":
    main()
