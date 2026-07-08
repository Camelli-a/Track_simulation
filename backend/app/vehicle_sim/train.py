from .atp import check_atp
from .dynamics import update_dynamics
from .models import AtoCommand, CommState, DriverInput, MaLimit, PowerState, TrainState
from .track_map import TrackMap


class Train:
    """Single train instance with independent state and dynamics."""

    def __init__(self, vehicle_id: str, line_id: str, track: TrackMap):
        self.state = TrainState(
            vehicle_id=vehicle_id,
            line_id=line_id,
            position=0.0,
            speed_ms=0.0,
            acceleration=0.0,
            mode="manual",
            is_running=False,
            emergency_brake=False,
        )

        self.track = track
        self.ma_limit = None
        self.power_fault = False
        self.power_factor = 1.0
        self.comm_ok = True
        self.last_alarm = None

    def apply_ma_state(self, ma_limit: MaLimit):
        if ma_limit.vehicle_id == self.state.vehicle_id:
            self.ma_limit = ma_limit.ma_limit

    def apply_power_state(self, power: PowerState):
        self.power_fault = power.is_fault
        self.power_factor = 0.0 if power.is_fault else 1.0

    def apply_comm_state(self, comm: CommState):
        self.comm_ok = comm.driver_console_connected and comm.zmq_connected

    def step_manual(self, driver_input: DriverInput, dt: float):
        if driver_input.vehicle_id != self.state.vehicle_id:
            return

        traction_level = driver_input.traction_level
        brake_level = driver_input.brake_level

        if driver_input.emergency_button:
            self.state.emergency_brake = True
            self.state.mode = "emergency"
        elif not self.state.emergency_brake:
            self.state.mode = "manual"

        self._step(traction_level, brake_level, dt)

    def step_ato(self, ato_command: AtoCommand, dt: float):
        if ato_command.vehicle_id != self.state.vehicle_id:
            return

        traction_level = ato_command.traction_level
        brake_level = ato_command.brake_level

        if not self.state.emergency_brake:
            self.state.mode = "ato"

        self._step(traction_level, brake_level, dt)

    def _step(self, traction_level: int, brake_level: int, dt: float):
        speed_limit = self.track.get_speed_limit(self.state.position)
        should_brake, alarm = check_atp(
            self.state,
            speed_limit=speed_limit,
            ma_limit=self.ma_limit,
            power_fault=self.power_fault,
            comm_ok=self.comm_ok,
        )

        if should_brake:
            self.state.emergency_brake = True
            self.state.mode = "emergency"
            self.last_alarm = alarm

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
