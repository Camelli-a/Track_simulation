import math
import time

from .adapters.command_mapping import command_percent_to_levels
from .adapters.id_mapping import vehicle_id_to_index
from .adapters.driver_plc_mapping import (
    service_brake_level_to_percent,
    traction_level_to_percent,
)
from .atp import (
    DRIVER_EMERGENCY_TIMEOUT_SEC,
    DRIVER_WARNING_TIMEOUT_SEC,
    AtpConfig,
    evaluate_atp,
)
from .controllers.train_ato_controller import AtoControlInput, TrainAtoController
from .dynamics import update_dynamics
from .door_state import DoorState, normalize_door_mode, sides_for_mode
from .ma_validation import MaValidationResult, effective_allowed_speed, validate_ma
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
            route_id="R_MAIN",
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
        self.external_speed_limit_kmh = None
        self.speed_constraint_reason = None
        self.speed_constraint_updated_at = None
        self.permission = None
        self.signal_state = None
        self.ma_updated_at = None
        self.ma_timeout_sec = 1.6
        self.power_fault = False
        self.power_factor = 1.0
        self.comm_ok = True
        self.last_comm_message_at = None
        self.comm_warning_timeout_sec = DRIVER_WARNING_TIMEOUT_SEC
        self.comm_timeout_sec = DRIVER_EMERGENCY_TIMEOUT_SEC
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
        self.ato_brake_bias_enabled = True
        self.ato_brake_bias = TrainAtoController.DEFAULT_BRAKE_BIAS
        self.ato_brake_bias_adaptation_enabled = True
        self.ato_brake_bias_learning_rate = 0.04
        self.ato_brake_bias_deadband_m = 0.20
        self.ato_brake_bias_max_step_per_stop = 0.05
        self.ato_brake_bias_min_samples = 1
        self.ato_brake_bias_history_size = 10
        self.ato_brake_bias_history = []
        self.ato_brake_bias_adapted_targets = set()
        self.last_brake_bias_adjustment = None
        self.sim_time_s = 0.0
        self.curve_output_enabled = True
        self.curve_history_enabled = True
        self.curve_history_size = 300
        self.curve_history = []
        self.last_curve_point = None
        self.current_traction_level = 0
        self.current_brake_level = 0
        self.cached_traction_level = 0
        self.cached_brake_level = 0
        self.cached_external_ato_command = None
        self.raw_brake_level = None
        self.fast_brake = False
        self.requested_traction_level = 0
        self.requested_brake_level = 0
        self.requested_traction_percent = 0.0
        self.requested_brake_percent = 0.0
        self.current_traction_percent = 0.0
        self.current_brake_percent = 0.0
        self.driving_mode = "SM"
        self.control_source = "manual"
        self.emergency_source = None
        self.atp_intervened = False
        self.emergency_pending = False
        self.commanded_traction_level = 0
        self.commanded_brake_level = 0
        self.applied_traction_level = 0
        self.applied_brake_level = 0
        self.ato_traction_level = 0
        self.ato_brake_level = 0
        self.ato_state = "manual_recommend"
        self.ato_target_speed_kmh = 0.0
        self.stop_target_m = None
        self.distance_to_stop_m = None
        self.last_stop_result = None
        self.last_stop_result_target_m = None
        self.stop_result_published_for_target = False
        self.manual_emergency_requested = False
        self.key_switch_active = True
        self.ato_start_requested = False
        self.ato_capable = False
        self.hardware_ato_active = False
        self.auto_reverse_capable = False
        self.auto_reverse_active = False
        self.auto_reverse_requested = False
        self.mode_up_confirmed = False
        self.mode_down_confirmed = False
        self.vigilance_active = False
        self.vigilance_release_allowed = False
        self.forced_release_requested = False
        self.forced_pump_requested = False
        self.horn_requested = False
        self.confirm_requested = False
        self.traction_aux_reset_requested = False
        self.wash_mode_switch_active = False
        self._previous_transient_inputs: dict[str, bool] = {}
        self._last_driver_frame_token: tuple[str, object] | None = None
        self.parking_brake_applied = False
        self.parking_release_requested = False
        self.brake_fault = False
        self.active_faults: set[str] = set()
        self.critical_faults: set[str] = set()
        self.external_emergency_fault = False
        self.hardware_high_voltage_light = None
        self.hardware_brake_bad_light = None
        self.hardware_network_fault_light = None
        self.door_state = DoorState()
        self.hardware_door_closed_light = None
        self.open_left_door_requested = False
        self.open_right_door_requested = False
        self.close_left_door_requested = False
        self.close_right_door_requested = False
        self.door_dwell_sec = 5.0
        self.door_stop_speed_ms = 0.05
        self.door_stop_tolerance_m = self.train_ato_controller.HOLD_DISTANCE_M
        self.door_rearm_distance_m = 2.0
        self.fallback_ato = None
        self.next_stop_target_m = None
        self.completed_stop_target_keys: set[float] = set()
        self.recommended_speed_kmh = None
        self.recommended_speed = 0.0
        self._sync_door_state()
        self._sync_indicator_outputs()
        self._sync_public_state()

    def configure_virtual_ato(self) -> None:
        """Prepare a non-hardware train for autonomous demo operation."""
        self.state.direction_code = 1
        self.key_switch_active = True
        self.manual_emergency_requested = False
        self.emergency_pending = False
        self.parking_brake_applied = False
        self.parking_release_requested = True
        self.requested_traction_level = 0
        self.requested_brake_level = 0
        self.cached_traction_level = 0
        self.cached_brake_level = 0
        self.requested_traction_percent = 0.0
        self.requested_brake_percent = 0.0
        self.current_traction_level = 0
        self.current_brake_level = 0
        self.current_traction_percent = 0.0
        self.current_brake_percent = 0.0
        self.ato_capable = True
        self.ato_start_requested = True
        self.hardware_ato_active = True
        self.driving_mode = "AM"
        self.control_source = "ato"
        if not self.state.emergency_brake:
            self.state.mode = "ato"
        self._sync_door_state()
        self._sync_public_state()

    def apply_ma_state(self, ma_limit: MaLimit):
        if ma_limit.vehicle_id == self.state.vehicle_id:
            self.ma_limit = ma_limit.ma_limit
            self.allowed_speed_kmh = ma_limit.allowed_speed_kmh
            self.eb_trigger_speed_kmh = ma_limit.eb_trigger_speed_kmh
            self.target_speed_kmh = ma_limit.target_speed
            self.target_distance_m = ma_limit.target_distance_m
            self.permission = ma_limit.permission
            self.signal_state = ma_limit.signal_state
            self.ma_updated_at = (
                time.time() if ma_limit.updated_at is None else ma_limit.updated_at
            )

    def set_next_stop_target_m(self, stop_target_m: float | None) -> None:
        """Accept a stop target unless this train has already served it."""
        key = self._stop_target_key(stop_target_m)
        if key is None:
            self.next_stop_target_m = None
            return
        if key in self.completed_stop_target_keys:
            return
        self.next_stop_target_m = float(stop_target_m)

    def _stop_target_key(self, stop_target_m: float | None) -> float | None:
        try:
            target = float(stop_target_m)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(target):
            return None
        return round(target, 2)

    def _is_completed_stop_target(self, stop_target_m: float | None) -> bool:
        key = self._stop_target_key(stop_target_m)
        return key is not None and key in self.completed_stop_target_keys

    def _track_stop_positions(self) -> list[float]:
        stops: list[float] = []
        seen: set[float] = set()
        for section in getattr(self.track, "sections", []):
            if not getattr(section, "station_id", None):
                continue
            key = self._stop_target_key(getattr(section, "stop_position", None))
            if key is None or key in seen:
                continue
            seen.add(key)
            stops.append(float(getattr(section, "stop_position")))
        return stops

    def _station_stop_position_at(self, position_m: float) -> float | None:
        if hasattr(self.track, "get_section"):
            section = self.track.get_section(float(position_m))
            if not getattr(section, "station_id", None):
                return None
            return getattr(section, "stop_position", None)
        if hasattr(self.track, "get_stop_position"):
            return self.track.get_stop_position(float(position_m))
        return None

    def _find_next_track_stop_m(self, position_m: float | None = None) -> float | None:
        position = self.state.position if position_m is None else float(position_m)
        direction_sign = -1 if int(self.state.direction_code) < 0 else 1
        margin = max(0.0, self.door_stop_tolerance_m)
        stops = [
            stop
            for stop in self._track_stop_positions()
            if not self._is_completed_stop_target(stop)
        ]
        if direction_sign < 0:
            candidates = [stop for stop in stops if stop < position - margin]
            return max(candidates) if candidates else None
        candidates = [stop for stop in stops if stop > position + margin]
        return min(candidates) if candidates else None

    def _complete_station_stop(self, stop_target_m: float | None) -> None:
        key = self._stop_target_key(stop_target_m)
        if key is None:
            return
        self.completed_stop_target_keys.add(key)
        if self._stop_target_key(self.next_stop_target_m) == key:
            self.next_stop_target_m = None
        next_target = self._find_next_track_stop_m(self.state.position)
        if next_target is not None:
            self.next_stop_target_m = next_target

    def validate_ma(self, now: float | None = None) -> MaValidationResult:
        """Return one normalized fail-safe view of the cached MA snapshot."""
        current_time = time.time() if now is None else float(now)
        return validate_ma(
            position_m=self.state.position,
            ma_limit_m=self.ma_limit,
            allowed_speed_kmh=self.allowed_speed_kmh,
            target_distance_m=self.target_distance_m,
            permission=self.permission,
            signal_state=self.signal_state,
            updated_at=self.ma_updated_at,
            now=current_time,
            timeout_sec=self.ma_timeout_sec,
            direction_code=self.state.direction_code,
            communication_ok=self.comm_ok,
        )

    def has_valid_ma(self, now: float | None = None) -> bool:
        return self.validate_ma(now).valid

    def get_distance_to_ma_m(self, now: float | None = None) -> float | None:
        result = self.validate_ma(now)
        return result.distance_to_ma_m if result.valid else None

    def get_effective_speed_limit_kmh(self, now: float | None = None) -> float:
        result = self.validate_ma(now)
        if not result.valid or result.allowed_speed_kmh is None:
            return 0.0
        external_limit = self._effective_external_allowed_speed()
        return effective_allowed_speed(
            result.allowed_speed_kmh if external_limit is None else external_limit,
            self.track.get_speed_limit(self.state.position),
        )

    def apply_power_state(self, power: PowerState):
        self.power_fault = power.is_fault or power.voltage < 1000.0
        self.power_factor = 0.0 if self.power_fault else 1.0
        self._sync_indicator_outputs()

    def apply_comm_state(self, comm: CommState):
        self.comm_ok = comm.driver_console_connected and comm.zmq_connected
        self.last_comm_message_at = comm.last_message_at
        self._sync_indicator_outputs()

    def apply_speed_constraint(
        self,
        speed_limit_kmh: float,
        *,
        reason: str = "external_constraint",
        updated_at: float | None = None,
    ) -> None:
        limit = float(speed_limit_kmh)
        if limit < 0.0:
            raise ValueError("speed constraint must be non-negative")
        self.external_speed_limit_kmh = limit
        self.speed_constraint_reason = reason
        self.speed_constraint_updated_at = time.time() if updated_at is None else updated_at

    def apply_signal_state(
        self,
        *,
        signal_state: str | None = None,
        permission: str | None = None,
    ) -> None:
        if signal_state is not None:
            self.signal_state = str(signal_state).lower()
        if permission is not None:
            self.permission = str(permission).lower()

    def apply_fault_event(
        self,
        fault_type: str,
        *,
        active: bool,
        severity: str = "warning",
    ) -> None:
        normalized_type = str(fault_type).strip().lower()
        if not normalized_type:
            raise ValueError("fault_type must not be empty")
        if active:
            self.active_faults.add(normalized_type)
        else:
            self.active_faults.discard(normalized_type)
        if active and str(severity).lower() in {"critical", "emergency"}:
            self.critical_faults.add(normalized_type)
        elif not active:
            self.critical_faults.discard(normalized_type)
        if normalized_type in {"power_fault", "high_voltage_fault"}:
            self.power_fault = active
            self.power_factor = 0.0 if active else 1.0
        if normalized_type in {"brake_fault", "brake_unavailable"}:
            self.brake_fault = active
        emergency_types = {"brake_fault", "brake_unavailable", "derailment", "fire"}
        self.external_emergency_fault = any(
            item in emergency_types for item in self.active_faults
        ) or bool(self.critical_faults)
        self._sync_indicator_outputs()

    def step_manual(self, driver_input: DriverInput, dt: float):
        """Cache a driver request; ``step_tick`` performs the only integration."""
        if driver_input.vehicle_id != self.state.vehicle_id:
            return

        frame_token = None
        if driver_input.message_id is not None:
            frame_token = ("message_id", driver_input.message_id)
        elif driver_input.frame_seq is not None:
            frame_token = ("frame_seq", driver_input.frame_seq)
        if frame_token is not None and frame_token == self._last_driver_frame_token:
            return
        if frame_token is not None:
            self._last_driver_frame_token = frame_token

        traction_level = max(0, min(int(driver_input.traction_level), 4))
        brake_level = max(0, min(int(driver_input.brake_level), 7))
        self.raw_brake_level = driver_input.raw_brake_level
        self.fast_brake = bool(driver_input.fast_brake or driver_input.main_handle_raw == 4)
        if self.fast_brake:
            traction_level = 0
            brake_level = 4
        traction_percent = (
            traction_level_to_percent(traction_level)
            if driver_input.traction_percent is None
            else max(0.0, min(float(driver_input.traction_percent), 100.0))
        )
        brake_percent = (
            traction_level_to_percent(brake_level)
            if self.fast_brake
            else service_brake_level_to_percent(brake_level)
            if driver_input.brake_percent is None
            else max(0.0, min(float(driver_input.brake_percent), 100.0))
        )
        if brake_percent > 0.0:
            traction_level = 0
            traction_percent = 0.0
        self.requested_traction_level = traction_level
        self.requested_brake_level = brake_level
        self.cached_traction_level = traction_level
        self.cached_brake_level = brake_level
        self.requested_traction_percent = traction_percent
        self.requested_brake_percent = brake_percent
        if self.fast_brake:
            self.current_traction_level = traction_level
            self.current_brake_level = brake_level
            self.current_traction_percent = traction_percent
            self.current_brake_percent = brake_percent
        if (driver_input.control_mode or "").lower() == "ato":
            self.driving_mode = "AM"
        else:
            self.driving_mode = "SM"
        self.control_source = "manual"
        if driver_input.direction_code is not None:
            self.state.direction_code = -1 if driver_input.direction_code == 2 else 1
        elif driver_input.direction in {"reverse", "backward"}:
            self.state.direction_code = -1
        elif driver_input.direction == "forward":
            self.state.direction_code = 1
        else:
            self.state.direction_code = 0

        self.manual_emergency_requested = bool(
            driver_input.emergency_button or driver_input.emergency_cmd
        )
        if self.manual_emergency_requested:
            self.emergency_pending = True
        if driver_input.key_switch is not None:
            self.key_switch_active = bool(driver_input.key_switch)
        self.ato_start_requested = self._rising_edge(
            "ato_start_btn", driver_input.ato_start_btn
        )
        if driver_input.ato_capable is not None:
            self.ato_capable = bool(driver_input.ato_capable)
        if driver_input.ato_active is not None:
            self.hardware_ato_active = bool(driver_input.ato_active)
        if driver_input.auto_reverse_cap is not None:
            self.auto_reverse_capable = bool(driver_input.auto_reverse_cap)
        if driver_input.auto_reverse_active is not None:
            self.auto_reverse_active = bool(driver_input.auto_reverse_active)
        self.auto_reverse_requested = self._rising_edge(
            "auto_rev_flag", driver_input.auto_rev_flag
        )
        self.mode_up_confirmed = self._rising_edge(
            "mode_up_confirm", driver_input.mode_up_confirm
        )
        self.mode_down_confirmed = self._rising_edge(
            "mode_dn_confirm", driver_input.mode_dn_confirm
        )
        self.vigilance_active = self._rising_edge("vigilance", driver_input.vigilance)
        self.vigilance_release_allowed = bool(driver_input.vigilance_allow)
        self.forced_release_requested = self._rising_edge(
            "forced_release", driver_input.forced_release
        )
        self.forced_pump_requested = self._rising_edge(
            "forced_pump", driver_input.forced_pump
        )
        self.horn_requested = self._rising_edge("horn", driver_input.horn)
        self.confirm_requested = self._rising_edge(
            "confirm_flag", driver_input.confirm_flag
        )
        self.traction_aux_reset_requested = self._rising_edge(
            "trac_aux_reset", driver_input.trac_aux_reset
        )
        self.wash_mode_switch_active = bool(driver_input.wash_mode_switch)
        parking_apply_pressed = self._rising_edge(
            "parking_apply", driver_input.parking_apply
        )
        if parking_apply_pressed:
            self.parking_brake_applied = True
        self.parking_release_requested = self._rising_edge(
            "parking_release", driver_input.parking_release
        )
        if (
            self.parking_release_requested
            and self.state.speed_ms <= 0.05
            and not self.state.emergency_brake
        ):
            self.parking_brake_applied = False
        if driver_input.brake_bad_light is not None:
            self.hardware_brake_bad_light = bool(driver_input.brake_bad_light)
        if driver_input.network_fault_light is not None:
            self.hardware_network_fault_light = bool(driver_input.network_fault_light)
        self.open_left_door_requested = self._rising_edge(
            "open_left_door", driver_input.open_left_door
        )
        self.open_right_door_requested = self._rising_edge(
            "open_right_door", driver_input.open_right_door
        )
        self.close_left_door_requested = self._rising_edge(
            "close_left_door", driver_input.close_left_door
        )
        self.close_right_door_requested = self._rising_edge(
            "close_right_door", driver_input.close_right_door
        )
        if driver_input.door_mode is not None:
            self.door_state.mode = normalize_door_mode(driver_input.door_mode)
        if driver_input.door_closed_light is not None:
            self.hardware_door_closed_light = bool(driver_input.door_closed_light)
        if driver_input.high_voltage_light is not None:
            self.hardware_high_voltage_light = bool(driver_input.high_voltage_light)

    def step_ato(self, ato_command: AtoCommand, dt: float):
        """Cache a legacy/external ATO request without integrating dynamics."""
        if ato_command.vehicle_id != self.state.vehicle_id:
            return

        traction_level, brake_level = self._resolve_command_levels(
            ato_command.traction_level,
            ato_command.brake_level,
            ato_command.command,
            ato_command.percent,
        )
        traction_level = max(0, min(int(traction_level), 4))
        brake_level = max(0, min(int(brake_level), 4))
        if brake_level > 0:
            traction_level = 0
        self.requested_traction_level = traction_level
        self.requested_brake_level = brake_level
        self.cached_external_ato_command = ato_command
        self.cached_traction_level = traction_level
        self.cached_brake_level = brake_level
        self.requested_traction_percent = traction_level_to_percent(traction_level)
        self.requested_brake_percent = traction_level_to_percent(brake_level)
        self.driving_mode = "AM"
        self.control_source = "ato"

    def step_tick(self, dt: float):
        self._update_doors(dt)
        self._sync_indicator_outputs()
        self._update_ato_recommendation(dt)
        traction_level = self.requested_traction_level
        brake_level = self.requested_brake_level
        traction_percent = self.requested_traction_percent
        brake_percent = self.requested_brake_percent
        selected_source = "ato" if self.driving_mode == "AM" else "manual"
        self.atp_intervened = False

        if self.driving_mode != "AM":
            if (
                self.cached_traction_level != self.requested_traction_level
                or self.cached_brake_level != self.requested_brake_level
            ):
                traction_level = self.cached_traction_level
                brake_level = self.cached_brake_level
                traction_percent = traction_level_to_percent(traction_level)
                brake_percent = service_brake_level_to_percent(brake_level)

        if self.fallback_ato is not None and not self.state.emergency_brake:
            traction_level, brake_level, _ = self.fallback_ato.compute(
                position=self.state.position,
                speed_kmh=self.state.speed_kmh,
            )
            self.driving_mode = "AM"
            selected_source = "fallback"
            traction_percent = traction_level_to_percent(traction_level)
            brake_percent = traction_level_to_percent(brake_level)

        if (
            self.driving_mode == "AM"
            and self.last_ato_output is not None
            and self.fallback_ato is None
            and self.cached_external_ato_command is None
        ):
            traction_level = self.last_ato_output.commanded_traction_level
            brake_level = self.last_ato_output.commanded_brake_level
            traction_percent = traction_level_to_percent(traction_level)
            brake_percent = traction_level_to_percent(brake_level)
            selected_source = self.last_ato_output.control_source or "ato"
            if self.last_ato_output.degraded:
                traction_level = 0
                traction_percent = 0.0
                brake_level = max(brake_level, 2)
                brake_percent = max(brake_percent, traction_level_to_percent(brake_level))
                selected_source = "degraded"

        if self.driving_mode == "AM" and not self.has_valid_ma():
            traction_level = 0
            traction_percent = 0.0

        if not self.key_switch_active or self.state.direction_code == 0:
            traction_level = 0
            traction_percent = 0.0

        if not self.door_state.all_closed:
            traction_level = 0
            traction_percent = 0.0
            selected_source = "door_interlock"

        if self.parking_brake_applied:
            traction_level = 0
            traction_percent = 0.0
            brake_level = 7
            brake_percent = 100.0
            selected_source = "parking_brake"

        if brake_percent > 0.0 or brake_level > 0:
            traction_level = 0
            traction_percent = 0.0

        if self.external_emergency_fault:
            traction_level = 0
            brake_level = 4
            traction_percent = 0.0
            brake_percent = 100.0
            self.state.emergency_brake = True
            self.state.mode = "emergency"
            selected_source = "fault_event"
            self.emergency_source = "fault_event"
        elif self.manual_emergency_requested:
            traction_level = 0
            brake_level = 4
            traction_percent = 0.0
            brake_percent = 100.0
            self.state.emergency_brake = True
            self.state.mode = "emergency"
            selected_source = "emergency_button"
            self.emergency_source = "emergency_button"
        elif self._can_release_am_atp_emergency():
            self.state.emergency_brake = False
            self.emergency_source = None
            self.atp_intervened = False
            self.state.mode = "ato"
            selected_source = "ato"
        elif self.state.emergency_brake:
            traction_level = 0
            brake_level = 4
            traction_percent = 0.0
            brake_percent = 100.0
            selected_source = (
                "emergency"
                if self.emergency_source in {None, "atp"}
                else self.emergency_source
            )
            self.atp_intervened = self.emergency_source == "atp"
            self.state.mode = "emergency"
        elif not self.state.emergency_brake:
            self.state.mode = "ato" if self.driving_mode == "AM" else "manual"

        self.current_traction_level = traction_level
        self.current_brake_level = brake_level
        if self.driving_mode != "AM":
            self.cached_traction_level = traction_level
            self.cached_brake_level = brake_level
        self.current_traction_percent = traction_percent
        self.current_brake_percent = brake_percent
        self.control_source = selected_source
        self.commanded_traction_level = traction_level
        self.commanded_brake_level = brake_level

        self._step(traction_level, brake_level, dt)
        self.distance_to_stop_m = (
            None
            if self.stop_target_m is None
            else self._signed_distance_m(self.stop_target_m)
        )
        self._maybe_generate_stop_result()
        self._maybe_adapt_brake_bias_from_stop_result()
        self.sim_time_s += max(0.0, float(dt))
        self._update_curve_output()
        self._sync_control_state_to_train_state()
        self._sync_public_state()
        self._clear_transient_events()

    def _can_release_am_atp_emergency(self) -> bool:
        if not self.state.emergency_brake:
            return False
        if self.driving_mode != "AM":
            return False
        if self.emergency_source not in {None, "atp"}:
            return False
        if self.external_emergency_fault or self.manual_emergency_requested:
            return False
        if self.state.speed_ms > max(self.door_stop_speed_ms, 0.2):
            return False
        ma_result = self.validate_ma()
        return ma_result.valid and ma_result.traction_permitted

    def _update_ato_recommendation(self, dt: float) -> None:
        stop_target_m = self._resolve_stop_target_m()
        ma_result = self.validate_ma()
        ato_input = AtoControlInput(
            vehicle_id=self.state.vehicle_id,
            position_m=self.state.position,
            speed_ms=self.state.speed_ms,
            ma_limit_m=self.ma_limit,
            allowed_speed_kmh=self._effective_external_allowed_speed(),
            stop_target_m=stop_target_m,
            target_distance_m=self.target_distance_m,
            permission=self.permission,
            signal_state=self.signal_state,
            driving_mode=self.driving_mode,
            direction=self.state.direction_code,
            ma_valid=ma_result.valid,
            ma_age_sec=ma_result.age_sec,
            max_ma_age_sec=self.ma_timeout_sec,
            comm_ok=self.comm_ok,
            dt=dt,
            acceleration_ms2=self.state.acceleration,
            control_delay_sec=self.ato_control_delay_sec,
            delay_compensation_enabled=self.ato_delay_compensation_enabled,
            gradient_permille=self.track.get_gradient(self.state.position),
            gradient_compensation_enabled=self.ato_gradient_compensation_enabled,
            previous_commanded_traction_level=self.commanded_traction_level,
            previous_commanded_brake_level=min(self.commanded_brake_level, 4),
            jerk_limit_enabled=self.ato_jerk_limit_enabled,
            brake_bias=self.ato_brake_bias,
            brake_bias_enabled=self.ato_brake_bias_enabled,
        )
        ato_output = self.train_ato_controller.compute_control(ato_input)
        self.last_ato_output = ato_output
        self.ato_traction_level = ato_output.ato_traction_level
        self.ato_brake_level = ato_output.ato_brake_level
        self.ato_state = ato_output.ato_state
        self.recommended_speed_kmh = ato_output.recommended_speed_kmh
        self.recommended_speed = ato_output.recommended_speed_kmh
        self.ato_target_speed_kmh = ato_output.ato_target_speed_kmh
        self.stop_target_m = stop_target_m
        self.distance_to_stop_m = ato_output.distance_to_stop_m

    def _rising_edge(self, name: str, current: bool) -> bool:
        current_value = bool(current)
        previous_value = self._previous_transient_inputs.get(name, False)
        self._previous_transient_inputs[name] = current_value
        return current_value and not previous_value

    def _clear_transient_events(self) -> None:
        self.ato_start_requested = False
        self.auto_reverse_requested = False
        self.mode_up_confirmed = False
        self.mode_down_confirmed = False
        self.vigilance_active = False
        self.forced_release_requested = False
        self.forced_pump_requested = False
        self.horn_requested = False
        self.confirm_requested = False
        self.traction_aux_reset_requested = False
        self.parking_release_requested = False

    def _update_doors(self, dt: float) -> None:
        """Apply door requests and automatic station dwell without integrating motion."""
        stopped = self.state.speed_ms <= self.door_stop_speed_ms
        stop_target_m = self._resolve_stop_target_m()
        at_stop_target = (
            stop_target_m is not None
            and abs(self.state.position - stop_target_m) <= self.door_stop_tolerance_m
        )

        if (
            self.door_state.last_auto_target_m is not None
            and abs(self.state.position - self.door_state.last_auto_target_m)
            > self.door_rearm_distance_m
        ):
            self.door_state.last_auto_target_m = None

        close_requested = self.close_left_door_requested or self.close_right_door_requested
        open_requested = self.open_left_door_requested or self.open_right_door_requested
        if close_requested:
            if self.close_left_door_requested:
                self.door_state.left_open = False
            if self.close_right_door_requested:
                self.door_state.right_open = False
            if self.door_state.all_closed:
                self.door_state.dwell_remaining_s = 0.0
        elif open_requested and stopped:
            self.door_state.open(
                left=self.open_left_door_requested,
                right=self.open_right_door_requested,
                dwell_s=self.door_dwell_sec,
            )
        elif (
            self.door_state.all_closed
            and stopped
            and at_stop_target
            and self.door_state.last_auto_target_m != stop_target_m
        ):
            left, right = sides_for_mode(self.door_state.mode)
            self.door_state.open(left=left, right=right, dwell_s=self.door_dwell_sec)
            self.door_state.last_auto_target_m = stop_target_m
        else:
            closed_after_dwell = self.door_state.tick(dt)
            if closed_after_dwell:
                self._complete_station_stop(self.door_state.last_auto_target_m)

        self.open_left_door_requested = False
        self.open_right_door_requested = False
        self.close_left_door_requested = False
        self.close_right_door_requested = False
        self._sync_door_state()

    def _sync_door_state(self) -> None:
        self.state.door_state = self.door_state.state
        self.state.left_door_open = self.door_state.left_open
        self.state.right_door_open = self.door_state.right_open
        self.state.doors_all_closed = self.door_state.all_closed
        self.state.door_mode = self.door_state.mode
        self.state.door_closed_light = self.door_state.all_closed

    def _sync_indicator_outputs(self) -> None:
        """Derive commanded lamps from business state, never from PLC feedback."""
        self.state.high_voltage_light = not self.power_fault
        self.state.brake_bad_light = bool(self.brake_fault)
        self.state.door_closed_light = self.door_state.all_closed

    def _sync_public_state(self) -> None:
        """Copy authoritative runtime values into the published train snapshot."""
        self.state.traction_level = self.current_traction_level
        self.state.brake_level = self.current_brake_level
        self.state.traction_percent = self.current_traction_percent
        self.state.brake_percent = self.current_brake_percent
        self.state.atp_intervention = self.atp_intervened
        self.state.driving_mode = self.driving_mode
        self.state.control_source = self.control_source
        self.state.ato_state = self.ato_state
        self.state.ato_target_speed_kmh = getattr(self, "ato_target_speed_kmh", None)
        self.state.ato_traction_level = self.ato_traction_level
        self.state.ato_brake_level = self.ato_brake_level
        self.state.commanded_traction_level = self.commanded_traction_level
        self.state.commanded_brake_level = self.commanded_brake_level
        self.state.applied_traction_level = self.applied_traction_level
        self.state.applied_brake_level = self.applied_brake_level
        self.state.atp_intervened = self.atp_intervened
        self.state.stop_target = getattr(self, "stop_target_m", getattr(self, "stop_target", None))
        self.state.distance_to_stop = getattr(self, "distance_to_stop_m", getattr(self, "distance_to_stop", None))
        self.state.stop_result = self._stop_result_to_dict()
        self.state.ato_brake_bias = self.ato_brake_bias
        self.state.ato_brake_bias_enabled = self.ato_brake_bias_enabled
        self.state.ato_active = (
            self.driving_mode == "AM" and self.state.mode == "ato"
        )
        self.state.ato_capable = self.ato_capable
        self.state.auto_reverse_cap = self.auto_reverse_capable
        self.state.auto_reverse_active = self.auto_reverse_active
        self.state.recommended_speed_kmh = getattr(self, "recommended_speed_kmh", None)
        self.state.recommended_speed = 0.0 if self.recommended_speed_kmh is None else self.recommended_speed_kmh
        self.state.parking_brake = self.parking_brake_applied
        self.state.external_speed_limit_kmh = self.external_speed_limit_kmh
        self.state.active_faults = tuple(sorted(self.active_faults))

    def build_atp_state(self) -> dict:
        decision = self.last_atp_decision
        return {
            "type": "atp_state",
            "timestamp": time.time(),
            "vehicle_id": self.state.vehicle_id,
            "intervened": self.atp_intervened,
            "emergency_brake": self.state.emergency_brake,
            "supervision_state": (
                "unknown" if decision is None else decision.supervision_state
            ),
            "reason": "not_evaluated" if decision is None else decision.reason,
            "allowed_speed_kmh": (
                None if decision is None else decision.allowed_speed_kmh
            ),
            "eb_trigger_speed_kmh": (
                None if decision is None else decision.eb_trigger_speed_kmh
            ),
        }

    def build_ato_state(self) -> dict:
        return {
            "type": "ato_state",
            "timestamp": time.time(),
            "vehicle_id": self.state.vehicle_id,
            "driving_mode": self.driving_mode,
            "ato_active": self.state.ato_active,
            "ato_capable": self.ato_capable,
            "ato_state": self.ato_state,
            "recommended_speed_kmh": self.recommended_speed_kmh,
            "ato_target_speed_kmh": self.ato_target_speed_kmh,
            "ato_traction_level": self.ato_traction_level,
            "ato_brake_level": self.ato_brake_level,
            "ato_brake_bias": self.ato_brake_bias,
            "ato_brake_bias_enabled": self.ato_brake_bias_enabled,
            "stop_target_m": self.stop_target_m,
            "distance_to_stop_m": self.distance_to_stop_m,
            "auto_reverse_cap": self.auto_reverse_capable,
            "auto_reverse_active": self.auto_reverse_active,
        }

    def build_door_state(self) -> dict:
        return {
            "type": "door_state",
            "timestamp": time.time(),
            "vehicle_id": self.state.vehicle_id,
            "door_state": self.door_state.state,
            "left_door_open": self.door_state.left_open,
            "right_door_open": self.door_state.right_open,
            "doors_all_closed": self.door_state.all_closed,
            "door_mode": self.door_state.mode,
        }

    def get_indicator_feedback_mismatches(self) -> dict[str, dict[str, bool]]:
        """Report lamp feedback mismatches without feeding them into control."""
        desired_and_feedback = {
            "high_voltage_light": (
                self.state.high_voltage_light,
                self.hardware_high_voltage_light,
            ),
            "brake_bad_light": (
                self.state.brake_bad_light,
                self.hardware_brake_bad_light,
            ),
            "door_closed_light": (
                self.state.door_closed_light,
                self.hardware_door_closed_light,
            ),
        }
        return {
            name: {"commanded": commanded, "feedback": feedback}
            for name, (commanded, feedback) in desired_and_feedback.items()
            if feedback is not None and commanded != feedback
        }

    def enable_fallback_ato(self, target_position: float, target_speed_kmh: float | None = None):
        from .controllers.fallback_ato import FallbackAtoController

        target_position = float(target_position)
        self.fallback_ato = FallbackAtoController(
            target_position,
            target_speed_kmh=30.0 if target_speed_kmh is None else float(target_speed_kmh),
        )
        self.next_stop_target_m = target_position
        self.stop_target_m = target_position
        self.distance_to_stop_m = self._signed_distance_m(target_position)
        if self.state.emergency_brake and self.distance_to_stop_m > 0.0:
            self.state.emergency_brake = False
            self.emergency_source = None
            self.atp_intervened = False
        if not self.state.emergency_brake:
            self.state.mode = "ato"

    def _step(self, traction_level: int, brake_level: int, dt: float):
        speed_limit = self.track.get_speed_limit(self.state.position)
        allowed_speed_kmh = self._effective_external_allowed_speed()
        eb_trigger_speed_kmh = self.eb_trigger_speed_kmh
        if self.signal_state == "red" or self.permission in {"stop", "deny", "blocked"}:
            allowed_speed_kmh = 0.0
            eb_trigger_speed_kmh = 0.0
        atp_decision = evaluate_atp(
            self.state,
            speed_limit=speed_limit,
            ma_limit=self.ma_limit,
            allowed_speed_kmh=allowed_speed_kmh,
            eb_trigger_speed_kmh=eb_trigger_speed_kmh,
            target_distance_m=self.target_distance_m,
            power_fault=self.power_fault,
            comm_ok=self.comm_ok,
            last_message_at=self.last_comm_message_at,
            gradient_permille=self.track.get_gradient(self.state.position),
            config=AtpConfig(
                comm_warning_timeout_sec=self.comm_warning_timeout_sec,
                comm_timeout_sec=self.comm_timeout_sec,
            ),
        )
        self.last_atp_decision = atp_decision

        if atp_decision.alarm is not None and not atp_decision.emergency_brake:
            if self.last_atp_alarm_reason != atp_decision.reason:
                self.last_alarm = atp_decision.alarm
                self.last_atp_alarm_reason = atp_decision.reason

        if atp_decision.emergency_brake:
            was_emergency = self.state.emergency_brake
            self.state.emergency_brake = True
            self.state.mode = "emergency"
            if not was_emergency and not self.atp_triggered:
                self.last_alarm = atp_decision.alarm
                self.atp_triggered = True
                self.last_atp_alarm_reason = atp_decision.reason
            traction_level = 0
            brake_level = 4
            self.current_traction_level = traction_level
            self.current_brake_level = brake_level
            self.current_traction_percent = 0.0
            self.current_brake_percent = 100.0
            self.applied_traction_level = traction_level
            self.applied_brake_level = brake_level
            self.control_source = "emergency"
            self.emergency_source = "atp"
            self.atp_intervened = True
        else:
            self.applied_traction_level = traction_level
            self.applied_brake_level = brake_level

        gradient = self.track.get_gradient(self.state.position)

        new_speed, new_position, acc, traction_force, brake_force = update_dynamics(
            speed_ms=self.state.speed_ms,
            position=self.state.position,
            traction_level=traction_level,
            brake_level=brake_level,
            gradient=gradient,
            dt=dt,
            power_factor=self.power_factor,
            emergency_brake=self.state.emergency_brake,
            traction_percent=self.current_traction_percent,
            brake_percent=self.current_brake_percent,
            direction_sign=self.state.direction_code,
        )

        self.state.speed_ms = new_speed
        self.state.position = new_position
        self.state.acceleration = acc
        self.state.is_running = new_speed > 0.0
        self.state.actual_traction_force_n = traction_force
        self.state.actual_brake_force_n = brake_force
        self._sync_public_state()
        self._update_track_position()

    def _resolve_stop_target_m(self) -> float | None:
        if (
            self.next_stop_target_m is not None
            and not self._is_completed_stop_target(self.next_stop_target_m)
        ):
            return self.next_stop_target_m
        if (
            self.next_stop_target_m is not None
            and self._is_completed_stop_target(self.next_stop_target_m)
        ):
            self.next_stop_target_m = None
        stop_position = self._station_stop_position_at(self.state.position)
        if stop_position is not None:
            if (
                not self._is_completed_stop_target(stop_position)
                and abs(float(stop_position) - self.state.position)
                <= self.door_stop_tolerance_m
            ):
                return stop_position
        next_track_stop = self._find_next_track_stop_m(self.state.position)
        if next_track_stop is not None:
            self.next_stop_target_m = next_track_stop
            return next_track_stop
        stop_position = self._station_stop_position_at(self.state.position)
        if stop_position is not None and not self._is_completed_stop_target(stop_position):
            return stop_position
        return None

    def _maybe_generate_stop_result(self) -> None:
        if self.stop_target_m != self.last_stop_result_target_m:
            self.last_stop_result_target_m = self.stop_target_m
            self.stop_result_published_for_target = False
            self.last_stop_result = None

        if self.stop_target_m is None or self.stop_result_published_for_target:
            return

        distance_to_stop_m = abs(self.state.position - self.stop_target_m)
        holding_state = (
            self.last_ato_output is not None
            and self.last_ato_output.ato_state == "holding"
        )
        if (
            self.state.speed_ms <= self.train_ato_controller.HOLD_SPEED_MS
            and (
                distance_to_stop_m <= self.train_ato_controller.HOLD_DISTANCE_M
                or holding_state
            )
        ):
            self.last_stop_result = self.train_ato_controller.evaluate_stop_result(
                vehicle_id=self.state.vehicle_id,
                target_position_m=self.stop_target_m,
                actual_position_m=self.state.position,
                speed_ms=self.state.speed_ms,
            )
            self.stop_result_published_for_target = True

    def _maybe_adapt_brake_bias_from_stop_result(self) -> None:
        stop_result = self._stop_result_to_dict()
        if not self._is_stop_result_eligible_for_brake_bias_adaptation(stop_result):
            return

        target_position_m = self._stop_result_value(
            stop_result,
            "target_position_m",
            "target_position",
        )
        actual_position_m = self._stop_result_value(
            stop_result,
            "actual_position_m",
            "actual_position",
        )
        error_m = self._stop_result_value(stop_result, "error_m")
        target_key = round(target_position_m, 2)
        old_bias = self.ato_brake_bias
        delta = self._compute_brake_bias_delta_from_error(error_m)
        new_bias = self.train_ato_controller.normalize_brake_bias(
            old_bias + delta,
            enabled=True,
        )
        applied_delta = round(new_bias - old_bias, 6)
        if applied_delta == 0.0:
            self.ato_brake_bias_adapted_targets.add(target_key)
            return

        self.ato_brake_bias = new_bias
        record = {
            "vehicle_id": self.state.vehicle_id,
            "target_position_m": target_position_m,
            "actual_position_m": actual_position_m,
            "error_m": error_m,
            "old_brake_bias": round(old_bias, 6),
            "new_brake_bias": round(new_bias, 6),
            "delta": applied_delta,
            "qualified": stop_result.get("qualified"),
            "status": stop_result.get("status"),
        }
        self.ato_brake_bias_history.append(record)
        self.ato_brake_bias_history = self.ato_brake_bias_history[
            -self.ato_brake_bias_history_size :
        ]
        self.last_brake_bias_adjustment = record
        self.ato_brake_bias_adapted_targets.add(target_key)

    def _is_stop_result_eligible_for_brake_bias_adaptation(self, stop_result: dict | None) -> bool:
        if not self.ato_brake_bias_adaptation_enabled:
            return False
        if not self.ato_brake_bias_enabled:
            return False
        if self.driving_mode != "AM":
            return False
        if self.atp_intervened or self.state.emergency_brake:
            return False
        if self.last_ato_output is None or self.last_ato_output.degraded:
            return False
        if not stop_result:
            return False
        if stop_result.get("vehicle_id") != self.state.vehicle_id:
            return False

        target_position_m = self._stop_result_value(
            stop_result,
            "target_position_m",
            "target_position",
        )
        actual_position_m = self._stop_result_value(
            stop_result,
            "actual_position_m",
            "actual_position",
        )
        error_m = self._stop_result_value(stop_result, "error_m")
        speed_ms = self._stop_result_value(stop_result, "speed_mps", "speed_ms")
        if (
            target_position_m is None
            or actual_position_m is None
            or error_m is None
            or speed_ms is None
        ):
            return False
        if abs(error_m) < self.ato_brake_bias_deadband_m:
            return False
        if speed_ms > 0.3:
            return False

        target_key = round(target_position_m, 2)
        return target_key not in self.ato_brake_bias_adapted_targets

    def _compute_brake_bias_delta_from_error(self, error_m: float) -> float:
        raw_delta = float(error_m) * self.ato_brake_bias_learning_rate
        return max(
            -self.ato_brake_bias_max_step_per_stop,
            min(self.ato_brake_bias_max_step_per_stop, raw_delta),
        )

    def _stop_result_value(self, stop_result: dict, *keys):
        for key in keys:
            if key in stop_result and stop_result[key] is not None:
                try:
                    value = float(stop_result[key])
                except (TypeError, ValueError):
                    return None
                if self.train_ato_controller.is_finite_number(value):
                    return value
                return None
        return None

    def _update_curve_output(self):
        if not self.curve_output_enabled:
            self.last_curve_point = None
            return

        self.last_curve_point = self._build_curve_point()
        if self.curve_history_enabled:
            self.curve_history.append(self.last_curve_point)
            self.curve_history = self.curve_history[-self.curve_history_size :]

    def _build_curve_point(self) -> dict:
        distance_to_ma_m = None
        if self.ma_limit is not None:
            distance_to_ma_m = self._signed_distance_m(self.ma_limit)

        stop_target_m = self.stop_target_m
        if stop_target_m is None:
            stop_target_m = self.next_stop_target_m
        distance_to_stop_m = None
        if stop_target_m is not None:
            distance_to_stop_m = self._signed_distance_m(stop_target_m)

        degraded = None
        if self.last_ato_output is not None:
            degraded = self.last_ato_output.degraded

        recommended_speed_kmh = getattr(self, "recommended_speed_kmh", None)
        if recommended_speed_kmh is None:
            recommended_speed_kmh = getattr(self, "recommended_speed", None)

        legacy_ato_target_speed = getattr(self, "ato_target_speed", None)
        ato_target_speed_kmh = getattr(self, "ato_target_speed_kmh", None)
        if (
            ato_target_speed_kmh is None
            or (
                ato_target_speed_kmh == 0.0
                and legacy_ato_target_speed is not None
                and self.last_ato_output is None
            )
        ):
            ato_target_speed_kmh = legacy_ato_target_speed

        return {
            "time_s": round(self.sim_time_s, 3),
            "vehicle_id": self.state.vehicle_id,
            "line_id": self.state.line_id,
            "position_m": round(self.state.position, 3),
            "direction": self.state.protocol_direction,
            "speed_mps": round(self.state.speed_ms, 3),
            "speed_kmh": round(self.state.speed_kmh, 3),
            "acceleration_mps2": round(self.state.acceleration, 3),
            "recommended_speed_mps": (
                None if recommended_speed_kmh is None else round(float(recommended_speed_kmh) / 3.6, 3)
            ),
            "recommended_speed_kmh": self._round_optional(recommended_speed_kmh),
            "ato_target_speed_mps": (
                None if ato_target_speed_kmh is None else round(float(ato_target_speed_kmh) / 3.6, 3)
            ),
            "ato_target_speed_kmh": self._round_optional(ato_target_speed_kmh),
            "allowed_speed_kmh": self._round_optional(self.allowed_speed_kmh),
            "eb_trigger_speed_kmh": self._round_optional(self.eb_trigger_speed_kmh),
            "ma_limit_m": self._round_optional(self.ma_limit),
            "distance_to_ma_m": self._round_optional(distance_to_ma_m),
            "stop_target_m": self._round_optional(stop_target_m),
            "distance_to_stop_m": self._round_optional(distance_to_stop_m),
            "ato_brake_level": self.ato_brake_level,
            "commanded_brake_level": self.commanded_brake_level,
            "applied_brake_level": self.applied_brake_level,
            "ato_traction_level": self.ato_traction_level,
            "commanded_traction_level": self.commanded_traction_level,
            "applied_traction_level": self.applied_traction_level,
            "driving_mode": self.driving_mode,
            "control_source": self.control_source,
            "ato_state": self.ato_state,
            "atp_intervened": self.atp_intervened,
            "emergency_brake": self.state.emergency_brake,
            "degraded": degraded,
            "ato_brake_bias": round(self.ato_brake_bias, 3),
            "ato_brake_bias_enabled": self.ato_brake_bias_enabled,
            "ato_brake_bias_adaptation_enabled": (
                self.ato_brake_bias_adaptation_enabled
            ),
        }

    def _round_optional(self, value):
        if value is None:
            return None
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return None

    def _stop_result_to_dict(self) -> dict | None:
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
        recommended_speed_kmh = getattr(self, "recommended_speed_kmh", None)
        if recommended_speed_kmh is None:
            recommended_speed_kmh = getattr(self, "recommended_speed", 0.0)

        legacy_ato_target_speed = getattr(self, "ato_target_speed", None)
        ato_target_speed_kmh = getattr(self, "ato_target_speed_kmh", None)
        if (
            ato_target_speed_kmh is None
            or (
                ato_target_speed_kmh == 0.0
                and legacy_ato_target_speed is not None
                and self.last_ato_output is None
            )
        ):
            ato_target_speed_kmh = legacy_ato_target_speed
        if ato_target_speed_kmh is None:
            ato_target_speed_kmh = 0.0

        self.state.recommended_speed = recommended_speed_kmh
        self.state.recommended_speed_kmh = recommended_speed_kmh
        self.state.ato_target_speed = ato_target_speed_kmh
        self.state.ato_target_speed_kmh = ato_target_speed_kmh
        self.state.ato_traction_level = self.ato_traction_level
        self.state.ato_brake_level = self.ato_brake_level
        self.state.commanded_traction_level = self.commanded_traction_level
        self.state.commanded_brake_level = self.commanded_brake_level
        self.state.applied_traction_level = self.applied_traction_level
        self.state.applied_brake_level = self.applied_brake_level
        self.state.control_source = self.control_source
        self.state.atp_intervened = self.atp_intervened
        self.state.stop_target = getattr(self, "stop_target_m", getattr(self, "stop_target", None))
        self.state.distance_to_stop = getattr(self, "distance_to_stop_m", getattr(self, "distance_to_stop", None))
        self.state.stop_result = self._stop_result_to_dict()
        self.state.ato_brake_bias = self.ato_brake_bias
        self.state.ato_brake_bias_enabled = self.ato_brake_bias_enabled
        self.state.ato_brake_bias_adaptation_enabled = (
            self.ato_brake_bias_adaptation_enabled
        )
        self.state.last_brake_bias_adjustment = self.last_brake_bias_adjustment
        self.state.brake_bias_history_size = len(self.ato_brake_bias_history)
        self.state.curve_output_enabled = self.curve_output_enabled
        self.state.curve_history_size = self.curve_history_size
        self.state.curve_point = self.last_curve_point

    def _signed_distance_m(self, target_position_m: float) -> float:
        direction_sign = -1 if int(self.state.direction_code) < 0 else 1
        return (float(target_position_m) - float(self.state.position)) * direction_sign

    def _effective_external_allowed_speed(self) -> float | None:
        candidates = [
            value
            for value in (self.allowed_speed_kmh, self.external_speed_limit_kmh)
            if value is not None
        ]
        return min(candidates) if candidates else None

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

    def _update_track_position(self):
        edge_info = self.track.get_edge_info(self.state.position)
        self.state.edge_id = edge_info["edge_id"]
        self.state.section_id = edge_info["section_id"]
        self.state.edge_offset_m = edge_info["edge_offset_m"]
