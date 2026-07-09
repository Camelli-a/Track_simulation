import time

from .adapters.command_mapping import command_percent_to_levels
from .adapters.driver_plc_mapping import decode_driver_handle, direction_code_to_text
from .adapters.id_mapping import index_to_vehicle_id
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
            return self._handle_set_train_state(message)
        elif msg_type == "add_train":
            return self._handle_add_train(message)
        elif msg_type == "remove_train":
            return self._handle_remove_train(message)
        elif msg_type == "clear_trains":
            return self.train_manager.clear_trains()
        elif msg_type == "reset_trains":
            return self.train_manager.reset_trains(int(message.get("count", 10)))

    def _handle_driver_input(self, msg: dict):
        vehicle_id = self._resolve_vehicle_id(msg)
        train = self.train_manager.get_train(vehicle_id)
        if train is None:
            return

        traction_level = int(msg.get("traction_level", 0))
        brake_level = int(msg.get("brake_level", 0))
        if msg.get("main_handle_state") is not None:
            traction_level, brake_level = decode_driver_handle(msg)
        elif msg.get("command") is not None:
            traction_level, brake_level = command_percent_to_levels(
                int(msg.get("command", 0)),
                float(msg.get("percent", 0.0)),
            )

        direction_code = (
            None if msg.get("direction_code") is None else int(msg["direction_code"])
        )
        direction = msg.get("direction", direction_code_to_text(direction_code))

        driver_input = DriverInput(
            vehicle_id=vehicle_id,
            line_id=msg.get("line_id", train.state.line_id),
            source=msg.get("source", "mock"),
            control_mode=msg.get("control_mode", "manual"),
            traction_level=traction_level,
            brake_level=brake_level,
            direction=direction,
            emergency_button=bool(msg.get("emergency_button", False)),
            command=msg.get("command"),
            percent=msg.get("percent"),
            main_handle_state=msg.get("main_handle_state"),
            traction_percent=msg.get("traction_percent"),
            brake_percent=msg.get("brake_percent"),
            direction_code=direction_code,
        )
        train.step_manual(driver_input, self.default_dt)

    def _handle_ato_command(self, msg: dict):
        vehicle_id = self._resolve_vehicle_id(msg)
        train = self.train_manager.get_train(vehicle_id)
        if train is None:
            return

        target_position = msg.get("target_position")
        traction_level = int(msg.get("traction_level", 0))
        brake_level = int(msg.get("brake_level", 0))
        if msg.get("command") is not None:
            traction_level, brake_level = command_percent_to_levels(
                int(msg.get("command", 0)),
                float(msg.get("percent", 0.0)),
            )

        ato_command = AtoCommand(
            vehicle_id=vehicle_id,
            line_id=msg.get("line_id", train.state.line_id),
            control_mode=msg.get("control_mode", "ato"),
            target_speed=float(msg.get("target_speed", 0.0)),
            target_position=(
                None if target_position is None else float(target_position)
            ),
            traction_level=traction_level,
            brake_level=brake_level,
            reason=msg.get("reason", "test"),
            command=msg.get("command"),
            percent=msg.get("percent"),
        )
        train.step_ato(ato_command, self.default_dt)

    def _handle_ma_state(self, msg: dict):
        for item in msg.get("ma_limits", []):
            vehicle_id = self._resolve_vehicle_id(item)
            train = self.train_manager.get_train(vehicle_id)
            if train is None:
                continue

            ma = MaLimit(
                vehicle_id=vehicle_id,
                ma_limit=float(item.get("ma_limit", item.get("ma_limit_m", 0.0))),
                target_speed=self._optional_float(
                    item.get("target_speed", item.get("target_speed_kmh"))
                ),
                reason=item.get("reason", "unknown"),
                allowed_speed_kmh=self._optional_float(
                    item.get("allowed_speed_kmh", item.get("speed_limit"))
                ),
                eb_trigger_speed_kmh=self._optional_float(
                    item.get("eb_trigger_speed_kmh")
                ),
                target_distance_m=self._optional_float(
                    item.get("target_distance_m", item.get("distance_to_ma"))
                ),
                permission=item.get("permission"),
                signal_state=item.get("signal_state"),
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
            last_message_at=float(msg.get("last_message_at", time.time())),
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
                edge_id=section.get("edge_id"),
                begin_km=section.get("begin_km"),
                end_km=section.get("end_km"),
                begin_switch=section.get("begin_switch"),
                end_switch=section.get("end_switch"),
                direction_code=int(section.get("direction_code", 1)),
            )
            for section in msg.get("sections", [])
        ]
        if not sections:
            return

        track = TrackMap(sections)
        for train in self.train_manager.trains.values():
            train.track = track

    def _handle_enable_fallback_ato(self, msg: dict):
        vehicle_id = self._resolve_vehicle_id(msg)
        train = self.train_manager.get_train(vehicle_id)
        if train is None:
            return
        train.enable_fallback_ato(float(msg["target_position"]))

    def _handle_set_train_state(self, msg: dict):
        vehicle_id = self._resolve_vehicle_id(msg)
        train = self.train_manager.get_train(vehicle_id)
        created = False
        if train is None:
            result = self.train_manager.add_train(
                vehicle_id=vehicle_id,
                slot=(
                    None if msg.get("train_index") is None else int(msg["train_index"])
                ),
                position=float(msg.get("position", 0.0)),
                line_id=msg.get("line_id", "LINE-1"),
            )
            if not result.get("ok"):
                return result
            train = self.train_manager.get_train(vehicle_id)
            if train is None:
                return result
            created = True

        if "position" in msg:
            train.state.position = float(msg["position"])
        if "speed" in msg:
            train.state.speed_ms = float(msg["speed"]) / 3.6
        if "acceleration" in msg:
            train.state.acceleration = float(msg["acceleration"])
        if "mode" in msg and not train.state.emergency_brake:
            train.state.mode = msg["mode"]
        if "direction_code" in msg:
            train.state.direction_code = int(msg["direction_code"])
        train.state.is_running = train.state.speed_ms > 0.0
        return {
            "ok": True,
            "vehicle_id": train.state.vehicle_id,
            "train_index": train.state.train_index,
            "created": created,
        }

    def _resolve_vehicle_id(self, msg: dict) -> str:
        if "vehicle_id" in msg:
            return msg["vehicle_id"]
        if "train_index" in msg:
            train = self.train_manager.get_train_by_slot(int(msg["train_index"]))
            if train is not None:
                return train.state.vehicle_id
            return index_to_vehicle_id(int(msg["train_index"]))
        raise KeyError("message must include vehicle_id or train_index")

    def _optional_float(self, value):
        return None if value is None else float(value)

    def _handle_add_train(self, msg: dict):
        return self.train_manager.add_train(
            vehicle_id=msg.get("vehicle_id"),
            slot=(
                None if msg.get("train_index") is None else int(msg["train_index"])
            ),
            position=float(msg.get("position", 0.0)),
            line_id=msg.get("line_id", "LINE-1"),
        )

    def _handle_remove_train(self, msg: dict):
        return self.train_manager.remove_train(
            vehicle_id=msg.get("vehicle_id"),
            slot=(
                None if msg.get("train_index") is None else int(msg["train_index"])
            ),
        )
