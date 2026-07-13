import time

from .adapters.command_mapping import command_percent_to_levels
from .adapters.driver_plc_mapping import decode_driver_control, direction_code_to_text
from .adapters.id_mapping import index_to_vehicle_id, vehicle_id_to_index
from .models import AtoCommand, CommState, DriverInput, MaLimit, PowerState, TrackSection
from .track_map import TrackMap
from .zmq_bus import normalize_message


class MessageRouter:
    def __init__(
        self,
        train_manager,
        default_dt: float = 0.1,
        physical_driver_vehicle_id: str = "TRAIN-001",
        owned_vehicle_id: str | None = None,
    ):
        self.train_manager = train_manager
        self.default_dt = default_dt
        self.physical_driver_vehicle_id = physical_driver_vehicle_id
        self.owned_vehicle_id = owned_vehicle_id

    def handle(self, message: dict):
        message = normalize_message(message)
        msg_type = message.get("type")

        if msg_type == "driver_input":
            return self._handle_driver_input(message)
        elif msg_type == "ato_command":
            self._handle_ato_command(message)
        elif msg_type == "ma_state":
            self._handle_ma_state(message)
        elif msg_type == "speed_constraint":
            return self._handle_speed_constraint(message)
        elif msg_type in {"signal_state", "interlocking_state"}:
            return self._handle_signal_or_interlocking_state(message)
        elif msg_type == "power_state":
            self._handle_power_state(message)
        elif msg_type == "comm_state":
            self._handle_comm_state(message)
        elif msg_type == "track_info":
            self._handle_track_info(message)
        elif msg_type == "fault_event":
            return self._handle_fault_event(message)
        elif msg_type == "enable_fallback_ato":
            self._handle_enable_fallback_ato(message)
        elif msg_type == "set_train_state":
            return self._handle_set_train_state(message)
        elif msg_type == "add_train":
            return self._handle_add_train(message)
        elif msg_type == "remove_train":
            return self._handle_remove_train(message)
        elif msg_type == "clear_trains":
            if self.owned_vehicle_id is not None:
                return {
                    "ok": True,
                    "ignored": True,
                    "reason": "single_train_process_ignores_clear_trains",
                }
            return self.train_manager.clear_trains()
        elif msg_type == "reset_trains":
            if self.owned_vehicle_id is not None:
                return self._reset_owned_train()
            return self.train_manager.reset_trains(int(message.get("count", 10)))

    def _handle_driver_input(self, msg: dict):
        source = str(msg.get("source", "mock")).lower()
        physical_source = source in {"driver_tcp", "driver_desk", "driver_plc", "plc"}
        if physical_source:
            vehicle_id = msg.get("vehicle_id")
            if not isinstance(vehicle_id, str) or not vehicle_id:
                return {"ok": False, "reason": "driver_input_requires_vehicle_id"}
            if vehicle_id != self.physical_driver_vehicle_id:
                return {
                    "ok": False,
                    "reason": "physical_driver_vehicle_mismatch",
                    "vehicle_id": vehicle_id,
                }
        else:
            vehicle_id = self._target_vehicle_id(msg)
            if vehicle_id is None:
                return {"ok": True, "ignored": True, "reason": "vehicle_id_not_owned"}
        train = self.train_manager.get_train(vehicle_id)
        if train is None:
            return {"ok": False, "reason": "train_not_found", "vehicle_id": vehicle_id}

        normalized_message = dict(msg)
        if msg.get("command") is not None and not any(
            field in msg
            for field in (
                "main_handle_raw",
                "main_handle_state",
                "traction_percent",
                "brake_percent",
            )
        ):
            command = int(msg.get("command", 0))
            percent = float(msg.get("percent", 0.0))
            if command == 1:
                normalized_message["traction_percent"] = percent
            elif command == 2:
                normalized_message["brake_percent"] = percent
        control = decode_driver_control(normalized_message)

        direction_code = (
            None if msg.get("direction_code") is None else int(msg["direction_code"])
        )
        direction = msg.get("direction", direction_code_to_text(direction_code))

        driver_input = DriverInput(
            vehicle_id=vehicle_id,
            line_id=msg.get("line_id", train.state.line_id),
            source=msg.get("source", "mock"),
            control_mode=msg.get("control_mode", "manual"),
            traction_level=control.traction_level,
            brake_level=control.brake_level,
            direction=direction,
            emergency_button=bool(msg.get("emergency_button", False)),
            command=msg.get("command"),
            percent=msg.get("percent"),
            main_handle_raw=msg.get("main_handle_raw", msg.get("main_handle_state")),
            main_handle_state=msg.get("main_handle_state"),
            traction_percent=control.traction_percent,
            brake_percent=control.brake_percent,
            direction_code=direction_code,
            emergency_cmd=bool(msg.get("emergency_cmd", False)),
            key_switch=msg.get("key_switch"),
            ato_start_btn=bool(msg.get("ato_start_btn", False)),
            ato_capable=msg.get("ato_capable"),
            ato_active=msg.get("ato_active"),
            auto_reverse_cap=msg.get("auto_reverse_cap"),
            auto_reverse_active=msg.get("auto_reverse_active"),
            auto_rev_flag=bool(msg.get("auto_rev_flag", False)),
            mode_up_confirm=bool(msg.get("mode_up_confirm", False)),
            mode_dn_confirm=bool(msg.get("mode_dn_confirm", False)),
            vigilance=bool(msg.get("vigilance", False)),
            vigilance_allow=bool(msg.get("vigilance_allow", False)),
            forced_release=bool(msg.get("forced_release", False)),
            parking_apply=bool(msg.get("parking_apply", False)),
            parking_release=bool(msg.get("parking_release", False)),
            brake_bad_light=msg.get("brake_bad_light"),
            network_fault_light=msg.get("network_fault_light"),
            open_left_door=bool(msg.get("open_left_door", False)),
            open_right_door=bool(msg.get("open_right_door", False)),
            close_left_door=bool(msg.get("close_left_door", False)),
            close_right_door=bool(msg.get("close_right_door", False)),
            door_mode=msg.get("door_mode"),
            door_closed_light=msg.get("door_closed_light"),
            high_voltage_light=msg.get("high_voltage_light"),
            forced_pump=bool(msg.get("forced_pump", False)),
            horn=bool(msg.get("horn", False)),
            confirm_flag=bool(msg.get("confirm_flag", False)),
            trac_aux_reset=bool(msg.get("trac_aux_reset", False)),
            wash_mode_switch=bool(msg.get("wash_mode_switch", False)),
            frame_seq=(
                None if msg.get("frame_seq") is None else int(msg["frame_seq"])
            ),
            message_id=(
                None if msg.get("message_id") is None else str(msg["message_id"])
            ),
            raw_brake_level=msg.get("brake_level"),
            fast_brake=control.handle_mode == "fast_brake",
        )
        train.step_manual(driver_input, self.default_dt)
        if driver_input.emergency_button or driver_input.emergency_cmd:
            train.state.emergency_brake = True
            train.state.mode = "emergency"
        return {"ok": True, "vehicle_id": vehicle_id}

    def _handle_ato_command(self, msg: dict):
        vehicle_id = self._target_vehicle_id(msg)
        if vehicle_id is None:
            return
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
        ma_limits = msg.get("ma_limits")
        if ma_limits is None and msg.get("vehicle_id"):
            ma_limits = [msg]

        for item in ma_limits or []:
            vehicle_id = self._target_vehicle_id(item)
            if vehicle_id is None:
                continue
            train = self.train_manager.get_train(vehicle_id)
            if train is None:
                continue

            ma = MaLimit(
                vehicle_id=vehicle_id,
                ma_limit=self._optional_float(
                    item.get("ma_limit", item.get("ma_limit_m"))
                ),
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
                updated_at=self._timestamp_or_now(
                    item.get("updated_at", item.get("timestamp", msg.get("timestamp")))
                ),
            )
            train.apply_ma_state(ma)
            stop_target_m = self._optional_float(
                item.get(
                    "stop_target_m",
                    item.get("stop_target", item.get("target_position")),
                )
            )
            if stop_target_m is not None:
                train.set_next_stop_target_m(stop_target_m)

    def _handle_power_state(self, msg: dict):
        if not self._should_handle_broadcast_or_owned(msg):
            return
        power = PowerState(
            substation_id=msg.get("substation_id", "SS-01"),
            voltage=float(msg.get("voltage", 1500.0)),
            current=float(msg.get("current", 0.0)),
            power=float(msg.get("power", 0.0)),
            is_fault=bool(msg.get("is_fault", False)),
        )
        for train in self.train_manager.trains.values():
            train.apply_power_state(power)

    def _handle_speed_constraint(self, msg: dict):
        vehicle_id = msg.get("vehicle_id")
        if not vehicle_id:
            return {"ok": False, "reason": "speed_constraint_requires_vehicle_id"}
        train = self.train_manager.get_train(str(vehicle_id))
        if train is None:
            return {"ok": False, "reason": "train_not_found", "vehicle_id": vehicle_id}
        raw_limit = msg.get(
            "speed_limit_kmh",
            msg.get("allowed_speed_kmh", msg.get("speed_limit")),
        )
        if raw_limit is None:
            return {"ok": False, "reason": "missing_speed_limit"}
        train.apply_speed_constraint(
            float(raw_limit),
            reason=str(msg.get("reason", "external_constraint")),
            updated_at=self._timestamp_or_now(
                msg.get("updated_at", msg.get("timestamp"))
            ),
        )
        return {"ok": True, "vehicle_id": vehicle_id}

    def _handle_signal_or_interlocking_state(self, msg: dict):
        vehicle_id = msg.get("vehicle_id")
        if not vehicle_id:
            return {"ok": False, "reason": "safety_state_requires_vehicle_id"}
        train = self.train_manager.get_train(str(vehicle_id))
        if train is None:
            return {"ok": False, "reason": "train_not_found", "vehicle_id": vehicle_id}
        train.apply_signal_state(
            signal_state=msg.get("signal_state", msg.get("state")),
            permission=msg.get("permission", msg.get("movement_permission")),
        )
        return {"ok": True, "vehicle_id": vehicle_id}

    def _handle_fault_event(self, msg: dict):
        fault_type = msg.get("fault_type", msg.get("code"))
        if not fault_type:
            return {"ok": False, "reason": "missing_fault_type"}
        scope_all = msg.get("scope") in {"all", "system"}
        vehicle_id = msg.get("vehicle_id")
        if not scope_all and not vehicle_id:
            return {"ok": False, "reason": "fault_event_requires_vehicle_id_or_scope"}
        if scope_all:
            trains = tuple(self.train_manager.trains.values())
        else:
            train = self.train_manager.get_train(str(vehicle_id))
            if train is None:
                return {"ok": False, "reason": "train_not_found", "vehicle_id": vehicle_id}
            trains = (train,)
        active = bool(msg.get("active", msg.get("is_active", True)))
        severity = str(msg.get("severity", "warning"))
        for train in trains:
            train.apply_fault_event(str(fault_type), active=active, severity=severity)
        return {"ok": True, "affected": len(trains), "fault_type": fault_type}

    def _handle_comm_state(self, msg: dict):
        if not self._should_handle_broadcast_or_owned(msg):
            return
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
        if not self._should_handle_broadcast_or_owned(msg):
            return
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
        vehicle_id = self._target_vehicle_id(msg)
        if vehicle_id is None:
            return
        train = self.train_manager.get_train(vehicle_id)
        if train is None:
            return
        train.enable_fallback_ato(float(msg["target_position"]))

    def _handle_set_train_state(self, msg: dict):
        vehicle_id = self._target_vehicle_id(msg)
        if vehicle_id is None:
            return {
                "ok": True,
                "ignored": True,
                "reason": "vehicle_id_not_owned",
            }
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

    def _message_vehicle_id(self, data: dict) -> str | None:
        if data.get("vehicle_id") is not None:
            return data["vehicle_id"]
        if data.get("train_index") is not None:
            train = self.train_manager.get_train_by_slot(int(data["train_index"]))
            if train is not None:
                return train.state.vehicle_id
            return index_to_vehicle_id(int(data["train_index"]))
        return None

    def _is_owned_vehicle(self, vehicle_id: str | None) -> bool:
        if self.owned_vehicle_id is None:
            return True
        return vehicle_id == self.owned_vehicle_id

    def _target_vehicle_id(self, msg: dict) -> str | None:
        if self.owned_vehicle_id is not None:
            vehicle_id = self._message_vehicle_id(msg)
            return vehicle_id if self._is_owned_vehicle(vehicle_id) else None
        return self._resolve_vehicle_id(msg)

    def _should_handle_broadcast_or_owned(self, msg: dict) -> bool:
        vehicle_id = self._message_vehicle_id(msg)
        if vehicle_id is None:
            return True
        return self._is_owned_vehicle(vehicle_id)

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

    def _timestamp_or_now(self, value):
        timestamp = self._optional_float(value)
        return time.time() if timestamp is None else timestamp

    def _handle_add_train(self, msg: dict):
        if self.owned_vehicle_id is not None:
            vehicle_id = msg.get("vehicle_id")
            if vehicle_id != self.owned_vehicle_id:
                return {
                    "ok": True,
                    "ignored": True,
                    "reason": "vehicle_id_not_owned",
                }
            if self.train_manager.get_train(vehicle_id) is not None:
                return {
                    "ok": True,
                    "ignored": True,
                    "reason": "train_already_exists_in_single_process",
                    "vehicle_id": vehicle_id,
                }

        return self.train_manager.add_train(
            vehicle_id=msg.get("vehicle_id"),
            slot=(
                None if msg.get("train_index") is None else int(msg["train_index"])
            ),
            position=float(msg.get("position", 0.0)),
            line_id=msg.get("line_id", "LINE-1"),
        )

    def _handle_remove_train(self, msg: dict):
        if self.owned_vehicle_id is not None:
            vehicle_id = self._message_vehicle_id(msg)
            if not self._is_owned_vehicle(vehicle_id):
                return {
                    "ok": True,
                    "ignored": True,
                    "reason": "vehicle_id_not_owned",
                }
            return {
                "ok": True,
                "ignored": True,
                "reason": "single_train_process_ignores_remove_train",
                "vehicle_id": self.owned_vehicle_id,
            }

        return self.train_manager.remove_train(
            vehicle_id=msg.get("vehicle_id"),
            slot=(
                None if msg.get("train_index") is None else int(msg["train_index"])
            ),
        )

    def _reset_owned_train(self):
        vehicle_id = self.owned_vehicle_id
        existing = self.train_manager.get_train(vehicle_id)
        line_id = "LINE-1" if existing is None else existing.state.line_id
        try:
            slot = vehicle_id_to_index(vehicle_id)
        except ValueError:
            slot = 1 if existing is None else existing.state.train_index

        self.train_manager.clear_trains()
        return self.train_manager.add_train(
            vehicle_id=vehicle_id,
            slot=slot,
            position=0.0,
            line_id=line_id,
        )
