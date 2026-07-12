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
    driving_mode: str = "SM"
    ato_state: Optional[str] = None
    recommended_speed: float = 0.0
    ato_target_speed: float = 0.0
    ato_traction_level: int = 0
    ato_brake_level: int = 0
    commanded_traction_level: int = 0
    commanded_brake_level: int = 0
    applied_traction_level: int = 0
    applied_brake_level: int = 0
    control_source: str = "manual"
    atp_intervened: bool = False
    stop_target: Optional[float] = None
    distance_to_stop: Optional[float] = None
    stop_result: Optional[dict] = None
    ato_brake_bias: float = 1.0
    ato_brake_bias_enabled: bool = False
    ato_brake_bias_adaptation_enabled: bool = False
    last_brake_bias_adjustment: Optional[dict] = None
    brake_bias_history_size: int = 0

    @property
    def speed_kmh(self) -> float:
        return self.speed_ms * 3.6

    @property
    def protocol_direction(self) -> int:
        if self.direction_code in (-1, 2, 0xAA):
            return -1
        return 1

    def to_protocol(self) -> dict:
        """Convert internal state to the train_state protocol message."""
        return {
            "type": "train_state",
            "timestamp": time.time(),
            "vehicle_id": self.vehicle_id,
            "train_index": self.train_index,
            "line_id": self.line_id,
            "position": round(self.position, 3),
            "position_m": round(self.position, 3),
            "speed": round(self.speed_kmh, 3),
            "speed_ms": round(self.speed_ms, 3),
            "speed_mps": round(self.speed_ms, 3),
            "speed_kmh": round(self.speed_kmh, 3),
            "acceleration": round(self.acceleration, 3),
            "acceleration_mps2": round(self.acceleration, 3),
            "mode": self.mode,
            "is_running": self.is_running,
            "emergency_brake": self.emergency_brake,
            "edge_id": self.edge_id,
            "section_id": self.section_id,
            "edge_offset_m": (
                None if self.edge_offset_m is None else round(self.edge_offset_m, 3)
            ),
            "direction_code": self.direction_code,
            "direction": self.protocol_direction,
            "driving_mode": self.driving_mode,
            "ato_state": self.ato_state,
            "recommended_speed": round(self.recommended_speed, 3),
            "recommended_speed_kmh": round(self.recommended_speed, 3),
            "recommended_speed_mps": round(self.recommended_speed / 3.6, 3),
            "ato_target_speed": round(self.ato_target_speed, 3),
            "ato_target_speed_kmh": round(self.ato_target_speed, 3),
            "ato_target_speed_mps": round(self.ato_target_speed / 3.6, 3),
            "ato_traction_level": self.ato_traction_level,
            "ato_brake_level": self.ato_brake_level,
            "commanded_traction_level": self.commanded_traction_level,
            "commanded_brake_level": self.commanded_brake_level,
            "applied_traction_level": self.applied_traction_level,
            "applied_brake_level": self.applied_brake_level,
            "control_source": self.control_source,
            "atp_intervened": self.atp_intervened,
            "stop_target": (
                None if self.stop_target is None else round(self.stop_target, 3)
            ),
            "distance_to_stop": (
                None if self.distance_to_stop is None else round(self.distance_to_stop, 3)
            ),
            "stop_result": self.stop_result,
            "ato_brake_bias": round(self.ato_brake_bias, 3),
            "ato_brake_bias_enabled": self.ato_brake_bias_enabled,
            "ato_brake_bias_adaptation_enabled": (
                self.ato_brake_bias_adaptation_enabled
            ),
            "last_brake_bias_adjustment": self.last_brake_bias_adjustment,
            "brake_bias_history_size": self.brake_bias_history_size,
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
    main_handle_raw: Optional[int] = None
    ato_capable: Optional[bool] = None
    ato_active: Optional[bool] = None
    ato_start_btn: Optional[bool] = None
    emergency_cmd: Optional[bool] = None
    key_switch: Optional[bool] = None
    network_fault_light: Optional[bool] = None
    raw_brake_level: Optional[int] = None
    fast_brake: bool = False


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
