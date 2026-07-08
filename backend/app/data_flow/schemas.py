from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


DataSource = Literal["mock", "udp", "zmq", "frontend", "unknown"]
SystemState = Literal["running", "degraded", "emergency", "offline"]
TrainMode = Literal["manual", "ato", "atp", "emergency", "unknown"]
SignalLightState = Literal["red", "yellow", "green", "unknown"]
MovementPermission = Literal["allow", "restricted", "stop", "unknown"]
ParkingPhase = Literal["cruising", "approaching", "braking", "docking", "stopped"]
SectionCondition = Literal["normal", "warning", "fault"]
SectionAspect = Literal["green", "yellow", "red", "unknown"]
SwitchPosition = Literal["normal", "reverse", "unknown"]
AlarmLevel = Literal["info", "warning", "critical"]


class IncomingMessage(BaseModel):
    """Loose input envelope for ZMQ/Mock messages from other modules."""

    type: str
    timestamp: float
    source: str = "unknown"
    data: Dict[str, Any] = Field(default_factory=dict)


class SystemStatus(BaseModel):
    status: SystemState = "running"
    system_mode: str = "normal"
    data_source: DataSource = "mock"
    zmq_connected: bool = False
    websocket_clients: int = 0


class CommunicationStatus(BaseModel):
    source: DataSource = "mock"
    driver_console_connected: bool = False
    udp_connected: bool = False
    zmq_connected: bool = False
    latency_ms: Optional[float] = None
    packet_loss_count: int = 0
    last_message_at: Optional[float] = None


class DriverInput(BaseModel):
    vehicle_id: str
    line_id: str = "LINE-1"
    source: DataSource = "mock"
    traction_level: int = 0
    brake_level: int = 0
    direction: Literal["forward", "backward", "neutral"] = "forward"
    control_mode: Literal["manual", "ato"] = "manual"
    emergency_button: bool = False
    updated_at: float
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class TrainSnapshot(BaseModel):
    vehicle_id: str
    line_id: str = "LINE-1"
    route_id: str = "R_MAIN"
    position: float = 0.0
    speed: float = 0.0
    acceleration: float = 0.0
    mode: TrainMode = "unknown"
    is_running: bool = True
    emergency_brake: bool = False
    ma_limit: Optional[float] = None
    distance_to_ma: Optional[float] = None
    permission: MovementPermission = "unknown"
    signal_state: SignalLightState = "unknown"
    speed_limit: Optional[float] = None
    target_speed: Optional[float] = None
    route_speed_limit: Optional[float] = None
    required_stop_distance: Optional[float] = None
    emergency_stop_distance: Optional[float] = None
    warning_distance: Optional[float] = None
    braking_curve_speed_limit: Optional[float] = None
    braking_model: Optional[str] = None
    front_vehicle_id: Optional[str] = None
    front_protection_point: Optional[float] = None
    energy_kwh: Optional[float] = None
    stop_distance: Optional[float] = None
    station_name: Optional[str] = None
    parking_phase: ParkingPhase = "cruising"
    stop_error_cm: Optional[float] = None
    platform_id: Optional[str] = None
    updated_at: float
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class TrackSectionSnapshot(BaseModel):
    section_id: str
    line_id: str = "LINE-1"
    track_seg_id: Optional[str] = None
    start: float
    end: float
    gradient: Optional[float] = None
    speed_limit: Optional[float] = None
    station_id: Optional[str] = None
    stop_position: Optional[float] = None
    occupied: bool = False
    vehicle_id: Optional[str] = None
    occupied_by: Optional[str] = None
    aspect: SectionAspect = "green"
    locked: bool = False
    locked_by_route_id: Optional[str] = None
    condition: SectionCondition = "normal"


class SignalSnapshot(BaseModel):
    signal_id: str
    position: float
    state: SignalLightState = "unknown"
    signal_type: Optional[str] = None
    route_id: Optional[str] = None
    signal_state: SignalLightState = "unknown"
    permission: MovementPermission = "unknown"


class SwitchSnapshot(BaseModel):
    switch_id: str
    position: SwitchPosition = "unknown"
    turnout_id: Optional[str] = None
    routing: SwitchPosition = "unknown"
    state: SwitchPosition = "unknown"
    locked: bool = False
    locked_by_route_id: Optional[str] = None
    related_section: Optional[str] = None
    reason: Optional[str] = None


class RouteResult(BaseModel):
    vehicle_id: Optional[str] = None
    route_id: Optional[str] = None
    allowed: bool = False
    reason: Optional[str] = None
    required_switch_id: Optional[str] = None
    required_position: Optional[SwitchPosition] = None
    current_position: Optional[SwitchPosition] = None
    locked_by_route_id: Optional[str] = None


class MovementAuthoritySnapshot(BaseModel):
    vehicle_id: str
    position: Optional[float] = None
    route_id: str = "R_MAIN"
    ma_limit: float
    distance_to_ma: Optional[float] = None
    permission: MovementPermission = "unknown"
    signal_state: SignalLightState = "unknown"
    speed_limit: Optional[float] = None
    target_speed: Optional[float] = None
    reason: Optional[str] = None
    front_vehicle_id: Optional[str] = None
    front_train_length: Optional[float] = None
    location_uncertainty: Optional[float] = None
    communication_margin: Optional[float] = None
    safety_margin: Optional[float] = None
    front_protection_point: Optional[float] = None
    safe_distance: Optional[float] = None
    current_speed: Optional[float] = None
    route_speed_limit: Optional[float] = None
    required_stop_distance: Optional[float] = None
    emergency_stop_distance: Optional[float] = None
    warning_distance: Optional[float] = None
    braking_curve_speed_limit: Optional[float] = None
    braking_model: Optional[str] = None
    updated_at: float
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class AtoCommandSnapshot(BaseModel):
    vehicle_id: str
    line_id: str = "LINE-1"
    control_mode: Literal["ato"] = "ato"
    target_speed: float = 0.0
    target_position: Optional[float] = None
    traction_level: int = 0
    brake_level: int = 0
    reason: str = "test"
    updated_at: float
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class PowerSnapshot(BaseModel):
    substation_id: str = "SS-01"
    voltage: float = 0.0
    current: float = 0.0
    power: float = 0.0
    is_fault: bool = False
    updated_at: Optional[float] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class AlarmEvent(BaseModel):
    alarm_id: str
    level: AlarmLevel = "info"
    source: str = "BACKEND"
    vehicle_id: Optional[str] = None
    message: str
    timestamp: float
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class DashboardSnapshot(BaseModel):
    type: Literal["dashboard_snapshot"] = "dashboard_snapshot"
    protocol_version: str = "1.0"
    timestamp: float
    system: SystemStatus
    communication: CommunicationStatus
    driver_inputs: List[DriverInput] = Field(default_factory=list)
    ato_commands: List[AtoCommandSnapshot] = Field(default_factory=list)
    trains: List[TrainSnapshot] = Field(default_factory=list)
    ma_limits: List[MovementAuthoritySnapshot] = Field(default_factory=list)
    sections: List[TrackSectionSnapshot] = Field(default_factory=list)
    signals: List[SignalSnapshot] = Field(default_factory=list)
    switches: List[SwitchSnapshot] = Field(default_factory=list)
    route_results: List[RouteResult] = Field(default_factory=list)
    power: PowerSnapshot = Field(default_factory=PowerSnapshot)
    alarms: List[AlarmEvent] = Field(default_factory=list)
