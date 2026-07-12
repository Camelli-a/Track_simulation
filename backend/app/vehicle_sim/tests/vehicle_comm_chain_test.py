from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from app.communication.message_bus import MessageBus
from app.vehicle_sim.mock_data import DEFAULT_TRACK
from app.vehicle_sim.models import DriverInput
from app.vehicle_sim.track_map import TrackMap
from app.vehicle_sim.train import Train


MESSAGE_COUNT = 29
REQUIRED_FIELDS = {
    "type",
    "timestamp",
    "vehicle_id",
    "line_id",
    "source",
    "control_mode",
    "traction_level",
    "brake_level",
    "direction",
    "emergency_button",
}


def build_driver_messages() -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    def add(scenario: str, traction: int, brake: int, direction: str = "forward", emergency: bool = False, repeats: int = 1):
        for _ in range(repeats):
            messages.append(
                {
                    "type": "driver_input",
                    "timestamp": time.time(),
                    "sequence_id": len(messages),
                    "scenario": scenario,
                    "vehicle_id": "TRAIN-001",
                    "line_id": "LINE-1",
                    "source": "mock",
                    "control_mode": "manual",
                    "traction_level": traction,
                    "brake_level": brake,
                    "direction": direction,
                    "emergency_button": emergency,
                }
            )

    add("coast_initial", 0, 0, repeats=2)
    add("traction_level_1", 1, 0, repeats=3)
    add("traction_level_2", 2, 0, repeats=3)
    add("traction_level_3", 3, 0, repeats=3)
    add("traction_zero", 0, 0, repeats=4)
    add("brake_level_1", 0, 1, repeats=2)
    add("brake_level_2", 0, 2, repeats=2)
    add("brake_level_3", 0, 3, repeats=2)
    add("traction_and_brake_conflict", 3, 2, repeats=3)
    add("direction_neutral_with_traction", 3, 0, direction="neutral", repeats=2)
    add("emergency_button", 0, 0, emergency=True, repeats=3)
    return messages


def write_ready(path: str | None) -> None:
    if path:
        Path(path).write_text("ready", encoding="utf-8")


def append_jsonl(path: str, record: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def publisher(args: argparse.Namespace) -> int:
    messages = build_driver_messages()
    if args.print_only:
        for message in messages:
            print(json.dumps(message, ensure_ascii=False), flush=True)
        return 0

    bus = MessageBus()
    bus.start()
    time.sleep(args.warmup)
    try:
        for message in messages:
            message["timestamp"] = time.time()
            bus.publish("driver_input", message)
            print(json.dumps({"published": message}, ensure_ascii=False), flush=True)
            time.sleep(args.interval)
    finally:
        bus.stop()
    return 0


def passive_subscriber(args: argparse.Namespace) -> int:
    received: list[dict[str, Any]] = []

    def on_driver_input(topic: str, data: dict) -> None:
        received.append(dict(data))
        append_jsonl(args.out, {"topic": topic, "data": dict(data)})

    bus = MessageBus()
    bus.start()
    bus.subscribe("driver_input", on_driver_input)
    write_ready(args.ready_file)
    deadline = time.time() + args.timeout
    try:
        while time.time() < deadline and len(received) < args.count:
            time.sleep(0.05)
    finally:
        bus.stop()

    print(json.dumps({"received": len(received), "expected": args.count}, ensure_ascii=False), flush=True)
    return 0 if len(received) >= args.count else 2


def vehicle_receiver(args: argparse.Namespace) -> int:
    track = TrackMap(DEFAULT_TRACK)
    train = Train("TRAIN-001", "LINE-1", track)
    records: list[dict[str, Any]] = []
    last_time: float | None = None

    def on_driver_input(topic: str, data: dict) -> None:
        nonlocal last_time
        now = time.time()
        if last_time is None:
            dt = args.default_dt
        else:
            dt = min(max(now - last_time, 0.01), args.max_dt)
        last_time = now

        if data.get("vehicle_id") != train.state.vehicle_id:
            record = {"topic": topic, "input": dict(data), "skipped": True, "reason": "vehicle_id_mismatch"}
            append_jsonl(args.out, record)
            records.append(record)
            return

        driver_input = DriverInput(
            vehicle_id=data["vehicle_id"],
            line_id=data.get("line_id", "LINE-1"),
            source=data.get("source", "mock"),
            control_mode=data.get("control_mode", "manual"),
            traction_level=int(data.get("traction_level", 0)),
            brake_level=int(data.get("brake_level", 0)),
            direction=data.get("direction", "forward"),
            emergency_button=bool(data.get("emergency_button", False)),
        )
        train.step_manual(driver_input, dt)
        train.step_tick(dt)
        state = train.state.to_protocol()
        record = {
            "topic": topic,
            "dt": dt,
            "input": dict(data),
            "state": state,
            "current_traction_level": train.current_traction_level,
            "current_brake_level": train.current_brake_level,
        }
        append_jsonl(args.out, record)
        records.append(record)

        if args.publish_state:
            state_bus.publish("train_state", state)

    bus = MessageBus()
    state_bus = bus
    bus.start()
    bus.subscribe("driver_input", on_driver_input)
    write_ready(args.ready_file)
    deadline = time.time() + args.timeout
    try:
        while time.time() < deadline and len(records) < args.count:
            time.sleep(0.05)
    finally:
        bus.stop()

    print(json.dumps({"processed": len(records), "expected": args.count}, ensure_ascii=False), flush=True)
    return 0 if len(records) >= args.count else 2


def backend_state_subscriber(args: argparse.Namespace) -> int:
    received: list[dict[str, Any]] = []

    def on_train_state(topic: str, data: dict) -> None:
        received.append(dict(data))
        append_jsonl(args.out, {"topic": topic, "data": dict(data)})

    bus = MessageBus()
    bus.start()
    bus.subscribe("train_state", on_train_state)
    write_ready(args.ready_file)
    deadline = time.time() + args.timeout
    try:
        while time.time() < deadline and len(received) < args.count:
            time.sleep(0.05)
    finally:
        bus.stop()

    print(json.dumps({"received": len(received), "expected": args.count}, ensure_ascii=False), flush=True)
    return 0 if len(received) >= args.count else 2


def wait_ready(path: Path, proc: subprocess.Popen, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.05)
    return False


def run_process(command: list[str], cwd: Path, env: dict[str, str], stdout_path: Path) -> subprocess.Popen:
    stdout = open(stdout_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=stdout,
        stderr=subprocess.STDOUT,
        text=True,
    )
    proc._vehicle_test_stdout = stdout
    return proc


def stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
    stdout = getattr(proc, "_vehicle_test_stdout", None)
    if stdout is not None and not stdout.closed:
        stdout.close()


def evaluate_vehicle_records(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        scenario = record.get("input", {}).get("scenario", "unknown")
        by_scenario.setdefault(scenario, []).append(record)

    def first_speed(name: str) -> float:
        return by_scenario[name][0]["state"]["speed"]

    def last_speed(name: str) -> float:
        return by_scenario[name][-1]["state"]["speed"]

    def last_acc(name: str) -> float:
        return by_scenario[name][-1]["state"]["acceleration"]

    rows: list[dict[str, str]] = []

    traction_pass = (
        last_speed("traction_level_1")
        < last_speed("traction_level_2")
        < last_speed("traction_level_3")
        and last_speed("traction_level_3") > first_speed("traction_level_1")
    )
    rows.append(
        {
            "operation": "牵引拉杆推到1/2/3",
            "expected": "speed逐渐增大, position增大",
            "actual": f"L1={last_speed('traction_level_1'):.3f}, L2={last_speed('traction_level_2'):.3f}, L3={last_speed('traction_level_3'):.3f} km/h",
            "passed": "通过" if traction_pass else "失败",
        }
    )

    zero_pass = last_acc("traction_zero") < last_acc("traction_level_3")
    rows.append(
        {
            "operation": "牵引归零",
            "expected": "加速度下降, 速度不再明显增加",
            "actual": f"traction_zero末帧acc={last_acc('traction_zero'):.3f}, traction3末帧acc={last_acc('traction_level_3'):.3f}",
            "passed": "通过" if zero_pass else "失败",
        }
    )

    brake_pass = last_speed("brake_level_3") < first_speed("brake_level_1")
    rows.append(
        {
            "operation": "制动拉杆拉到1/2/3",
            "expected": "speed逐渐下降",
            "actual": f"brake起始={first_speed('brake_level_1'):.3f}, brake3末帧={last_speed('brake_level_3'):.3f} km/h",
            "passed": "通过" if brake_pass else "失败",
        }
    )

    conflict_pass = last_acc("traction_and_brake_conflict") <= 0
    rows.append(
        {
            "operation": "同时牵引和制动>0",
            "expected": "制动优先",
            "actual": f"末帧acc={last_acc('traction_and_brake_conflict'):.3f}, current_brake={by_scenario['traction_and_brake_conflict'][-1]['current_brake_level']}",
            "passed": "通过" if conflict_pass else "失败",
        }
    )

    emergency_state = by_scenario["emergency_button"][-1]["state"]
    emergency_pass = emergency_state["emergency_brake"] is True and emergency_state["mode"] == "emergency"
    rows.append(
        {
            "operation": "emergency_button=true",
            "expected": "emergency_brake=true, mode=emergency",
            "actual": f"emergency_brake={emergency_state['emergency_brake']}, mode={emergency_state['mode']}",
            "passed": "通过" if emergency_pass else "失败",
        }
    )

    neutral_records = by_scenario["direction_neutral_with_traction"]
    neutral_speed_delta = neutral_records[-1]["state"]["speed"] - neutral_records[0]["state"]["speed"]
    neutral_pass = neutral_speed_delta <= 0.05 and last_acc("direction_neutral_with_traction") <= 0
    rows.append(
        {
            "operation": "direction=neutral",
            "expected": "车辆不再执行牵引",
            "actual": f"speed_delta={neutral_speed_delta:.3f} km/h, acc={last_acc('direction_neutral_with_traction'):.3f}",
            "passed": "通过" if neutral_pass else "失败",
        }
    )
    return rows


def orchestrator(args: argparse.Namespace) -> int:
    backend_dir = Path(__file__).resolve().parents[3]
    script = Path(__file__).resolve()
    python = sys.executable
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    processes: list[subprocess.Popen] = []
    broker_proc: subprocess.Popen | None = None
    broker_owned = False

    with tempfile.TemporaryDirectory(prefix="vehicle_comm_chain_", ignore_cleanup_errors=True) as temp_name:
        temp = Path(temp_name)
        module = "app.vehicle_sim.tests.vehicle_comm_chain_test"

        phase1 = subprocess.run(
            [python, "-m", module, "publisher", "--print-only"],
            cwd=str(backend_dir),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        phase1_messages = [
            json.loads(line)
            for line in phase1.stdout.splitlines()
            if line.strip().startswith("{")
        ]
        phase1_valid = (
            phase1.returncode == 0
            and len(phase1_messages) == MESSAGE_COUNT
            and all(REQUIRED_FIELDS <= set(message) for message in phase1_messages)
            and all(0 <= int(message["traction_level"]) <= 4 and 0 <= int(message["brake_level"]) <= 4 for message in phase1_messages)
        )

        try:
            broker_stdout = temp / "broker.log"
            broker_proc = run_process(
                [python, "-m", "app.communication.broker"],
                backend_dir,
                env,
                broker_stdout,
            )
            time.sleep(1.0)
            if broker_proc.poll() is None:
                broker_owned = True
                processes.append(broker_proc)

            phase2_out = temp / "phase2_sub.jsonl"
            phase2_ready = temp / "phase2.ready"
            phase2_proc = run_process(
                [
                    python,
                    "-m",
                    module,
                    "passive-subscriber",
                    "--count",
                    str(MESSAGE_COUNT),
                    "--out",
                    str(phase2_out),
                    "--ready-file",
                    str(phase2_ready),
                ],
                backend_dir,
                env,
                temp / "phase2_sub.log",
            )
            processes.append(phase2_proc)
            phase2_ready_ok = wait_ready(phase2_ready, phase2_proc)
            phase2_pub = subprocess.run(
                [python, "-m", module, "publisher", "--interval", "0.08", "--warmup", "0.8"],
                cwd=str(backend_dir),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            phase2_proc.wait(timeout=15)
            phase2_records = read_jsonl(phase2_out)
            phase2_sequences = [record["data"].get("sequence_id") for record in phase2_records]
            phase2_pass = (
                phase2_ready_ok
                and phase2_pub.returncode == 0
                and len(phase2_records) == MESSAGE_COUNT
                and phase2_sequences == list(range(MESSAGE_COUNT))
            )

            phase3_out = temp / "phase3_vehicle.jsonl"
            phase3_ready = temp / "phase3.ready"
            phase3_proc = run_process(
                [
                    python,
                    "-m",
                    module,
                    "vehicle-receiver",
                    "--count",
                    str(MESSAGE_COUNT),
                    "--out",
                    str(phase3_out),
                    "--ready-file",
                    str(phase3_ready),
                ],
                backend_dir,
                env,
                temp / "phase3_vehicle.log",
            )
            processes.append(phase3_proc)
            phase3_ready_ok = wait_ready(phase3_ready, phase3_proc)
            phase3_pub = subprocess.run(
                [python, "-m", module, "publisher", "--interval", "0.08", "--warmup", "0.8"],
                cwd=str(backend_dir),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            phase3_proc.wait(timeout=15)
            phase3_records = read_jsonl(phase3_out)
            phase3_rows = evaluate_vehicle_records(phase3_records) if len(phase3_records) == MESSAGE_COUNT else []
            phase3_pass = phase3_ready_ok and phase3_pub.returncode == 0 and len(phase3_records) == MESSAGE_COUNT

            phase4_vehicle_out = temp / "phase4_vehicle.jsonl"
            phase4_backend_out = temp / "phase4_backend.jsonl"
            phase4_vehicle_ready = temp / "phase4_vehicle.ready"
            phase4_backend_ready = temp / "phase4_backend.ready"
            backend_proc = run_process(
                [
                    python,
                    "-m",
                    module,
                    "backend-subscriber",
                    "--count",
                    str(MESSAGE_COUNT),
                    "--out",
                    str(phase4_backend_out),
                    "--ready-file",
                    str(phase4_backend_ready),
                ],
                backend_dir,
                env,
                temp / "phase4_backend.log",
            )
            processes.append(backend_proc)
            vehicle_proc = run_process(
                [
                    python,
                    "-m",
                    module,
                    "vehicle-receiver",
                    "--count",
                    str(MESSAGE_COUNT),
                    "--publish-state",
                    "--out",
                    str(phase4_vehicle_out),
                    "--ready-file",
                    str(phase4_vehicle_ready),
                ],
                backend_dir,
                env,
                temp / "phase4_vehicle.log",
            )
            processes.append(vehicle_proc)
            phase4_ready_ok = wait_ready(phase4_backend_ready, backend_proc) and wait_ready(phase4_vehicle_ready, vehicle_proc)
            phase4_pub = subprocess.run(
                [python, "-m", module, "publisher", "--interval", "0.08", "--warmup", "0.8"],
                cwd=str(backend_dir),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            vehicle_proc.wait(timeout=15)
            backend_proc.wait(timeout=15)
            phase4_vehicle_records = read_jsonl(phase4_vehicle_out)
            phase4_backend_records = read_jsonl(phase4_backend_out)
            phase4_pass = (
                phase4_ready_ok
                and phase4_pub.returncode == 0
                and len(phase4_vehicle_records) == MESSAGE_COUNT
                and len(phase4_backend_records) == MESSAGE_COUNT
            )

            summary = {
                "environment": {
                    "python": sys.version.split()[0],
                    "frontend_xpub": "tcp://127.0.0.1:5555",
                    "backend_xsub": "tcp://127.0.0.1:5556",
                    "message_count": MESSAGE_COUNT,
                    "broker_owned_by_test": broker_owned,
                    "processes": [
                        "app.communication.broker",
                        "vehicle_comm_chain_test.py publisher",
                        "vehicle_comm_chain_test.py passive-subscriber",
                        "vehicle_comm_chain_test.py vehicle-receiver",
                        "vehicle_comm_chain_test.py backend-subscriber",
                    ],
                },
                "phase1": {
                    "passed": phase1_valid,
                    "sent": len(phase1_messages),
                    "scenarios": sorted({message["scenario"] for message in phase1_messages}),
                    "sample": phase1_messages[:2],
                },
                "phase2": {
                    "passed": phase2_pass,
                    "ready_before_publish": phase2_ready_ok,
                    "published_returncode": phase2_pub.returncode,
                    "received": len(phase2_records),
                    "sequence_ids": phase2_sequences,
                },
                "phase3": {
                    "passed": phase3_pass,
                    "ready_before_publish": phase3_ready_ok,
                    "published_returncode": phase3_pub.returncode,
                    "processed": len(phase3_records),
                    "operation_rows": phase3_rows,
                },
                "phase4": {
                    "passed": phase4_pass,
                    "ready_before_publish": phase4_ready_ok,
                    "published_returncode": phase4_pub.returncode,
                    "vehicle_outputs": len(phase4_vehicle_records),
                    "backend_received": len(phase4_backend_records),
                    "sample_train_state": phase4_backend_records[-1]["data"] if phase4_backend_records else None,
                },
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
            return 0 if all([phase1_valid, phase2_pass, phase3_pass, phase4_pass]) else 3
        finally:
            for proc in reversed(processes):
                stop_process(proc)
            if broker_proc is not None and broker_owned:
                stop_process(broker_proc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vehicle communication chain integration test")
    subparsers = parser.add_subparsers(dest="role", required=True)

    publisher_parser = subparsers.add_parser("publisher")
    publisher_parser.add_argument("--print-only", action="store_true")
    publisher_parser.add_argument("--interval", type=float, default=0.08)
    publisher_parser.add_argument("--warmup", type=float, default=0.5)

    passive_parser = subparsers.add_parser("passive-subscriber")
    passive_parser.add_argument("--count", type=int, default=MESSAGE_COUNT)
    passive_parser.add_argument("--timeout", type=float, default=10.0)
    passive_parser.add_argument("--out", required=True)
    passive_parser.add_argument("--ready-file")

    vehicle_parser = subparsers.add_parser("vehicle-receiver")
    vehicle_parser.add_argument("--count", type=int, default=MESSAGE_COUNT)
    vehicle_parser.add_argument("--timeout", type=float, default=10.0)
    vehicle_parser.add_argument("--out", required=True)
    vehicle_parser.add_argument("--ready-file")
    vehicle_parser.add_argument("--default-dt", type=float, default=0.1)
    vehicle_parser.add_argument("--max-dt", type=float, default=0.2)
    vehicle_parser.add_argument("--publish-state", action="store_true")

    backend_parser = subparsers.add_parser("backend-subscriber")
    backend_parser.add_argument("--count", type=int, default=MESSAGE_COUNT)
    backend_parser.add_argument("--timeout", type=float, default=10.0)
    backend_parser.add_argument("--out", required=True)
    backend_parser.add_argument("--ready-file")

    subparsers.add_parser("orchestrator")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.role == "publisher":
        return publisher(args)
    if args.role == "passive-subscriber":
        return passive_subscriber(args)
    if args.role == "vehicle-receiver":
        return vehicle_receiver(args)
    if args.role == "backend-subscriber":
        return backend_state_subscriber(args)
    if args.role == "orchestrator":
        return orchestrator(args)
    raise ValueError(args.role)


if __name__ == "__main__":
    raise SystemExit(main())
