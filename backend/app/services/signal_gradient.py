from copy import deepcopy

from app.services.signal_track_config import GRADIENT_PROFILE


def find_gradient_at_position(position, gradient_profile=None) -> dict | None:
    try:
        position = float(position)
    except (TypeError, ValueError):
        return None

    profile = gradient_profile if gradient_profile is not None else GRADIENT_PROFILE
    matching_gradients = []
    for gradient in profile:
        try:
            start = float(gradient["start"])
            end = float(gradient["end"])
            gradient_value = float(gradient["gradient"])
        except (KeyError, TypeError, ValueError):
            continue
        if start <= position < end:
            candidate = deepcopy(gradient)
            candidate["gradient"] = gradient_value
            matching_gradients.append(candidate)

    if not matching_gradients:
        return None

    return min(
        matching_gradients,
        key=lambda item: (
            float(item["end"]) - float(item["start"]),
            int(item.get("source_index", 0)),
        ),
    )


def calculate_effective_deceleration(
    base_deceleration: float,
    gradient: float | None,
    min_deceleration: float = 0.35,
    max_deceleration: float = 1.20,
) -> float:
    base = _to_float(base_deceleration, 0.0)
    gradient_value = _to_float(gradient, 0.0)
    gradient_acceleration = 9.81 * (gradient_value / 1000.0)
    effective = base + gradient_acceleration
    return round(min(max(effective, min_deceleration), max_deceleration), 3)


def _to_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
