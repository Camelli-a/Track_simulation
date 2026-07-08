import argparse
import json
import time

from .evaluation.recorder import RunRecorder
from .evaluation.report import print_report
from .message_router import MessageRouter
from .scenario.scenario_runner import ScenarioRunner
from .scenario.scenarios import SCENARIOS
from .train_manager import TrainManager
from .zmq_bus import ZmqPublisher


def main():
    parser = argparse.ArgumentParser(description="Run a vehicle simulation scenario.")
    parser.add_argument(
        "--scenario",
        default="normal_station_stop",
        choices=list(SCENARIOS.keys()),
    )
    parser.add_argument("--dt", type=float, default=0.1)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--target-stop", type=float, default=None)
    parser.add_argument("--vehicle-id", default="TRAIN-001")
    parser.add_argument("--log-dir", default="logs/vehicle_runs")
    parser.add_argument("--no-sleep", action="store_true")
    args = parser.parse_args()

    manager = TrainManager()
    router = MessageRouter(manager, default_dt=args.dt)
    recorder = RunRecorder(output_dir=args.log_dir)

    scenario = SCENARIOS[args.scenario]()
    runner = ScenarioRunner(scenario, router, realtime=not args.no_sleep)

    publisher = ZmqPublisher() if args.publish else None

    print(f"Running scenario: {scenario.name}")
    print(scenario.description)

    runner.start()

    try:
        while not runner.is_finished():
            runner.tick()

            train_states = manager.step_all(args.dt)
            for state in train_states:
                recorder.record_train_state(state)

                if publisher is not None:
                    publisher.publish(state)

                print(json.dumps(state, ensure_ascii=False))

            for train in manager.trains.values():
                if train.last_alarm is not None:
                    recorder.record_alarm(train.last_alarm)

                    if publisher is not None:
                        publisher.publish(train.last_alarm)

                    print(json.dumps(train.last_alarm, ensure_ascii=False))
                    train.last_alarm = None

            runner.advance(args.dt)
            if not args.no_sleep:
                time.sleep(args.dt)
    finally:
        if publisher is not None:
            publisher.close()

    print(f"\nLog saved to: {recorder.path}")
    print_report(
        str(recorder.path),
        target_stop_position=args.target_stop,
        vehicle_id=args.vehicle_id,
    )


if __name__ == "__main__":
    main()
