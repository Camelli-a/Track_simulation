"""Pydantic schemas for the speed curve module."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# A single recorded / predicted point on the speed curve
# ---------------------------------------------------------------------------

class SpeedPoint(BaseModel):
    """One point on the speed-vs-distance (or speed-vs-time) curve."""

    timestamp: float = Field(..., description="Unix timestamp (s)")
    position_m: float = Field(..., description="Train front position (m)")
    speed_kmh: float = Field(..., description="Speed (km/h)")
    speed_ms: float = Field(..., description="Speed (m/s)")
    acceleration_mps2: float = Field(..., description="Acceleration (m/s²)")

    # Tractive effort / braking effort
    traction_level: int = Field(default=0, description="Traction notch 0-4")
    brake_level: int = Field(default=0, description="Brake notch 0-7")
    traction_percent: float = Field(default=0.0, description="Traction command %")
    brake_percent: float = Field(default=0.0, description="Brake command %")
    traction_force_n: float = Field(default=0.0, description="Traction force (N)")
    brake_force_n: float = Field(default=0.0, description="Brake force (N)")

    # Track context
    gradient_permille: float = Field(default=0.0, description="Track gradient (‰, + uphill)")
    speed_limit_kmh: Optional[float] = Field(default=None, description="Static speed limit (km/h)")

    # Control
    emergency_brake: bool = Field(default=False)
    control_mode: Literal["manual", "ato"] = Field(default="manual")
    source: str = Field(default="zmq", description="Data source tag")


# ---------------------------------------------------------------------------
# Predicted curve point (forward simulation)
# ---------------------------------------------------------------------------

class PredictedPoint(BaseModel):
    """One point of a forward-simulated prediction curve."""

    position_m: float
    speed_kmh: float
    speed_ms: float
    acceleration_mps2: float
    gradient_permille: float = 0.0
    speed_limit_kmh: Optional[float] = None
    traction_force_n: float = 0.0
    brake_force_n: float = 0.0


# ---------------------------------------------------------------------------
# API response schemas
# ---------------------------------------------------------------------------

class SpeedCurveHistory(BaseModel):
    """Historical speed curve for one vehicle."""

    vehicle_id: str
    count: int
    points: List[SpeedPoint]


class SpeedCurvePrediction(BaseModel):
    """Forward-simulated speed curve using the current driver command."""

    vehicle_id: str
    horizon_m: float = Field(..., description="Simulation horizon (m)")
    dt_s: float = Field(..., description="Integration step (s)")
    step_count: int
    points: List[PredictedPoint]


class SpeedCurveStatus(BaseModel):
    """Snapshot of current speed curve state for one vehicle."""

    vehicle_id: str
    connected: bool
    last_update_at: Optional[float]
    history_count: int
    current_speed_kmh: float = 0.0
    current_position_m: float = 0.0
    current_acceleration_mps2: float = 0.0
    current_traction_percent: float = 0.0
    current_brake_percent: float = 0.0
    current_gradient_permille: float = 0.0
    current_speed_limit_kmh: Optional[float] = None
    emergency_brake: bool = False
    control_mode: str = "manual"


class SpeedCurveListResponse(BaseModel):
    """List of all tracked vehicles."""

    vehicles: List[str]
    count: int
