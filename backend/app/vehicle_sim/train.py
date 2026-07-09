from .adapters.command_mapping import command_percent_to_levels
from .adapters.id_mapping import vehicle_id_to_index
from .atp import AtpConfig, evaluate_atp
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
        self.last_alarm = None
        self.last_atp_decision = None
        self.last_atp_alarm_reason = None
        self.atp_triggered = False
        self.current_traction_level = 0
        self.current_brake_level = 0
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
        self.current_traction_level = traction_level
        self.current_brake_level = brake_level
        if driver_input.direction_code is not None:
            self.state.direction_code = -1 if driver_input.direction_code == 2 else 1

        if driver_input.emergency_button:
            self.state.emergency_brake = True
            self.state.mode = "emergency"
        elif not self.state.emergency_brake:
            self.state.mode = "manual"

        self._step(traction_level, brake_level, dt)

    def step_ato(self, ato_command: AtoCommand, dt: float):
        if ato_command.vehicle_id != self.state.vehicle_id:
            return

        traction_level, brake_level = self._resolve_command_levels(
            ato_command.traction_level,
            ato_command.brake_level,
            ato_command.command,
            ato_command.percent,
        )
        self.current_traction_level = traction_level
        self.current_brake_level = brake_level

        if not self.state.emergency_brake:
            self.state.mode = "ato"

        self._step(traction_level, brake_level, dt)

    def step_tick(self, dt: float):
        traction_level = self.current_traction_level
        brake_level = self.current_brake_level

        if self.fallback_ato is not None and not self.state.emergency_brake:
            traction_level, brake_level, _ = self.fallback_ato.compute(
                position=self.state.position,
                speed_kmh=self.state.speed_kmh,
            )
            self.state.mode = "ato"
            self.current_traction_level = traction_level
            self.current_brake_level = brake_level

        self._step(traction_level, brake_level, dt)

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

    def _update_track_position(self):
        edge_info = self.track.get_edge_info(self.state.position)
        self.state.edge_id = edge_info["edge_id"]
        self.state.section_id = edge_info["section_id"]
        self.state.edge_offset_m = edge_info["edge_offset_m"]
