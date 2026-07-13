from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")


@dataclass
class ManagedBrokerProcess:
    process: subprocess.Popen
    log_path: Path

    @property
    def pid(self) -> int | None:
        return self.process.pid

    @property
    def running(self) -> bool:
        return self.process.poll() is None


class BrokerProcessManager:
    """Own the local ZMQ broker for development/demo backend runs."""

    def __init__(self, *, enabled: bool | None = None) -> None:
        self.enabled = settings.ENABLE_ZMQ_BROKER_MANAGER if enabled is None else enabled
        self._broker: ManagedBrokerProcess | None = None
        self._lock = RLock()

    def start(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "started": False, "reason": "broker_manager_disabled"}

        with self._lock:
            if self._broker and self._broker.running:
                return {
                    "enabled": True,
                    "started": False,
                    "already_running": True,
                    "pid": self._broker.pid,
                    "log_path": str(self._broker.log_path),
                }

            backend_root = Path(__file__).resolve().parents[2]
            log_dir = backend_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "zmq_broker.log"
            command = [sys.executable, "-m", "app.communication.broker"]

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

            time.sleep(0.3)
            self._broker = ManagedBrokerProcess(process=process, log_path=log_path)
            if not self._broker.running:
                logger.warning("Local ZMQ broker exited immediately; another broker may already own the ports")
                return {
                    "enabled": True,
                    "started": False,
                    "running": False,
                    "pid": process.pid,
                    "log_path": str(log_path),
                    "reason": "broker_exited_immediately",
                }

            logger.info("Started local ZMQ broker process: pid=%s", process.pid)
            return {
                "enabled": True,
                "started": True,
                "running": True,
                "pid": process.pid,
                "log_path": str(log_path),
            }

    def stop(self, *, timeout: float = 3.0) -> dict[str, Any]:
        with self._lock:
            broker = self._broker
            self._broker = None

        if broker is None:
            return {"stopped": False, "reason": "broker_not_managed"}
        if not broker.running:
            return {"stopped": False, "pid": broker.pid, "reason": "broker_already_exited"}

        broker.process.terminate()
        try:
            broker.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            broker.process.kill()
            broker.process.wait(timeout=timeout)

        logger.info("Stopped local ZMQ broker process: pid=%s", broker.pid)
        return {"stopped": True, "pid": broker.pid}

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._broker is None:
                return {"process_managed": False, "process_running": False}
            return {
                "process_managed": True,
                "process_running": self._broker.running,
                "process_pid": self._broker.pid,
                "process_log_path": str(self._broker.log_path),
            }


broker_process_manager = BrokerProcessManager()
