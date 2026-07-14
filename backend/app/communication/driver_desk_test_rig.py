from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Any

from app.communication.driver_desk_source import (
    DIR_FORWARD,
    DIR_NEUTRAL,
    DIR_REVERSE,
    FRAME_FMT,
    FRAME_LEN,
    FRAME_MAGIC,
    MAIN_HANDLE_BRAKE,
    MAIN_HANDLE_COAST,
    MAIN_HANDLE_FAST,
    MAIN_HANDLE_TRAC,
    DriverDeskSource,
)
from app.communication.plc_feedback_aggregator import PlcFeedbackAggregator
from app.core.config import settings

UPLINK_FRAME_FMT = "<IHHHHHHHHHHBBH"
UPLINK_FRAME_LEN = struct.calcsize(UPLINK_FRAME_FMT)
UPLINK_FRAME_MAGIC = 0xAA55AA55


class PublishOnlyBus:
    """Minimal bus for TCP protocol testing when local pyzmq is unavailable."""

    def __init__(self, pub_address: str | None = None) -> None:
        self.pub_address = pub_address or settings.ZMQ_BROKER_BACKEND
        self._lock = threading.Lock()
        self.published_count = 0
        self.last_topic: str | None = None
        self.last_data: dict | None = None

    def start(self) -> None:
        return

    def publish(self, topic: str, data: dict) -> None:
        with self._lock:
            self.published_count += 1
            self.last_topic = topic
            self.last_data = dict(data)
        try:
            if topic == "driver_input":
                from app.api.v1.endpoints.vehicle import vehicle_message_router
                from app.data_flow.state_store import state_store

                vehicle_id = str(data.get("vehicle_id") or "TRAIN-001")
                routed = {"type": "driver_input", **data}
                routed.setdefault("source", "driver_tcp")
                vehicle_message_router.handle(routed)
                state_store.update_driver_input(vehicle_id, routed)
            elif topic == "comm_state":
                from app.api.v1.endpoints.vehicle import vehicle_message_router
                from app.data_flow.state_store import state_store

                routed = {"type": "comm_state", **data}
                vehicle_message_router.handle(routed)
                state_store.update_comm(routed)
        except Exception:
            # Keep the TCP protocol rig alive even if the optional in-process bridge fails.
            return

    def subscribe(self, _topic: str, _handler: Any) -> None:
        return

    def unsubscribe(self, _topic: str, _handler: Any = None) -> None:
        return

    def stop(self) -> None:
        return


class DriverDeskBridgeService:
    OBSERVED_TOPICS = ("driver_input", "comm_state", "train_state", "ato_state", "door_state")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bus: MessageBus | None = None
        self._source: DriverDeskSource | None = None
        self._aggregator: PlcFeedbackAggregator | None = None
        self._running = False
        self._bus_diagnostics = self._empty_bus_diagnostics()

    def start(self, *, vehicle_id: str, plc_host: str, plc_port: int) -> dict[str, Any]:
        self.stop()

        bus = PublishOnlyBus()
        bus.start()
        source = DriverDeskSource(
            vehicle_id=vehicle_id,
            plc_host=plc_host,
            plc_port=plc_port,
            bus=bus,
        )

        def safe_send_to_plc(**kwargs: Any) -> None:
            if source.status().get("connected"):
                source.send_to_plc(**kwargs)

        aggregator = PlcFeedbackAggregator(safe_send_to_plc)
        with self._lock:
            self._bus_diagnostics = self._empty_bus_diagnostics()

        source.start()
        aggregator.start()

        with self._lock:
            self._bus = bus
            self._source = source
            self._aggregator = aggregator
            self._running = True

        return self.snapshot()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            bus = self._bus
            source = self._source
            aggregator = self._aggregator
            self._bus = None
            self._source = None
            self._aggregator = None
            self._running = False

        if aggregator is not None:
            aggregator.stop()
        if source is not None:
            source.stop()
        if bus is not None:
            bus.stop()
        with self._lock:
            self._bus_diagnostics = self._empty_bus_diagnostics()

        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            source = self._source
            aggregator = self._aggregator
            running = self._running
            bus_diagnostics = dict(self._bus_diagnostics)
        source_status = source.status() if source is not None else None
        aggregator_status = {
            "running": aggregator is not None,
            "interval_sec": aggregator.interval_sec if aggregator is not None else None,
        } if aggregator is not None else None
        warnings = []
        if settings.DATA_SOURCE != "zmq":
            warnings.append("dashboard_listener_inactive_until_data_source_is_zmq")
        if source_status and source_status.get("recv_count", 0) > 0 and bus_diagnostics["driver_input_count"] == 0:
            warnings.append("tcp_frames_received_but_driver_input_not_observed_on_bus")
        return {
            "running": running,
            "vehicle_id": source_status.get("vehicle_id") if source_status else None,
            "plc_host": source_status.get("plc", "").split(":")[0] if source_status else None,
            "plc_port": int(source_status.get("plc", "0:0").split(":")[-1]) if source_status else None,
            "source_status": source_status,
            "aggregator_running": aggregator is not None,
            "aggregator_status": aggregator_status,
            "bus_diagnostics": bus_diagnostics,
            "dashboard_path_ready": settings.DATA_SOURCE == "zmq",
            "warnings": warnings,
        }

    def _on_driver_desk_binding(self, _topic: str, data: dict) -> None:
        vehicle_id = data.get("vehicle_id")
        if not vehicle_id:
            return
        with self._lock:
            aggregator = self._aggregator
        if aggregator is not None:
            aggregator.set_active_vehicle_id(str(vehicle_id))

    def _on_driver_input(self, topic: str, data: dict) -> None:
        now = time.time()
        with self._lock:
            self._bus_diagnostics["last_topic"] = topic
            self._bus_diagnostics["last_seen_at"] = now
            self._bus_diagnostics["driver_input_count"] += 1
            self._bus_diagnostics["last_driver_input_at"] = now
            self._bus_diagnostics["last_driver_input_vehicle_id"] = data.get("vehicle_id")
            self._bus_diagnostics["last_driver_input_source"] = data.get("source")

    def _on_comm_state(self, topic: str, data: dict) -> None:
        now = time.time()
        with self._lock:
            self._bus_diagnostics["last_topic"] = topic
            self._bus_diagnostics["last_seen_at"] = now
            self._bus_diagnostics["comm_state_count"] += 1
            self._bus_diagnostics["last_comm_state_at"] = now
            self._bus_diagnostics["last_comm_state_source"] = data.get("source")
            self._bus_diagnostics["driver_console_connected"] = bool(
                data.get("driver_console_connected", False)
            )
            self._bus_diagnostics["zmq_connected"] = bool(data.get("zmq_connected", False))

    def _on_feedback_state(self, topic: str, data: dict) -> None:
        now = time.time()
        counter_key = f"{topic}_count"
        timestamp_key = f"last_{topic}_at"
        with self._lock:
            self._bus_diagnostics["last_topic"] = topic
            self._bus_diagnostics["last_seen_at"] = now
            self._bus_diagnostics[counter_key] += 1
            self._bus_diagnostics[timestamp_key] = now
            if topic == "train_state":
                self._bus_diagnostics["last_feedback_vehicle_id"] = data.get("vehicle_id")

    @classmethod
    def _empty_bus_diagnostics(cls) -> dict[str, Any]:
        diagnostics: dict[str, Any] = {
            "last_topic": None,
            "last_seen_at": None,
            "driver_input_count": 0,
            "comm_state_count": 0,
            "train_state_count": 0,
            "ato_state_count": 0,
            "door_state_count": 0,
            "last_driver_input_at": None,
            "last_driver_input_vehicle_id": None,
            "last_driver_input_source": None,
            "last_comm_state_at": None,
            "last_comm_state_source": None,
            "driver_console_connected": False,
            "zmq_connected": False,
            "last_train_state_at": None,
            "last_ato_state_at": None,
            "last_door_state_at": None,
            "last_feedback_vehicle_id": None,
        }
        for topic in cls.OBSERVED_TOPICS:
            diagnostics.setdefault(f"{topic}_count", 0)
            diagnostics.setdefault(f"last_{topic}_at", None)
        return diagnostics


class DriverDeskProtocolSimulator:
    PULSE_FIELDS = {
        "forced_release",
        "forced_pump",
        "parking_apply",
        "parking_release",
        "horn",
        "open_left_door",
        "open_right_door",
        "close_left_door",
        "close_right_door",
        "mode_up_confirm",
        "mode_dn_confirm",
        "confirm_flag",
        "auto_rev_flag",
        "trac_aux_reset",
        "ato_start_btn",
        "vigilance",
    }

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 18001,
        interval_sec: float = 0.1,
        pulse_width_ms: int = 250,
        vehicle_id: str = "TRAIN-001",
    ) -> None:
        self.host = host
        self.port = int(port)
        self.interval_sec = max(0.02, float(interval_sec))
        self.pulse_width_ms = max(50, int(pulse_width_ms))
        self.vehicle_id = vehicle_id

        self._lock = threading.RLock()
        self._server_socket: socket.socket | None = None
        self._client_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._client_addr: str | None = None
        self._last_error: str | None = None
        self._frames_sent = 0
        self._frames_received = 0
        self._last_downlink_sent_at: float | None = None
        self._last_uplink_received_at: float | None = None
        self._pulse_deadlines: dict[str, float] = {}
        self._input_state = self._default_input_state()
        self._feedback_state = self._default_feedback_state()

    def start(self) -> dict[str, Any]:
        self.stop()
        with self._lock:
            self._running = True
            self._last_error = None
            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="driver-desk-protocol-simulator",
            )
            self._thread.start()
        return self.snapshot()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._running = False
            server_socket = self._server_socket
            client_socket = self._client_socket
            thread = self._thread
            self._server_socket = None
            self._client_socket = None
            self._thread = None
            self._client_addr = None
        for sock in (client_socket, server_socket):
            if sock is None:
                continue
            try:
                sock.close()
            except OSError:
                pass
        if thread is not None:
            thread.join(timeout=1.5)
        return self.snapshot()

    def update_input(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for key, value in updates.items():
                if key not in self._input_state:
                    raise ValueError(f"unsupported_input_field:{key}")
                self._input_state[key] = self._sanitize_input_value(key, value)
        return self.snapshot()

    def pulse(self, field_name: str, duration_ms: int | None = None) -> dict[str, Any]:
        if field_name not in self.PULSE_FIELDS:
            raise ValueError(f"unsupported_pulse_field:{field_name}")
        pulse_ms = self.pulse_width_ms if duration_ms is None else max(50, int(duration_ms))
        with self._lock:
            self._pulse_deadlines[field_name] = time.time() + pulse_ms / 1000.0
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "listening": self._server_socket is not None,
                "client_connected": self._client_socket is not None,
                "client_addr": self._client_addr,
                "host": self.host,
                "port": self.port,
                "vehicle_id": self.vehicle_id,
                "interval_sec": self.interval_sec,
                "pulse_width_ms": self.pulse_width_ms,
                "frames_sent": self._frames_sent,
                "frames_received": self._frames_received,
                "last_downlink_sent_at": self._last_downlink_sent_at,
                "last_uplink_received_at": self._last_uplink_received_at,
                "last_error": self._last_error,
                "input_state": dict(self._input_state),
                "feedback_state": dict(self._feedback_state),
                "active_pulses": {
                    key: deadline
                    for key, deadline in self._pulse_deadlines.items()
                    if deadline > time.time()
                },
            }

    def _run(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(1)
        server.settimeout(0.2)
        with self._lock:
            self._server_socket = server

        try:
            while self._is_running():
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue
                conn.settimeout(0.02)
                with self._lock:
                    self._client_socket = conn
                    self._client_addr = f"{addr[0]}:{addr[1]}"
                    self._last_error = None
                try:
                    self._handle_client(conn)
                finally:
                    with self._lock:
                        if self._client_socket is conn:
                            self._client_socket = None
                            self._client_addr = None
                    try:
                        conn.close()
                    except OSError:
                        pass
        except OSError as exc:
            if self._is_running():
                with self._lock:
                    self._last_error = str(exc)
        finally:
            with self._lock:
                self._server_socket = None
            try:
                server.close()
            except OSError:
                pass

    def _handle_client(self, conn: socket.socket) -> None:
        recv_buffer = b""
        next_send_at = time.time()
        while self._is_running():
            now = time.time()
            if now >= next_send_at:
                frame = self._build_downlink_frame()
                conn.sendall(frame)
                with self._lock:
                    self._frames_sent += 1
                    self._last_downlink_sent_at = now
                next_send_at = now + self.interval_sec
            try:
                chunk = conn.recv(4096)
                if chunk:
                    recv_buffer += chunk
                    while len(recv_buffer) >= UPLINK_FRAME_LEN:
                        frame = recv_buffer[:UPLINK_FRAME_LEN]
                        recv_buffer = recv_buffer[UPLINK_FRAME_LEN:]
                        self._parse_uplink_frame(frame)
                else:
                    break
            except socket.timeout:
                pass
            except (ConnectionResetError, BrokenPipeError, OSError) as exc:
                with self._lock:
                    self._last_error = str(exc)
                break
            time.sleep(0.005)

    def _build_downlink_frame(self) -> bytes:
        with self._lock:
            state = dict(self._input_state)
            feedback = dict(self._feedback_state)
        now = time.localtime()
        speed_echo = int(round(float(feedback.get("vehicle_speed_kmh", 0.0)))) & 0xFFFF
        byte24 = 0
        if self._active_flag(state, "high_voltage_light"):
            byte24 |= 1 << 1
        if self._active_flag(state, "brake_bad_light"):
            byte24 |= 1 << 2
        if self._active_flag(state, "door_closed_light"):
            byte24 |= 1 << 5
        if self._active_flag(state, "network_fault_light"):
            byte24 |= 1 << 6
        if self._active_flag(state, "auto_reverse_cap"):
            byte24 |= 1 << 7

        byte25 = 0
        if self._active_flag(state, "ato_capable"):
            byte25 |= 1 << 0
        if self._active_flag(state, "wash_mode_status"):
            byte25 |= 1 << 1
        if self._active_flag(state, "ato_active"):
            byte25 |= 1 << 2
        if self._active_flag(state, "auto_reverse_active"):
            byte25 |= 1 << 3

        byte28 = 0
        for bit, field_name in enumerate(
            [
                "emergency_button",
                "bus_ctrl_btn",
                "forced_release",
                "forced_pump",
                "emergency_cmd",
                "parking_apply",
                "parking_release",
                "horn",
            ]
        ):
            if self._active_flag(state, field_name):
                byte28 |= 1 << bit

        byte29 = 0
        for bit, field_name in enumerate(
            [
                "open_left_door",
                "open_right_door",
                "close_left_door",
                "close_right_door",
            ]
        ):
            if self._active_flag(state, field_name):
                byte29 |= 1 << bit

        byte34 = 0
        for bit, field_name in enumerate(
            [
                "high_accel_btn",
                "cab_light_switch",
                "mode_up_confirm",
                "mode_dn_confirm",
                "confirm_flag",
                "auto_rev_flag",
                "trac_aux_reset",
                "ato_start_btn",
            ]
        ):
            if self._active_flag(state, field_name):
                byte34 |= 1 << bit

        byte35 = 0
        for bit, field_name in enumerate(
            [
                "wash_mode_switch",
                "key_switch",
                "vigilance",
                "vigilance_allow",
            ]
        ):
            if self._active_flag(state, field_name):
                byte35 |= 1 << bit

        return struct.pack(
            FRAME_FMT,
            FRAME_MAGIC,
            FRAME_LEN,
            22,
            now.tm_year,
            now.tm_mon,
            now.tm_mday,
            now.tm_hour,
            now.tm_min,
            now.tm_sec,
            0,
            0,
            byte24,
            byte25,
            speed_echo,
            byte28,
            byte29,
            self._light_switch_code(state.get("light_switch")),
            self._door_mode_code(state.get("door_mode")),
            byte34,
            byte35,
            self._direction_code(state.get("direction")),
            self._main_handle_code(state.get("main_handle_raw")),
            self._percent_value(state.get("traction_percent")),
            self._percent_value(state.get("brake_percent")),
            0,
        )

    def _parse_uplink_frame(self, frame: bytes) -> None:
        unpacked = struct.unpack(UPLINK_FRAME_FMT, frame)
        identify = unpacked[0]
        if identify != UPLINK_FRAME_MAGIC:
            raise ValueError(f"unexpected_uplink_magic:{identify}")

        byte24 = unpacked[11]
        byte25 = unpacked[12]
        speed_word = unpacked[13]
        with self._lock:
            self._frames_received += 1
            self._last_uplink_received_at = time.time()
            self._feedback_state = {
                "vehicle_speed_kmh": float(speed_word),
                "high_voltage_on": bool((byte24 >> 1) & 1),
                "brake_bad_light": bool((byte24 >> 2) & 1),
                "door_open_light": bool((byte24 >> 4) & 1),
                "door_closed_light": bool((byte24 >> 5) & 1),
                "network_fault": bool((byte24 >> 6) & 1),
                "auto_reverse_cap": bool((byte24 >> 7) & 1),
                "ato_capable": bool((byte25 >> 0) & 1),
                "wash_mode_status": bool((byte25 >> 1) & 1),
                "ato_active": bool((byte25 >> 2) & 1),
                "auto_reverse_active": bool((byte25 >> 3) & 1),
            }

    def _default_input_state(self) -> dict[str, Any]:
        return {
            "direction": "forward",
            "main_handle_raw": 0,
            "traction_percent": 0,
            "brake_percent": 0,
            "emergency_button": False,
            "bus_ctrl_btn": False,
            "forced_release": False,
            "forced_pump": False,
            "emergency_cmd": False,
            "parking_apply": False,
            "parking_release": True,
            "horn": False,
            "open_left_door": False,
            "open_right_door": False,
            "close_left_door": False,
            "close_right_door": False,
            "light_switch": "off",
            "door_mode": "manual",
            "high_accel_btn": False,
            "cab_light_switch": False,
            "mode_up_confirm": False,
            "mode_dn_confirm": False,
            "confirm_flag": False,
            "auto_rev_flag": False,
            "trac_aux_reset": False,
            "ato_start_btn": False,
            "wash_mode_switch": False,
            "key_switch": True,
            "vigilance": False,
            "vigilance_allow": False,
            "high_voltage_light": False,
            "brake_bad_light": False,
            "door_closed_light": True,
            "network_fault_light": False,
            "auto_reverse_cap": False,
            "ato_capable": True,
            "wash_mode_status": False,
            "ato_active": False,
            "auto_reverse_active": False,
        }

    @staticmethod
    def _default_feedback_state() -> dict[str, Any]:
        return {
            "vehicle_speed_kmh": 0.0,
            "high_voltage_on": False,
            "brake_bad_light": False,
            "door_open_light": False,
            "door_closed_light": False,
            "network_fault": False,
            "auto_reverse_cap": False,
            "ato_capable": False,
            "wash_mode_status": False,
            "ato_active": False,
            "auto_reverse_active": False,
        }

    def _sanitize_input_value(self, key: str, value: Any) -> Any:
        if key in {"traction_percent", "brake_percent"}:
            return self._percent_value(value)
        if key == "direction":
            normalized = str(value).strip().lower()
            if normalized not in {"neutral", "forward", "backward", "reverse"}:
                raise ValueError("invalid_direction")
            return "backward" if normalized == "reverse" else normalized
        if key == "main_handle_raw":
            code = self._main_handle_code(value)
            return {
                MAIN_HANDLE_COAST: 0,
                MAIN_HANDLE_TRAC: 1,
                MAIN_HANDLE_BRAKE: 2,
                MAIN_HANDLE_FAST: 4,
            }[code]
        if key == "door_mode":
            normalized = str(value).strip().lower()
            if normalized not in {"semi_auto", "manual", "auto"}:
                raise ValueError("invalid_door_mode")
            return normalized
        if key == "light_switch":
            normalized = str(value).strip().lower()
            if normalized not in {"off", "auto", "low_beam", "high_beam"}:
                raise ValueError("invalid_light_switch")
            return normalized
        return bool(value)

    def _active_flag(self, state: dict[str, Any], field_name: str) -> bool:
        now = time.time()
        with self._lock:
            deadline = self._pulse_deadlines.get(field_name)
            pulse_active = deadline is not None and deadline > now
        return bool(state.get(field_name, False) or pulse_active)

    @staticmethod
    def _direction_code(value: Any) -> int:
        normalized = str(value).strip().lower()
        if normalized == "forward":
            return DIR_FORWARD
        if normalized in {"backward", "reverse"}:
            return DIR_REVERSE
        return DIR_NEUTRAL

    @staticmethod
    def _main_handle_code(value: Any) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = 0
        if numeric not in {MAIN_HANDLE_COAST, MAIN_HANDLE_TRAC, MAIN_HANDLE_BRAKE, MAIN_HANDLE_FAST}:
            raise ValueError("invalid_main_handle_raw")
        return numeric

    @staticmethod
    def _door_mode_code(value: Any) -> int:
        mapping = {"semi_auto": 0, "manual": 1, "auto": 2}
        return mapping.get(str(value).strip().lower(), 1)

    @staticmethod
    def _light_switch_code(value: Any) -> int:
        mapping = {"off": 0, "auto": 1, "low_beam": 2, "high_beam": 4}
        return mapping.get(str(value).strip().lower(), 0)

    @staticmethod
    def _percent_value(value: Any) -> int:
        try:
            numeric = int(round(float(value)))
        except (TypeError, ValueError):
            numeric = 0
        return max(0, min(100, numeric))

    def _is_running(self) -> bool:
        with self._lock:
            return self._running


class DriverDeskTestRigService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bridge = DriverDeskBridgeService()
        self._simulator: DriverDeskProtocolSimulator | None = None

    def start(
        self,
        *,
        vehicle_id: str,
        simulator_host: str,
        simulator_port: int,
        pulse_width_ms: int = 250,
    ) -> dict[str, Any]:
        self.stop()
        simulator = DriverDeskProtocolSimulator(
            host=simulator_host,
            port=simulator_port,
            vehicle_id=vehicle_id,
            pulse_width_ms=pulse_width_ms,
        )
        try:
            simulator.start()
            with self._lock:
                self._simulator = simulator
            self._bridge.start(
                vehicle_id=vehicle_id,
                plc_host=simulator_host,
                plc_port=simulator_port,
            )
            return self.snapshot()
        except Exception:
            self._bridge.stop()
            simulator.stop()
            with self._lock:
                if self._simulator is simulator:
                    self._simulator = None
            raise

    def stop(self) -> dict[str, Any]:
        with self._lock:
            simulator = self._simulator
            self._simulator = None
        self._bridge.stop()
        if simulator is not None:
            simulator.stop()
        return self.snapshot()

    def update_input(self, updates: dict[str, Any]) -> dict[str, Any]:
        simulator = self._require_simulator()
        return simulator.update_input(updates)

    def pulse(self, field_name: str, duration_ms: int | None = None) -> dict[str, Any]:
        simulator = self._require_simulator()
        return simulator.pulse(field_name, duration_ms)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            simulator = self._simulator
        return {
            "simulator": simulator.snapshot() if simulator is not None else {
                "running": False,
                "listening": False,
                "client_connected": False,
            },
            "bridge": self._bridge.snapshot(),
        }

    def _require_simulator(self) -> DriverDeskProtocolSimulator:
        with self._lock:
            simulator = self._simulator
        if simulator is None:
            raise ValueError("simulator_not_running")
        return simulator


driver_desk_test_rig = DriverDeskTestRigService()
