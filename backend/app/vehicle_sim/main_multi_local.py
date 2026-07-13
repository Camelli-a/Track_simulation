import argparse
import json
import time
from typing import Optional

from .line_data_loader import build_initial_train_configs, build_track_map_from_line_layout
from .models import DriverInput
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
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--spacing", type=float, default=300.0)
    parser.add_argument("--start-position", type=float, default=0.0)
    parser.add_argument("--line-layout", default=None)
    parser.add_argument(
        "--zmq-pub-address",
        "--zmq-address",
        default=None,
        help="Publisher address for the MessageBus broker backend.",
    )
    args = parser.parse_args()

    track = build_track_map_from_line_layout(args.line_layout)
    trains = []
    for config in build_initial_train_configs(
        args.count,
        spacing_m=args.spacing,
        start_position_m=args.start_position,
    ):
        train = Train(
            config["vehicle_id"],
            config["line_id"],
            track,
            train_index=config["train_index"],
        )
        train.state.position = config["position_m"]
        trains.append(train)

    publisher: Optional[ZmqPublisher] = (
        ZmqPublisher(args.zmq_pub_address) if args.use_zmq else None
    )

    try:
        for i in range(args.steps):
            for train in trains:
                train.step_manual(build_driver_input(train, i), args.dt)
                train.step_tick(args.dt)
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
