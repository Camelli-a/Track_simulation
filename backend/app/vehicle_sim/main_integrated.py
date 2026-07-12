import argparse
import json
import time

from .message_router import MessageRouter
from .train_manager import TrainManager
from .zmq_bus import ZmqPublisher, ZmqSubscriber


def main():
    parser = argparse.ArgumentParser(description="Run integrated vehicle simulation.")
    parser.add_argument("--dt", type=float, default=0.1)
    parser.add_argument("--no-zmq", action="store_true")
    parser.add_argument("--zmq-pub-address", default=None)
    parser.add_argument("--zmq-sub-address", default=None)
    parser.add_argument("--steps", type=int, default=None)
    args = parser.parse_args()

    manager = TrainManager()
    router = MessageRouter(manager, default_dt=args.dt)

    publisher = None if args.no_zmq else ZmqPublisher(args.zmq_pub_address)
    subscriber = None if args.no_zmq else ZmqSubscriber(args.zmq_sub_address)

    print("vehicle_sim integrated mode started")

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
