"""协议 v1.0：dashboard_snapshot 输出结构。"""
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.power import PowerStatus


class DashboardTrain(BaseModel):
    vehicle_id: str
    line_id: Optional[str] = None
    position: float
    speed: float
    acceleration: float
    mode: str = "manual"
    is_running: bool = True
    emergency_brake: bool = False
    ma_limit: Optional[float] = None
    target_speed: Optional[float] = None
    energy_kwh: float = 0.0
    stop_distance: Optional[float] = None
    station_name: Optional[str] = None
    parking_phase: Optional[str] = None
    stop_error_cm: Optional[float] = None
    platform_id: Optional[str] = None
    updated_at: Optional[float] = None


class DashboardSection(BaseModel):
    section_id: str
    start: float
    end: float
    occupied: bool
    vehicle_id: Optional[str] = None
    condition: str = "normal"
    aspect: str = "green"


class DashboardSignal(BaseModel):
    signal_id: str
    position: float
    state: str


class DashboardSwitch(BaseModel):
    switch_id: str
    routing: str = "normal"
    locked: bool = False
    related_section: Optional[str] = None


class DashboardAlarm(BaseModel):
    alarm_id: str
    level: str
    source: str
    vehicle_id: Optional[str] = None
    message: str
    timestamp: float


class DashboardSystem(BaseModel):
    status: str = "running"
    data_source: str = "mock"
    zmq_connected: bool = False
    websocket_clients: int = 0


class DashboardSnapshot(BaseModel):
    type: str = "dashboard_snapshot"
    protocol_version: str = "1.0"
    timestamp: float
    system: DashboardSystem
    trains: List[DashboardTrain]
    sections: List[DashboardSection]
    signals: List[DashboardSignal]
    switches: List[DashboardSwitch]
    power: PowerStatus
    alarms: List[DashboardAlarm] = []
