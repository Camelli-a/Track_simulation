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
    train_index: int = 0
    edge_id: Optional[int] = None
    section_id: Optional[str] = None
    edge_offset_m: Optional[float] = None
    direction_code: int = 1

    @property
    def speed_kmh(self) -> float:
        return self.speed_ms * 3.6

    def to_protocol(self) -> dict:
        """Convert internal state to the train_state protocol message."""
        return {
            "type": "train_state",
            "timestamp": time.time(),
            "vehicle_id": self.vehicle_id,
            "train_index": self.train_index,
            "line_id": self.line_id,
            "position": round(self.position, 3),
            "speed": round(self.speed_kmh, 3),
            "acceleration": round(self.acceleration, 3),
            "mode": self.mode,
            "is_running": self.is_running,
            "emergency_brake": self.emergency_brake,
            "edge_id": self.edge_id,
            "section_id": self.section_id,
            "edge_offset_m": (
                None if self.edge_offset_m is None else round(self.edge_offset_m, 3)
            ),
            "direction_code": self.direction_code,
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
    command: Optional[int] = None
    percent: Optional[float] = None
    main_handle_state: Optional[int] = None
    traction_percent: Optional[float] = None
    brake_percent: Optional[float] = None
    direction_code: Optional[int] = None


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
    command: Optional[int] = None
    percent: Optional[float] = None


@dataclass
class MaLimit:
    vehicle_id: str
    ma_limit: float
    target_speed: Optional[float]
    reason: str
    allowed_speed_kmh: Optional[float] = None
    eb_trigger_speed_kmh: Optional[float] = None
    target_distance_m: Optional[float] = None
    permission: Optional[str] = None
    signal_state: Optional[str] = None


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
    edge_id: Optional[int] = None
    begin_km: Optional[float] = None
    end_km: Optional[float] = None
    begin_switch: Optional[str] = None
    end_switch: Optional[str] = None
    direction_code: int = 1
