from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MAX_DEMO_TRAINS = 5


def validate_launch_range(launch_from_index: int, max_index: int) -> tuple[int, int]:
    launch_from = int(launch_from_index)
    max_train_index = int(max_index)
    if launch_from <= 1:
        raise ValueError("--launch-from-index must be >= 2; TRAIN-001 is hardware-controlled")
    if max_train_index > MAX_DEMO_TRAINS:
        raise ValueError(f"--max-index must be <= {MAX_DEMO_TRAINS}")
    if max_train_index < launch_from:
        raise ValueError("--max-index must be >= --launch-from-index")
    return launch_from, max_train_index


def vehicle_id_for(prefix: str, index: int) -> str:
    return f"{prefix}-{int(index):03d}"


def planned_vehicle_ids(prefix: str, launch_from_index: int, max_index: int) -> list[str]:
    launch_from, max_train_index = validate_launch_range(launch_from_index, max_index)
    return [
        vehicle_id_for(prefix, index)
        for index in range(launch_from, max_train_index + 1)
    ]


def next_launch_index(
    launched_count: int,
    launch_from_index: int,
    max_index: int,
) -> int | None:
    launch_from, max_train_index = validate_launch_range(launch_from_index, max_index)
    launched = max(0, int(launched_count))
    candidate = launch_from + launched
    return candidate if candidate <= max_train_index else None


def monitor_vehicle_for_launch(
    *,
    anchor_vehicle_id: str,
    vehicle_prefix: str,
    launch_from_index: int,
    launched_count: int,
) -> str:
    if int(launched_count) <= 0:
        return anchor_vehicle_id
    return vehicle_id_for(vehicle_prefix, int(launch_from_index) + int(launched_count) - 1)


def next_launch_index_if_ready(
    snapshot: dict[str, Any],
    *,
    anchor_vehicle_id: str,
    vehicle_prefix: str,
    launch_from_index: int,
    max_index: int,
    launched_count: int,
    clear_distance_m: float,
) -> int | None:
    launch_index = next_launch_index(launched_count, launch_from_index, max_index)
    if launch_index is None:
        return None
    monitor_vehicle = monitor_vehicle_for_launch(
        anchor_vehicle_id=anchor_vehicle_id,
        vehicle_prefix=vehicle_prefix,
        launch_from_index=launch_from_index,
        launched_count=launched_count,
    )
    return (
        launch_index
        if has_cleared_origin(snapshot, monitor_vehicle, clear_distance_m)
        else None
    )


def build_vehicle_command(
    *,
    python_executable: str,
    vehicle_id: str,
    train_index: int,
    initial_position: float,
    dt: float,
) -> list[str]:
    return [
        python_executable,
        "-m",
        "app.vehicle_sim.main_integrated",
        "--vehicle-id",
        vehicle_id,
        "--train-index",
        str(int(train_index)),
        "--initial-position",
        str(float(initial_position)),
        "--dt",
        str(float(dt)),
    ]


def find_train(snapshot: dict[str, Any], vehicle_id: str) -> dict[str, Any] | None:
    trains = snapshot.get("trains")
    if not isinstance(trains, list):
        return None
    for train in trains:
        if isinstance(train, dict) and train.get("vehicle_id") == vehicle_id:
            return train
    return None


def train_position_m(snapshot: dict[str, Any], vehicle_id: str) -> float | None:
    train = find_train(snapshot, vehicle_id)
    if train is None:
        return None
    for key in ("position_m", "position"):
        value = train.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def has_cleared_origin(
    snapshot: dict[str, Any],
    vehicle_id: str,
    clear_distance_m: float,
) -> bool:
    position = train_position_m(snapshot, vehicle_id)
    return position is not None and position >= float(clear_distance_m)


def fetch_dashboard_snapshot(url: str, timeout_sec: float = 2.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as response:
            payload = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError) as exc:
        print(f"[launcher] dashboard unavailable: {exc}", flush=True)
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        print(f"[launcher] dashboard returned invalid JSON: {exc}", flush=True)
        return None
    return data if isinstance(data, dict) else None


class AutoDepartureLauncher:
    def __init__(
        self,
        *,
        anchor_vehicle_id: str,
        launch_from_index: int,
        max_index: int,
        initial_position: float,
        clear_distance: float,
        dt: float,
        poll_interval: float,
        dashboard_url: str,
        vehicle_prefix: str,
        python_executable: str | None = None,
        cwd: Path | None = None,
    ):
        launch_from, max_train_index = validate_launch_range(launch_from_index, max_index)
        self.anchor_vehicle_id = anchor_vehicle_id
        self.launch_from_index = launch_from
        self.max_index = max_train_index
        self.initial_position = float(initial_position)
        self.clear_distance = float(clear_distance)
        self.dt = float(dt)
        self.poll_interval = float(poll_interval)
        self.dashboard_url = dashboard_url
        self.vehicle_prefix = vehicle_prefix
        self.python_executable = python_executable or sys.executable
        self.cwd = cwd or BACKEND_ROOT
        self.processes: dict[str, subprocess.Popen] = {}

    def vehicle_id(self, train_index: int) -> str:
        return vehicle_id_for(self.vehicle_prefix, train_index)

    def start_vehicle(self, train_index: int) -> None:
        vehicle_id = self.vehicle_id(train_index)
        command = build_vehicle_command(
            python_executable=self.python_executable,
            vehicle_id=vehicle_id,
            train_index=train_index,
            initial_position=self.initial_position,
            dt=self.dt,
        )
        print(f"[launcher] starting {vehicle_id}: {' '.join(command)}", flush=True)
        self.processes[vehicle_id] = subprocess.Popen(command, cwd=str(self.cwd))

    def run(self) -> None:
        print(
            f"[launcher] monitoring anchor {self.anchor_vehicle_id}; "
            f"will launch {planned_vehicle_ids(self.vehicle_prefix, self.launch_from_index, self.max_index)}",
            flush=True,
        )
        launched = 0
        try:
            while (
                next_index := next_launch_index(
                    launched,
                    self.launch_from_index,
                    self.max_index,
                )
            ) is not None:
                previous_vehicle = monitor_vehicle_for_launch(
                    anchor_vehicle_id=self.anchor_vehicle_id,
                    vehicle_prefix=self.vehicle_prefix,
                    launch_from_index=self.launch_from_index,
                    launched_count=launched,
                )
                snapshot = fetch_dashboard_snapshot(self.dashboard_url)
                position = None if snapshot is None else train_position_m(snapshot, previous_vehicle)
                if position is None:
                    print(
                        f"[launcher] waiting for {previous_vehicle} to appear in dashboard...",
                        flush=True,
                    )
                elif position >= self.clear_distance:
                    print(
                        f"[launcher] {previous_vehicle} cleared origin at {position:.1f}m; "
                        f"starting {self.vehicle_id(next_index)}",
                        flush=True,
                    )
                    self.start_vehicle(next_index)
                    launched += 1
                else:
                    print(
                        f"[launcher] waiting for {previous_vehicle} to clear origin... "
                        f"position={position:.1f}m threshold={self.clear_distance:.1f}m",
                        flush=True,
                    )
                time.sleep(self.poll_interval)

            print("[launcher] all requested virtual vehicles started.", flush=True)
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("[launcher] Ctrl+C received.", flush=True)
        finally:
            self.print_processes()

    def print_processes(self) -> None:
        print("[launcher] started vehicle processes:", flush=True)
        for vehicle_id, process in self.processes.items():
            status = process.poll()
            status_text = "running" if status is None else f"exited={status}"
            print(f"  {vehicle_id}: pid={process.pid} {status_text}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start virtual train processes after an anchor train clears origin.")
    parser.add_argument("--anchor-vehicle-id", default="TRAIN-001")
    parser.add_argument("--launch-from-index", type=int, default=2)
    parser.add_argument("--max-index", type=int, default=3)
    parser.add_argument("--initial-position", type=float, default=0.0)
    parser.add_argument("--clear-distance", type=float, default=200.0)
    parser.add_argument("--dt", type=float, default=0.1)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument(
        "--dashboard-url",
        default="http://127.0.0.1:8000/api/v1/dashboard/snapshot",
    )
    parser.add_argument("--vehicle-prefix", default="TRAIN")
    args = parser.parse_args()
    try:
        validate_launch_range(args.launch_from_index, args.max_index)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main() -> None:
    args = parse_args()
    launcher = AutoDepartureLauncher(
        anchor_vehicle_id=args.anchor_vehicle_id,
        launch_from_index=args.launch_from_index,
        max_index=args.max_index,
        initial_position=args.initial_position,
        clear_distance=args.clear_distance,
        dt=args.dt,
        poll_interval=args.poll_interval,
        dashboard_url=args.dashboard_url,
        vehicle_prefix=args.vehicle_prefix,
    )
    launcher.run()


if __name__ == "__main__":
    main()
