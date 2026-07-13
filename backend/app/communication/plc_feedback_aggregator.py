"""Single owner for assembling and sending complete PLC feedback frames."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any


PLC_FEEDBACK_TOPICS = ("train_state", "ato_state", "door_state", "comm_state")


class PlcFeedbackAggregator:
    """Cache module states and call the PLC sender once with a full snapshot.

    This class belongs to the communication layer.  Vehicle and ATO modules
    publish state only and never receive a reference to the PLC sender.
    """

    def __init__(
        self,
        send_to_plc: Callable[..., Any],
        *,
        interval_sec: float = 0.1,
        comm_timeout_sec: float = 0.5,
    ) -> None:
        if interval_sec <= 0.0:
            raise ValueError("interval_sec must be positive")
        self._send_to_plc = send_to_plc
        self.interval_sec = float(interval_sec)
        self.comm_timeout_sec = float(comm_timeout_sec)
        self._vehicle_states: dict[str, dict[str, Any]] = {}
        self._comm_state: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def attach(self, bus) -> None:
        """Subscribe to state topics on the shared MessageBus."""
        for topic in PLC_FEEDBACK_TOPICS:
            bus.subscribe(topic, self.on_message)

    def on_message(self, topic: str, data: dict) -> None:
        """MessageBus callback; cache state without sending a partial frame."""
        if topic == "comm_state":
            with self._lock:
                self._comm_state.update(data)
            return
        vehicle_id = data.get("vehicle_id")
        if not vehicle_id:
            return
        with self._lock:
            self._vehicle_states.setdefault(str(vehicle_id), {}).update(data)

    def build_snapshot(self, vehicle_id: str, *, now: float | None = None) -> dict:
        """Build one complete PLC call from the latest cached module states."""
        current_time = time.time() if now is None else float(now)
        with self._lock:
            state = dict(self._vehicle_states.get(vehicle_id, {}))
            comm = dict(self._comm_state)

        last_message_at = comm.get("last_message_at")
        comm_stale = (
            last_message_at is None
            or current_time - float(last_message_at) > self.comm_timeout_sec
        )
        network_fault = (
            not bool(comm.get("driver_console_connected", False))
            or not bool(comm.get("zmq_connected", False))
            or comm_stale
        )
        door_closed = bool(
            state.get("door_closed_light", state.get("doors_all_closed", True))
        )
        door_open = bool(state.get("door_open_light", not door_closed))

        # ── ATO 具备条件判断 ──────────────────────────────────────────
        # 上位机主动判断是否满足 ATO 前提条件，满足时发 ato_capable=True
        # 给司机台，驱动按钮闪烁提示司机可以按下启动。
        # 条件：门全关 + 方向手柄不在0位 + 无紧急制动
        # 注意：不使用司机台下行帧里的 ato_capable 原样回传，
        #       避免自循环（司机台说具备 → 上位机回传 → 司机台显示具备）。
        direction_code = state.get("direction_code", 0)
        emergency_brake = bool(state.get("emergency_brake", False))
        ato_capable = (
            door_closed
            and int(direction_code) != 0
            and not emergency_brake
        )

        return {
            "vehicle_speed_kmh": float(
                state.get("vehicle_speed_kmh", state.get("speed_kmh", state.get("speed", 0.0)))
            ),
            "high_voltage_on": bool(
                state.get("high_voltage_on", state.get("high_voltage_light", False))
            ),
            "brake_bad_light": bool(state.get("brake_bad_light", False)),
            "door_open_light": door_open,
            "door_closed_light": door_closed,
            "network_fault": network_fault,
            "ato_capable": ato_capable,
            "wash_mode_status": bool(state.get("wash_mode_status", False)),
            "ato_active": bool(state.get("ato_active", False)),
            "auto_reverse_cap": bool(state.get("auto_reverse_cap", False)),
            "auto_reverse_active": bool(state.get("auto_reverse_active", False)),
        }

    def flush_once(self, *, now: float | None = None) -> int:
        """Send one full snapshot per known vehicle and return the send count."""
        with self._lock:
            vehicle_ids = tuple(sorted(self._vehicle_states))
        for vehicle_id in vehicle_ids:
            self._send_to_plc(**self.build_snapshot(vehicle_id, now=now))
        return len(vehicle_ids)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="plc-feedback-aggregator",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval_sec * 2.0))
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval_sec):
            self.flush_once()
