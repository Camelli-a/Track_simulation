from typing import Any, Dict

from pydantic import BaseModel, Field


class DriverDeskSimStartRequest(BaseModel):
    vehicle_id: str = "TRAIN-001"
    simulator_host: str = "127.0.0.1"
    simulator_port: int = 18001
    pulse_width_ms: int = 250


class DriverDeskSimInputUpdateRequest(BaseModel):
    updates: Dict[str, Any] = Field(default_factory=dict)


class DriverDeskSimPulseRequest(BaseModel):
    field_name: str
    duration_ms: int | None = None
