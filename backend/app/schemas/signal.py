from pydantic import BaseModel, Field
from typing import List, Optional


class SignalLight(BaseModel):
    signal_id: str
    position: float   # 里程位置 (m)
    state: str        # red | yellow | green


class SignalAspect(BaseModel):
    signal_id: str
    position: float
    state: str
    route_id: str
    signal_state: str
    permission: str


class SectionStatus(BaseModel):
    section_id: str
    start: float
    end: float
    occupied: bool
    vehicle_id: Optional[str] = None
    locked: bool = False
    locked_by_route_id: Optional[str] = None
    condition: str


class SwitchStatus(BaseModel):
    switch_id: str
    position: str
    locked: bool
    locked_by_route_id: Optional[str] = None
    related_section: str
    reason: str


class MovementAuthorityLimit(BaseModel):
    vehicle_id: str
    position: float
    route_id: str
    ma_limit: float
    distance_to_ma: float
    permission: str
    signal_state: str
    speed_limit: float
    target_speed: float
    reason: str
    front_vehicle_id: Optional[str] = None
    front_train_length: Optional[float] = None
    location_uncertainty: float
    communication_margin: float
    safety_margin: float
    front_protection_point: Optional[float] = None
    safe_distance: float
    current_speed: float
    route_speed_limit: float
    static_speed_limit: Optional[float] = None
    static_speed_limit_id: Optional[str] = None
    fault_speed_limit: Optional[float] = None
    speed_limit_reason: Optional[str] = None
    required_stop_distance: float
    emergency_stop_distance: float
    warning_distance: float
    braking_curve_speed_limit: float
    braking_model: str


class RouteResult(BaseModel):
    vehicle_id: str
    route_id: str
    allowed: bool
    reason: str
    required_switch_id: str
    required_position: str
    current_position: str
    locked_by_route_id: Optional[str] = None


class TrainStateInput(BaseModel):
    vehicle_id: str
    position: float
    speed: float
    route_id: str
    train_length: Optional[float] = None


class RouteRequestInput(BaseModel):
    vehicle_id: str
    route_id: str


class SignalEvaluateRequest(BaseModel):
    train_states: List[TrainStateInput]
    route_requests: List[RouteRequestInput] = Field(default_factory=list)


class SignalStatus(BaseModel):
    timestamp: float
    lights: List[SignalLight]
    signals: List[SignalAspect] = Field(default_factory=list)
    sections: List[SectionStatus] = Field(default_factory=list)
    switches: List[SwitchStatus] = Field(default_factory=list)
    ma_limits: List[MovementAuthorityLimit] = Field(default_factory=list)
    route_results: List[RouteResult] = Field(default_factory=list)
    system_mode: str = "normal"   # normal | degraded | emergency
