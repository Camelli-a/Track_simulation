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
    brake_level: int = Field(default=0, ge=0, le=4)
    direction: Literal["forward", "backward", "neutral"] = "forward"
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


class VehicleManagementResponse(BaseModel):
    accepted: bool = True
    ok: bool
    published: bool
    topic: Literal["add_train", "remove_train", "clear_trains", "reset_trains"]
    result: Dict[str, Any]
    trains: list[Dict[str, Any]]
