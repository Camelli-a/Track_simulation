from dataclasses import dataclass


@dataclass
class SafetyEnvelope:
    vehicle_id: str
    allowed_speed_kmh: float | None = None
    eb_trigger_speed_kmh: float | None = None
    target_speed_kmh: float | None = None
    target_distance_m: float | None = None
    ma_limit_m: float | None = None

