from dataclasses import dataclass
from typing import Literal, Optional
import time


Mode = Literal["manual", "ato", "atp", "emergency"]


@dataclass
class TrainState:
    """Internal train state.

    Protocol units:
    - position: m
    - speed: km/h, derived from internal speed_ms
    - acceleration: m/s^2
    """

    vehicle_id: str
    line_id: str
    position: float
    speed_ms: float
    acceleration: float
    mode: Mode
    is_running: bool
    emergency_brake: bool

    @property
    def speed_kmh(self) -> float:
        return self.speed_ms * 3.6

    def to_protocol(self) -> dict:
        """Convert internal state to the train_state protocol message."""
        return {
            "type": "train_state",
            "timestamp": time.time(),
            "vehicle_id": self.vehicle_id,
            "line_id": self.line_id,
            "position": round(self.position, 3),
            "speed": round(self.speed_kmh, 3),
            "acceleration": round(self.acceleration, 3),
            "mode": self.mode,
            "is_running": self.is_running,
            "emergency_brake": self.emergency_brake,
        }


@dataclass
class DriverInput:
    vehicle_id: str
    line_id: str
    source: str
    control_mode: str
    traction_level: int
    brake_level: int
    direction: str
    emergency_button: bool


@dataclass
class AtoCommand:
    vehicle_id: str
    line_id: str
    control_mode: str
    target_speed: float
    target_position: Optional[float]
    traction_level: int
    brake_level: int
    reason: str


@dataclass
class MaLimit:
    vehicle_id: str
    ma_limit: float
    target_speed: Optional[float]
    reason: str


@dataclass
class PowerState:
    substation_id: str
    voltage: float
    current: float
    power: float
    is_fault: bool


@dataclass
class CommState:
    source: str
    driver_console_connected: bool
    zmq_connected: bool
    last_message_at: float


@dataclass
class TrackSection:
    section_id: str
    start: float
    end: float
    gradient: float
    speed_limit: float
    station_id: Optional[str]
    stop_position: Optional[float]
