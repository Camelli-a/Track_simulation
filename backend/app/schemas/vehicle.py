from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class VehicleStatus(BaseModel):
    timestamp: float
    vehicle_id: str
    position: float
    speed: float
    acceleration: float
    line_id: str
    is_running: bool = True


class VehicleControlRequest(BaseModel):
    vehicle_id: str = Field(default="TRAIN-001")
    line_id: str = Field(default="LINE-1")
    command: Literal["manual", "traction", "brake", "emergency_stop", "emergency_brake", "ato"] = "manual"
    level: int = Field(default=1, ge=0, le=4)
    source: str = "frontend"
    traction_level: int = Field(default=0, ge=0, le=4)
    brake_level: int = Field(default=0, ge=0, le=7)
    traction_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    brake_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    main_handle_raw: Optional[int] = None
    key_switch: Optional[bool] = None
    direction: Literal["forward", "reverse", "backward", "neutral"] = "forward"
    open_left_door: bool = False
    open_right_door: bool = False
    close_left_door: bool = False
    close_right_door: bool = False
    door_mode: Optional[str] = None
    door_closed_light: Optional[bool] = None
    high_voltage_light: Optional[bool] = None
    brake_bad_light: Optional[bool] = None
    network_fault_light: Optional[bool] = None
    target_speed: Optional[float] = Field(default=None, ge=0)
    target_position: Optional[float] = Field(default=None, ge=0)
    reason: str = "frontend_control"


class VehicleControlResponse(BaseModel):
    accepted: bool = True
    published: bool
    topic: Literal["driver_input", "ato_command"]
    message: Dict[str, Any]


class VehicleManagementRequest(BaseModel):
    type: Literal["add_train", "remove_train", "clear_trains", "reset_trains"]
    vehicle_id: Optional[str] = None
    train_index: Optional[int] = Field(default=None, ge=1)
    line_id: str = Field(default="LINE-1")
    position: float = Field(default=0.0, ge=0)
    count: Optional[int] = Field(default=None, ge=0)
    virtual_ato: bool = False
    enqueue_ato: bool = False


class VehicleManagementResponse(BaseModel):
    accepted: bool = True
    ok: bool
    published: bool
    topic: Literal["add_train", "remove_train", "clear_trains", "reset_trains"]
    result: Dict[str, Any]
    trains: list[Dict[str, Any]]


class DriverDeskBindingRequest(BaseModel):
    vehicle_id: str = Field(default="TRAIN-001")


class DriverDeskBindingResponse(BaseModel):
    accepted: bool = True
    published: bool
    topic: Literal["driver_desk_binding"]
    active_driver_vehicle_id: str
    previous_vehicle_id: Optional[str] = None


class DriverDeskBindingStatus(BaseModel):
    driver_desk_connected: bool = False
    active_driver_vehicle_id: Optional[str] = None


class StationDemoRequest(BaseModel):
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    headway_sec: float = Field(default=10.0, ge=5.0)
    dwell_sec: float = Field(default=4.0, ge=2.0)
    max_active_trains: int = Field(default=4, ge=1, le=12)
    approach_distance_m: float = Field(default=450.0, ge=100.0)
    exit_distance_m: float = Field(default=1000.0, ge=100.0)
    min_train_spacing_m: float = Field(default=260.0, ge=120.0)
    cruise_speed_kmh: float = Field(default=28.0, ge=5.0, le=80.0)
    start_index: int = Field(default=20, ge=1)


class LineOperationRequest(BaseModel):
    headway_sec: float = Field(default=8.0, ge=3.0)
    max_active_trains: int = Field(default=10, ge=2, le=30)
    dwell_sec: float = Field(default=4.0, ge=2.0)
    min_train_spacing_m: float = Field(default=550.0, ge=150.0)
    start_index_up: int = Field(default=2000, ge=1)
    start_index_down: int = Field(default=3000, ge=1)
