from typing import List, Optional

from pydantic import BaseModel

from app.schemas.power import PowerStatus
from app.schemas.signal import SignalLight


class VehicleTick(BaseModel):
    vehicle_id: str
    position: float
    speed: float
    acceleration: float
    emergency_brake: bool = False
    energy_kwh: float = 0.0
    ma_end: Optional[float] = None
    drive_mode: str = "manual"           # manual | ato
    target_speed_limit: float = 80.0     # 当前分区限速 (km/h)，F5.2 目标指针
    station_name: Optional[str] = None   # 前方/当前站台
    stop_distance: Optional[float] = None  # 对标停车剩余距离 (m)
    parking_phase: Optional[str] = None  # cruising|approaching|braking|docking|stopped
    stop_error_cm: Optional[float] = None
    platform_id: Optional[str] = None


class TrackSegmentTick(BaseModel):
    segment_id: str
    start: float
    end: float
    occupied: bool
    aspect: str = "green"    # green | yellow | red — 闭塞分区信号显示
    condition: str = "normal"
    occupied_by: Optional[str] = None


class StationTick(BaseModel):
    station_id: str
    name: str
    position: float


class TurnoutTick(BaseModel):
    turnout_id: str
    position: float
    state: str = "normal"
    locked: bool = False


class SimulationTick(BaseModel):
    type: str = "tick"
    timestamp: float
    vehicles: List[VehicleTick]
    track_segments: List[TrackSegmentTick]
    stations: List[StationTick] = []
    total_length: float
    power: PowerStatus
    signals: List[SignalLight]
    turnouts: List[TurnoutTick] = []
    system_mode: str = "normal"
