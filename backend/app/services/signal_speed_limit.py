from copy import deepcopy

from app.services.signal_track_config import STATIC_SPEED_LIMITS


SPEED_LIMIT_REASON_PRIORITY = {
    "emergency_brake": 0,
    "stop": 1,
    "braking_curve": 2,
    "fault_limit": 3,
    "static_limit": 4,
    "route_limit": 5,
    "no_valid_limit": 6,
}


def _to_positive_float(value) -> float | None:
    try:
        if value is None:
            return None
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if converted > 0 else None


def find_static_speed_limit(position: float, static_speed_limits=None) -> dict | None:
    limits = static_speed_limits if static_speed_limits is not None else STATIC_SPEED_LIMITS
    matching_limits = []
    for limit in limits:
        try:
            start = float(limit["start"])
            end = float(limit["end"])
            speed_limit = float(limit["speed_limit"])
        except (KeyError, TypeError, ValueError):
            continue
        if start <= position < end:
            candidate = deepcopy(limit)
            candidate["speed_limit"] = speed_limit
            matching_limits.append(candidate)

    if not matching_limits:
        return None

    return min(matching_limits, key=lambda item: item["speed_limit"])


def resolve_speed_limit(
    *,
    permission: str,
    route_speed_limit: float | None,
    static_speed_limit: float | None = None,
    static_speed_limit_id: str | None = None,
    fault_speed_limit: float | None = None,
    braking_curve_speed_limit: float | None = None,
    emergency_brake: bool = False,
) -> dict:
    route_limit = _to_positive_float(route_speed_limit)
    static_limit = _to_positive_float(static_speed_limit)
    braking_limit = _to_positive_float(braking_curve_speed_limit)
    try:
        raw_fault_limit = None if fault_speed_limit is None else float(fault_speed_limit)
    except (TypeError, ValueError):
        raw_fault_limit = None

    result = {
        "route_speed_limit": round(route_limit, 1) if route_limit is not None else None,
        "static_speed_limit": round(static_limit, 1) if static_limit is not None else None,
        "static_speed_limit_id": static_speed_limit_id if static_limit is not None else None,
        "fault_speed_limit": round(raw_fault_limit, 1) if raw_fault_limit is not None else None,
        "braking_curve_speed_limit": round(braking_limit, 1) if braking_limit is not None else None,
    }

    if emergency_brake:
        return {
            **result,
            "speed_limit": 0.0,
            "speed_limit_reason": "emergency_brake",
            "permission_override": "stop",
            "signal_state_override": "red",
        }

    if str(permission).strip().lower() == "stop":
        return {
            **result,
            "speed_limit": 0.0,
            "speed_limit_reason": "stop",
        }

    if raw_fault_limit is not None:
        if raw_fault_limit <= 0:
            return {
                **result,
                "speed_limit": 0.0,
                "speed_limit_reason": "fault_limit",
                "permission_override": "stop",
                "signal_state_override": "red",
            }

    candidates = []
    if route_limit is not None:
        candidates.append((route_limit, "route_limit"))
    if static_limit is not None:
        candidates.append((static_limit, "static_limit"))
    if raw_fault_limit is not None and raw_fault_limit > 0:
        candidates.append((raw_fault_limit, "fault_limit"))
    if str(permission).strip().lower() == "restricted" and braking_limit is not None:
        candidates.append((braking_limit, "braking_curve"))

    if not candidates:
        return {
            **result,
            "speed_limit": 0.0,
            "speed_limit_reason": "no_valid_limit",
            "permission_override": "stop",
            "signal_state_override": "red",
        }

    speed_limit, reason = min(
        candidates,
        key=lambda item: (item[0], SPEED_LIMIT_REASON_PRIORITY[item[1]]),
    )
    return {
        **result,
        "speed_limit": round(max(speed_limit, 0.0), 1),
        "speed_limit_reason": reason,
    }
