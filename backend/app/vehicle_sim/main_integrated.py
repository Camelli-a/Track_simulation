import argparse
import json
import time

from .adapters.id_mapping import vehicle_id_to_index
from .message_router import MessageRouter
from .train_manager import TrainManager
from .zmq_bus import ZmqPublisher, ZmqSubscriber


def infer_train_index(vehicle_id: str) -> int:
    try:
        return vehicle_id_to_index(vehicle_id)
    except ValueError:
        return 1


def main():
    parser = argparse.ArgumentParser(description="Run integrated vehicle simulation.")
    parser.add_argument("--dt", type=float, default=0.1)
    parser.add_argument("--no-zmq", action="store_true")
    parser.add_argument("--zmq-pub-address", default=None)
    parser.add_argument("--zmq-sub-address", default=None)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--vehicle-id", default="TRAIN-001")
    parser.add_argument("--train-index", type=int, default=None)
    parser.add_argument("--initial-position", type=float, default=0.0)
    args = parser.parse_args()

    vehicle_id = args.vehicle_id
    train_index = args.train_index or infer_train_index(vehicle_id)

    manager = TrainManager(initial_count=0)
    result = manager.add_train(
        vehicle_id=vehicle_id,
        slot=train_index,
        position=args.initial_position,
    )
    if not result.get("ok"):
        raise SystemExit(f"failed to create single train process: {result}")

    router = MessageRouter(
        manager,
        default_dt=args.dt,
        owned_vehicle_id=vehicle_id,
    )

    publisher = None if args.no_zmq else ZmqPublisher(args.zmq_pub_address)
    subscriber = None if args.no_zmq else ZmqSubscriber(args.zmq_sub_address)

    print("Single-train vehicle process started")
    print(f"vehicle_id={vehicle_id}")
    print(f"train_index={train_index}")
    print(f"initial_position={args.initial_position}")

    try:
        step_index = 0
        while args.steps is None or step_index < args.steps:
            if subscriber is not None:
                for _ in range(20):
                    msg = subscriber.receive_nowait()
                    if msg is None:
                        break
                    router.handle(msg)

            train_states = manager.step_all(args.dt)
            for state in train_states:
                if publisher is not None:
                    publisher.publish(state)
                print(json.dumps(state, ensure_ascii=False))

            for train in manager.trains.values():
                for state in (
                    train.build_ato_state(),
                    train.build_atp_state(),
                    train.build_door_state(),
                ):
                    if publisher is not None:
                        publisher.publish(state)
                    print(json.dumps(state, ensure_ascii=False))

            for train in manager.trains.values():
                if train.last_alarm is not None:
                    if publisher is not None:
                        publisher.publish(train.last_alarm)
                    print(json.dumps(train.last_alarm, ensure_ascii=False))
                    train.last_alarm = None

            time.sleep(args.dt)
            step_index += 1
    finally:
        if subscriber is not None:
            subscriber.close()
        if publisher is not None:
            publisher.close()


if __name__ == "__main__":
    main()
