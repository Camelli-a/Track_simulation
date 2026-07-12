import time

from .adapters.command_mapping import (
    command_percent_to_levels,
    normalize_driver_brake_level,
    normalize_driver_traction_level,
)
from .adapters.id_mapping import vehicle_id_to_index
from .atp import AtpConfig, evaluate_atp
from .controllers.train_ato_controller import AtoControlInput, TrainAtoController
from .dynamics import update_dynamics
from .models import AtoCommand, CommState, DriverInput, MaLimit, PowerState, TrainState
from .track_map import TrackMap


class Train:
    """Single train instance with independent state and dynamics."""

    def __init__(
        self,
        vehicle_id: str,
        line_id: str,
        track: TrackMap,
        train_index: int | None = None,
    ):
        if train_index is None:
            train_index = vehicle_id_to_index(vehicle_id)

        self.state = TrainState(
            vehicle_id=vehicle_id,
            line_id=line_id,
            position=0.0,
            speed_ms=0.0,
            acceleration=0.0,
            mode="manual",
            is_running=False,
            emergency_brake=False,
            train_index=train_index,
        )

        self.track = track
        self.ma_limit = None
        self.allowed_speed_kmh = None
        self.eb_trigger_speed_kmh = None
        self.target_speed_kmh = None
        self.target_distance_m = None
        self.permission = None
        self.signal_state = None
        self.power_fault = False
        self.power_factor = 1.0
        self.comm_ok = True
        self.last_comm_message_at = None
        self.comm_timeout_sec = 1.6
        self.last_ma_updated_at = None
        self.last_alarm = None
        self.last_atp_decision = None
        self.last_atp_alarm_reason = None
        self.atp_triggered = False
        self.train_ato_controller = TrainAtoController()
        self.last_ato_output = None
        self.ato_control_delay_sec = TrainAtoController.DEFAULT_CONTROL_DELAY_SEC
        self.ato_delay_compensation_enabled = True
        self.ato_gradient_compensation_enabled = True
        self.ato_jerk_limit_enabled = True
        self.current_traction_level = 0
        self.current_brake_level = 0
        self.cached_traction_level = 0
        self.cached_brake_level = 0
        self.cached_external_ato_command = None
        self.last_driver_input = None
        self.raw_traction_percent = None
        self.raw_brake_percent = None
        self.raw_brake_level = None
        self.fast_brake = False
        self.driving_mode = "SM"
        self.emergency_pending = False
        self.driver_key_off = False
        self.driver_network_fault = False
        self.ato_capable = False
        self.ato_active = False
        self.ato_start_btn = False
        self.commanded_traction_level = 0
        self.commanded_brake_level = 0
        self.applied_traction_level = 0
        self.applied_brake_level = 0
        self.ato_traction_level = 0
        self.ato_brake_level = 0
        self.recommended_speed = 0.0
        self.ato_target_speed = 0.0
        self.ato_state = "manual_recommend"
        self.control_source = "manual"
        self.atp_intervened = False
        self.next_stop_target_m = None
        self.distance_to_stop = None
        self.stop_target = None
        self.last_stop_result = None
        self.last_stop_result_target_m = None
        self.stop_result_published_for_target = False
        self.fallback_ato = None

    def apply_ma_state(self, ma_limit: MaLimit):
        if ma_limit.vehicle_id == self.state.vehicle_id:
            self.ma_limit = ma_limit.ma_limit
            self.allowed_speed_kmh = ma_limit.allowed_speed_kmh
            self.eb_trigger_speed_kmh = ma_limit.eb_trigger_speed_kmh
            self.target_speed_kmh = ma_limit.target_speed
            self.target_distance_m = ma_limit.target_distance_m
            self.permission = ma_limit.permission
            self.signal_state = ma_limit.signal_state
            self.last_ma_updated_at = time.time()

    def apply_power_state(self, power: PowerState):
        self.power_fault = power.is_fault or power.voltage < 1000.0
        self.power_factor = 0.0 if self.power_fault else 1.0

    def apply_comm_state(self, comm: CommState):
        self.comm_ok = comm.driver_console_connected and comm.zmq_connected
        self.last_comm_message_at = comm.last_message_at

    def step_manual(self, driver_input: DriverInput, dt: float):
        if driver_input.vehicle_id != self.state.vehicle_id:
            return

        traction_level, brake_level = self._resolve_command_levels(
            driver_input.traction_level,
            driver_input.brake_level,
            driver_input.command,
            driver_input.percent,
        )
        if driver_input.raw_brake_level is not None:
            brake_level = normalize_driver_brake_level(driver_input.raw_brake_level)
        else:
            brake_level = normalize_driver_traction_level(brake_level)
        traction_level = normalize_driver_traction_level(traction_level)

        main_handle = (
            driver_input.main_handle_raw
            if driver_input.main_handle_raw is not None
            else driver_input.main_handle_state
        )
        try:
            main_handle_code = None if main_handle is None else int(main_handle)
        except (TypeError, ValueError):
            main_handle_code = None
        fast_brake = bool(driver_input.fast_brake or main_handle_code == 4)
        if fast_brake:
            traction_level = 0
            brake_level = 4
        elif brake_level > 0:
            traction_level = 0

        if driver_input.key_switch is False:
            traction_level = 0

        self.last_driver_input = driver_input
        self.cached_traction_level = traction_level
        self.cached_brake_level = brake_level
        self.current_traction_level = traction_level
        self.current_brake_level = brake_level
        self.raw_traction_percent = driver_input.traction_percent
        self.raw_brake_percent = driver_input.brake_percent
        self.raw_brake_level = driver_input.raw_brake_level
        self.fast_brake = fast_brake
        self.driver_key_off = driver_input.key_switch is False
        self.driver_network_fault = bool(driver_input.network_fault_light)
        self.ato_capable = bool(driver_input.ato_capable)
        self.ato_active = bool(driver_input.ato_active)
        self.ato_start_btn = bool(driver_input.ato_start_btn)
        if (driver_input.control_mode or "").lower() == "ato" or driver_input.ato_active:
            self.driving_mode = "AM"
        else:
            self.driving_mode = "SM"

        self._apply_driver_direction(driver_input)

        if driver_input.emergency_button or driver_input.emergency_cmd:
            self.state.emergency_brake = True
            self.emergency_pending = True
            self.state.mode = "emergency"
            self.cached_traction_level = 0
            self.cached_brake_level = 4
            self.current_traction_level = 0
            self.current_brake_level = 4

    def step_ato(self, ato_command: AtoCommand, dt: float):
        if ato_command.vehicle_id != self.state.vehicle_id:
            return

        traction_level, brake_level = self._resolve_command_levels(
            ato_command.traction_level,
            ato_command.brake_level,
            ato_command.command,
            ato_command.percent,
        )
        traction_level = normalize_driver_traction_level(traction_level)
        brake_level = normalize_driver_traction_level(brake_level)
        if brake_level > 0:
            traction_level = 0

        self.cached_external_ato_command = ato_command
        self.cached_traction_level = traction_level
        self.cached_brake_level = brake_level
        self.current_traction_level = traction_level
        self.current_brake_level = brake_level

    def step_tick(self, dt: float):
        stop_target_m = self._resolve_stop_target_m()
        ma_age_sec = None
        if self.last_ma_updated_at is not None:
            ma_age_sec = time.time() - self.last_ma_updated_at
        gradient_permille = self._resolve_gradient_permille()

        ato_input = AtoControlInput(
            vehicle_id=self.state.vehicle_id,
            position_m=self.state.position,
            speed_ms=self.state.speed_ms,
            ma_limit_m=self.ma_limit,
            allowed_speed_kmh=self.allowed_speed_kmh,
            stop_target_m=stop_target_m,
            target_distance_m=self.target_distance_m,
            permission=self.permission,
            signal_state=self.signal_state,
            driving_mode=self.driving_mode,
            direction=self.state.direction_code,
            ma_valid=self.ma_limit is not None and self.allowed_speed_kmh is not None,
            ma_age_sec=ma_age_sec,
            max_ma_age_sec=self.comm_timeout_sec,
            comm_ok=self.comm_ok,
            dt=dt,
            acceleration_ms2=self.state.acceleration,
            control_delay_sec=self.ato_control_delay_sec,
            delay_compensation_enabled=self.ato_delay_compensation_enabled,
            gradient_permille=gradient_permille,
            gradient_compensation_enabled=self.ato_gradient_compensation_enabled,
            previous_commanded_traction_level=self.commanded_traction_level,
            previous_commanded_brake_level=self.commanded_brake_level,
            jerk_limit_enabled=self.ato_jerk_limit_enabled,
        )
        ato_output = self.train_ato_controller.compute_control(ato_input)
        self.last_ato_output = ato_output
        self.ato_traction_level = ato_output.ato_traction_level
        self.ato_brake_level = ato_output.ato_brake_level
        self.recommended_speed = ato_output.recommended_speed_kmh
        self.ato_target_speed = ato_output.ato_target_speed_kmh
        self.ato_state = ato_output.ato_state
        self.distance_to_stop = ato_output.distance_to_stop_m
        self.stop_target = stop_target_m

        if self.state.emergency_brake:
            traction_level = 0
            brake_level = 4
            control_source = "emergency"
            self.state.mode = "emergency"
        elif self.driving_mode == "AM":
            traction_level = ato_output.commanded_traction_level
            brake_level = ato_output.commanded_brake_level
            control_source = ato_output.control_source or "ato"
            if ato_output.degraded:
                traction_level = 0
                brake_level = max(brake_level, 2)
                control_source = "degraded"
            self.state.mode = "ato"
        elif self.fallback_ato is not None:
            traction_level, brake_level, _ = self.fallback_ato.compute(
                position=self.state.position,
                speed_kmh=self.state.speed_kmh,
            )
            control_source = "ato"
            self.state.mode = "ato"
        else:
            traction_level = self.cached_traction_level
            brake_level = self.cached_brake_level
            control_source = "manual"
            self.state.mode = "manual"

        traction_level, brake_level = self.train_ato_controller.resolve_exclusive_levels(
            traction_level, brake_level
        )
        self.commanded_traction_level = traction_level
        self.commanded_brake_level = brake_level
        self.control_source = control_source
        self.current_traction_level = traction_level
        self.current_brake_level = brake_level

        self._step(traction_level, brake_level, dt)
        self.distance_to_stop = (
            None if self.stop_target is None else self.stop_target - self.state.position
        )
        self._maybe_generate_stop_result()
        self._sync_control_state_to_train_state()

    def enable_fallback_ato(self, target_position: float):
        from .controllers.fallback_ato import FallbackAtoController

        self.fallback_ato = FallbackAtoController(target_position)
        if not self.state.emergency_brake:
            self.state.mode = "ato"

    def _step(self, traction_level: int, brake_level: int, dt: float):
        speed_limit = self.track.get_speed_limit(self.state.position)
        atp_decision = evaluate_atp(
            self.state,
            speed_limit=speed_limit,
            ma_limit=self.ma_limit,
            allowed_speed_kmh=self.allowed_speed_kmh,
            eb_trigger_speed_kmh=self.eb_trigger_speed_kmh,
            target_distance_m=self.target_distance_m,
            power_fault=self.power_fault,
            comm_ok=self.comm_ok,
            last_message_at=self.last_comm_message_at,
            config=AtpConfig(comm_timeout_sec=self.comm_timeout_sec),
        )
        self.last_atp_decision = atp_decision

        if atp_decision.alarm is not None and not atp_decision.emergency_brake:
            if self.last_atp_alarm_reason != atp_decision.reason:
                self.last_alarm = atp_decision.alarm
                self.last_atp_alarm_reason = atp_decision.reason

        if atp_decision.emergency_brake or self.state.emergency_brake:
            was_emergency = self.state.emergency_brake
            self.state.emergency_brake = True
            self.state.mode = "emergency"
            if atp_decision.emergency_brake and not was_emergency and not self.atp_triggered:
                self.last_alarm = atp_decision.alarm
                self.atp_triggered = True
                self.last_atp_alarm_reason = atp_decision.reason
            traction_level = 0
            brake_level = 4
            self.cached_traction_level = traction_level
            self.cached_brake_level = brake_level
            self.current_traction_level = traction_level
            self.current_brake_level = brake_level
            self.control_source = "emergency"
            self.atp_intervened = bool(atp_decision.emergency_brake)
        else:
            self.atp_intervened = False

        traction_level, brake_level = self.train_ato_controller.resolve_exclusive_levels(
            traction_level, brake_level
        )
        self.applied_traction_level = traction_level
        self.applied_brake_level = brake_level

        gradient = self.track.get_gradient(self.state.position)

        new_speed, new_position, acc, _, _ = update_dynamics(
            speed_ms=self.state.speed_ms,
            position=self.state.position,
            traction_level=traction_level,
            brake_level=brake_level,
            gradient=gradient,
            dt=dt,
            power_factor=self.power_factor,
            emergency_brake=self.state.emergency_brake,
        )

        self.state.speed_ms = new_speed
        self.state.position = new_position
        self.state.acceleration = acc
        self.state.is_running = new_speed > 0.0
        self._update_track_position()

    def _resolve_command_levels(
        self,
        traction_level: int,
        brake_level: int,
        command: int | None,
        percent: float | None,
    ) -> tuple[int, int]:
        if command is not None:
            return command_percent_to_levels(command, 0.0 if percent is None else percent)
        return traction_level, brake_level

    def _apply_driver_direction(self, driver_input: DriverInput):
        if driver_input.direction_code is not None:
            if driver_input.direction_code == 2:
                self.state.direction_code = -1
            elif driver_input.direction_code == 0:
                self.state.direction_code = 0
            else:
                self.state.direction_code = 1
            return

        direction = (driver_input.direction or "").lower()
        if direction in ("backward", "reverse"):
            self.state.direction_code = -1
        elif direction == "neutral":
            self.state.direction_code = 0
        elif direction == "forward":
            self.state.direction_code = 1

    def _resolve_stop_target_m(self):
        if self.next_stop_target_m is not None:
            return self.next_stop_target_m
        if hasattr(self.track, "get_stop_position"):
            return self.track.get_stop_position(self.state.position)
        return None

    def _resolve_gradient_permille(self) -> float:
        if hasattr(self.track, "get_gradient"):
            try:
                return float(self.track.get_gradient(self.state.position))
            except (TypeError, ValueError):
                return 0.0
        return 0.0

    def _maybe_generate_stop_result(self):
        if self.stop_target != self.last_stop_result_target_m:
            self.last_stop_result_target_m = self.stop_target
            self.stop_result_published_for_target = False
            self.last_stop_result = None

        if self.stop_target is None or self.stop_result_published_for_target:
            return

        if (
            self.state.speed_ms <= self.train_ato_controller.HOLD_SPEED_MS
            and abs(self.state.position - self.stop_target) <= 2.0
        ):
            self.last_stop_result = self.train_ato_controller.evaluate_stop_result(
                vehicle_id=self.state.vehicle_id,
                target_position_m=self.stop_target,
                actual_position_m=self.state.position,
                speed_ms=self.state.speed_ms,
            )
            self.stop_result_published_for_target = True

    def _stop_result_to_dict(self):
        if self.last_stop_result is None:
            return None
        result = self.last_stop_result
        return {
            "type": "stop_result",
            "vehicle_id": result.vehicle_id,
            "target_position": result.target_position_m,
            "target_position_m": result.target_position_m,
            "actual_position": result.actual_position_m,
            "actual_position_m": result.actual_position_m,
            "error_m": result.error_m,
            "error_cm": result.error_cm,
            "qualified": result.qualified,
            "status": result.status,
            "speed_ms": result.speed_ms,
            "speed_mps": result.speed_ms,
        }

    def _sync_control_state_to_train_state(self):
        self.state.driving_mode = self.driving_mode
        self.state.ato_state = self.ato_state
        self.state.recommended_speed = self.recommended_speed
        self.state.ato_target_speed = self.ato_target_speed
        self.state.ato_traction_level = self.ato_traction_level
        self.state.ato_brake_level = self.ato_brake_level
        self.state.commanded_traction_level = self.commanded_traction_level
        self.state.commanded_brake_level = self.commanded_brake_level
        self.state.applied_traction_level = self.applied_traction_level
        self.state.applied_brake_level = self.applied_brake_level
        self.state.control_source = self.control_source
        self.state.atp_intervened = self.atp_intervened
        self.state.stop_target = self.stop_target
        self.state.distance_to_stop = self.distance_to_stop
        self.state.stop_result = self._stop_result_to_dict()

    def _update_track_position(self):
        edge_info = self.track.get_edge_info(self.state.position)
        self.state.edge_id = edge_info["edge_id"]
        self.state.section_id = edge_info["section_id"]
        self.state.edge_offset_m = edge_info["edge_offset_m"]
