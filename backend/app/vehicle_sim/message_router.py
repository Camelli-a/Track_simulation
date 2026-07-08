from .models import AtoCommand, CommState, DriverInput, MaLimit, PowerState, TrackSection
from .track_map import TrackMap
from .zmq_bus import normalize_message


class MessageRouter:
    def __init__(self, train_manager, default_dt: float = 0.1):
        self.train_manager = train_manager
        self.default_dt = default_dt

    def handle(self, message: dict):
        message = normalize_message(message)
        msg_type = message.get("type")

        if msg_type == "driver_input":
            self._handle_driver_input(message)
        elif msg_type == "ato_command":
            self._handle_ato_command(message)
        elif msg_type == "ma_state":
            self._handle_ma_state(message)
        elif msg_type == "power_state":
            self._handle_power_state(message)
        elif msg_type == "comm_state":
            self._handle_comm_state(message)
        elif msg_type == "track_info":
            self._handle_track_info(message)
        elif msg_type == "enable_fallback_ato":
            self._handle_enable_fallback_ato(message)
        elif msg_type == "set_train_state":
            self._handle_set_train_state(message)

    def _handle_driver_input(self, msg: dict):
        train = self.train_manager.get_train(msg["vehicle_id"])
        if train is None:
            return

        driver_input = DriverInput(
            vehicle_id=msg["vehicle_id"],
            line_id=msg.get("line_id", train.state.line_id),
            source=msg.get("source", "mock"),
            control_mode=msg.get("control_mode", "manual"),
            traction_level=int(msg.get("traction_level", 0)),
            brake_level=int(msg.get("brake_level", 0)),
            direction=msg.get("direction", "forward"),
            emergency_button=bool(msg.get("emergency_button", False)),
        )
        train.step_manual(driver_input, self.default_dt)

    def _handle_ato_command(self, msg: dict):
        train = self.train_manager.get_train(msg["vehicle_id"])
        if train is None:
            return

        target_position = msg.get("target_position")
        ato_command = AtoCommand(
            vehicle_id=msg["vehicle_id"],
            line_id=msg.get("line_id", train.state.line_id),
            control_mode=msg.get("control_mode", "ato"),
            target_speed=float(msg.get("target_speed", 0.0)),
            target_position=(
                None if target_position is None else float(target_position)
            ),
            traction_level=int(msg.get("traction_level", 0)),
            brake_level=int(msg.get("brake_level", 0)),
            reason=msg.get("reason", "test"),
        )
        train.step_ato(ato_command, self.default_dt)

    def _handle_ma_state(self, msg: dict):
        for item in msg.get("ma_limits", []):
            train = self.train_manager.get_train(item["vehicle_id"])
            if train is None:
                continue

            ma = MaLimit(
                vehicle_id=item["vehicle_id"],
                ma_limit=float(item["ma_limit"]),
                target_speed=item.get("target_speed"),
                reason=item.get("reason", "unknown"),
            )
            train.apply_ma_state(ma)

    def _handle_power_state(self, msg: dict):
        power = PowerState(
            substation_id=msg.get("substation_id", "SS-01"),
            voltage=float(msg.get("voltage", 1500.0)),
            current=float(msg.get("current", 0.0)),
            power=float(msg.get("power", 0.0)),
            is_fault=bool(msg.get("is_fault", False)),
        )
        for train in self.train_manager.trains.values():
            train.apply_power_state(power)

    def _handle_comm_state(self, msg: dict):
        comm = CommState(
            source=msg.get("source", "mock"),
            driver_console_connected=bool(
                msg.get("driver_console_connected", True)
            ),
            zmq_connected=bool(msg.get("zmq_connected", True)),
            last_message_at=float(msg.get("last_message_at", 0.0)),
        )
        for train in self.train_manager.trains.values():
            train.apply_comm_state(comm)

    def _handle_track_info(self, msg: dict):
        sections = [
            TrackSection(
                section_id=section["section_id"],
                start=float(section["start"]),
                end=float(section["end"]),
                gradient=float(section["gradient"]),
                speed_limit=float(section["speed_limit"]),
                station_id=section.get("station_id"),
                stop_position=section.get("stop_position"),
            )
            for section in msg.get("sections", [])
        ]
        if not sections:
            return

        track = TrackMap(sections)
        for train in self.train_manager.trains.values():
            train.track = track

    def _handle_enable_fallback_ato(self, msg: dict):
        train = self.train_manager.get_train(msg["vehicle_id"])
        if train is None:
            return
        train.enable_fallback_ato(float(msg["target_position"]))

    def _handle_set_train_state(self, msg: dict):
        train = self.train_manager.get_train(msg["vehicle_id"])
        if train is None:
            return

        if "position" in msg:
            train.state.position = float(msg["position"])
        if "speed" in msg:
            train.state.speed_ms = float(msg["speed"]) / 3.6
        if "acceleration" in msg:
            train.state.acceleration = float(msg["acceleration"])
        if "mode" in msg and not train.state.emergency_brake:
            train.state.mode = msg["mode"]
        train.state.is_running = train.state.speed_ms > 0.0
