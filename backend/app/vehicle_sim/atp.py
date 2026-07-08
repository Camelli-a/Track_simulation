import time
from typing import Optional, Tuple

from .models import TrainState


def build_alarm(vehicle_id: str, level: str, message: str) -> dict:
    return {
        "type": "alarm_event",
        "timestamp": time.time(),
        "alarm_id": f"ALM-{int(time.time() * 1000)}",
        "level": level,
        "source": "ATP",
        "vehicle_id": vehicle_id,
        "message": message,
    }


def check_atp(
    state: TrainState,
    speed_limit: float,
    ma_limit: Optional[float],
    power_fault: bool,
    comm_ok: bool,
) -> Tuple[bool, Optional[dict]]:
    """Return whether ATP should trigger emergency braking."""
    if state.speed_kmh > speed_limit:
        return True, build_alarm(
            state.vehicle_id,
            "critical",
            "Train overspeed, emergency brake triggered",
        )

    if ma_limit is not None and state.position >= ma_limit:
        return True, build_alarm(
            state.vehicle_id,
            "critical",
            "Train exceeded MA limit, emergency brake triggered",
        )

    if power_fault:
        return True, build_alarm(
            state.vehicle_id,
            "critical",
            "Power fault, emergency brake triggered",
        )

    if not comm_ok:
        return True, build_alarm(
            state.vehicle_id,
            "critical",
            "Communication lost, emergency brake triggered",
        )

    return False, None
