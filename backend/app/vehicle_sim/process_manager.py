from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


@dataclass
class ManagedVehicleProcess:
    vehicle_id: str
    train_index: int
    initial_position: float
    process: subprocess.Popen
    log_path: Path

    @property
    def pid(self) -> int | None:
        return self.process.pid

    @property
    def running(self) -> bool:
        return self.process.poll() is None


class VehicleProcessManager:
    """Start/stop local one-process-per-train vehicle simulations.

    This manager is deliberately small and local-only. It is useful for MVP
    demos where FastAPI owns child Python processes; a production deployment
    should use a process supervisor/container orchestrator instead.
    """

    def __init__(self, *, enabled: bool | None = None) -> None:
        self.enabled = settings.ENABLE_VEHICLE_PROCESS_MANAGER if enabled is None else enabled
        self._processes: dict[str, ManagedVehicleProcess] = {}
        self._lock = RLock()

    def start_train(
        self,
        *,
        vehicle_id: str,
        train_index: int,
        initial_position: float = 0.0,
        line_layout: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "started": False, "reason": "vehicle_process_manager_disabled"}

        with self._lock:
            existing = self._processes.get(vehicle_id)
            if existing and existing.running:
                return {
                    "enabled": True,
                    "started": False,
                    "already_running": True,
                    "vehicle_id": vehicle_id,
                    "pid": existing.pid,
                    "log_path": str(existing.log_path),
                }
            if existing:
                self._processes.pop(vehicle_id, None)

            backend_root = Path(__file__).resolve().parents[2]
            project_root = backend_root.parent
            layout_path = Path(line_layout) if line_layout else project_root / "frontend" / "public" / "data" / "line-layout.json"
            log_dir = backend_root / "logs" / "vehicle_processes"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"{vehicle_id}.log"

            command = [
                sys.executable,
                "-m",
                "app.vehicle_sim.main_integrated",
                "--vehicle-id",
                vehicle_id,
                "--train-index",
                str(int(train_index)),
                "--initial-position",
                str(float(initial_position)),
                "--dt",
                str(float(settings.VEHICLE_PROCESS_DT)),
                "--line-layout",
                str(layout_path),
            ]

            env = os.environ.copy()
            env.setdefault("PYTHONUNBUFFERED", "1")

            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            log_file = log_path.open("a", encoding="utf-8")
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(backend_root),
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                    creationflags=creationflags,
                )
            finally:
                log_file.close()

            managed = ManagedVehicleProcess(
                vehicle_id=vehicle_id,
                train_index=int(train_index),
                initial_position=float(initial_position),
                process=process,
                log_path=log_path,
            )
            self._processes[vehicle_id] = managed
            logger.info("Started vehicle process: vehicle_id=%s pid=%s", vehicle_id, process.pid)
            return {
                "enabled": True,
                "started": True,
                "vehicle_id": vehicle_id,
                "train_index": int(train_index),
                "pid": process.pid,
                "log_path": str(log_path),
                "command": command,
            }

    def stop_train(self, vehicle_id: str, *, timeout: float = 3.0) -> dict[str, Any]:
        with self._lock:
            managed = self._processes.pop(vehicle_id, None)
            if managed is None:
                return {"stopped": False, "vehicle_id": vehicle_id, "reason": "process_not_managed"}

            if not managed.running:
                return {
                    "stopped": False,
                    "vehicle_id": vehicle_id,
                    "pid": managed.pid,
                    "reason": "process_already_exited",
                }

            managed.process.terminate()
            try:
                managed.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                managed.process.kill()
                managed.process.wait(timeout=timeout)

            logger.info("Stopped vehicle process: vehicle_id=%s pid=%s", vehicle_id, managed.pid)
            return {"stopped": True, "vehicle_id": vehicle_id, "pid": managed.pid}

    def stop_all(self) -> dict[str, Any]:
        with self._lock:
            vehicle_ids = list(self._processes)
        results = [self.stop_train(vehicle_id) for vehicle_id in vehicle_ids]
        return {"stopped": sum(1 for item in results if item.get("stopped")), "results": results}

    def status(self, vehicle_id: str) -> dict[str, Any]:
        with self._lock:
            managed = self._processes.get(vehicle_id)
            if managed is None:
                return {"process_managed": False, "process_running": False}
            return {
                "process_managed": True,
                "process_running": managed.running,
                "process_pid": managed.pid,
                "process_log_path": str(managed.log_path),
            }

    def enrich_trains(self, trains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**train, **self.status(str(train.get("vehicle_id")))} for train in trains]


vehicle_process_manager = VehicleProcessManager()
