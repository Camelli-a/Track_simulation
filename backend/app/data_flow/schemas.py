from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


DataSource = Literal["mock", "udp", "zmq", "unknown"]
SystemState = Literal["running", "degraded", "emergency", "offline"]
TrainMode = Literal["manual", "ato", "atp", "emergency", "unknown"]
SignalLightState = Literal["red", "yellow", "green", "unknown"]
SectionCondition = Literal["normal", "warning", "fault"]
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
    position: float = 0.0
    speed: float = 0.0
    acceleration: float = 0.0
    mode: TrainMode = "unknown"
    is_running: bool = True
    emergency_brake: bool = False
    ma_limit: Optional[float] = None
    updated_at: float
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class TrackSectionSnapshot(BaseModel):
    section_id: str
    start: float
    end: float
    occupied: bool = False
    vehicle_id: Optional[str] = None
    condition: SectionCondition = "normal"


class SignalSnapshot(BaseModel):
    signal_id: str
    position: float
    state: SignalLightState = "unknown"


class SwitchSnapshot(BaseModel):
    switch_id: str
    position: SwitchPosition = "unknown"
    locked: bool = False
    related_section: Optional[str] = None


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
    trains: List[TrainSnapshot] = Field(default_factory=list)
    sections: List[TrackSectionSnapshot] = Field(default_factory=list)
    signals: List[SignalSnapshot] = Field(default_factory=list)
    switches: List[SwitchSnapshot] = Field(default_factory=list)
    power: PowerSnapshot = Field(default_factory=PowerSnapshot)
    alarms: List[AlarmEvent] = Field(default_factory=list)

