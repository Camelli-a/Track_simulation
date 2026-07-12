"""Pure movement-authority validation helpers.

This module deliberately has no dependency on ``Train`` or the message bus.  It
normalizes one already-decoded MA snapshot and returns a fail-safe result that
can later be consumed by ATO/ATP integration at a tick boundary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Literal, Optional


Permission = Literal["allow", "restricted", "stop"]
SignalState = Literal["green", "yellow", "red"]
DistanceSource = Literal["target_distance", "ma_limit", "conservative", "none"]

DEFAULT_MA_TIMEOUT_SEC = 1.6
DEFAULT_DISTANCE_TOLERANCE_M = 1.0

_EXPECTED_SIGNAL: dict[Permission, SignalState] = {
    "allow": "green",
    "restricted": "yellow",
    "stop": "red",
}


@dataclass(frozen=True)
class MaValidationResult:
    """Normalized, immutable result of validating one MA snapshot.

    ``valid`` means the MA is safe to use for continued movement.  A well-
    formed ``stop/red`` snapshot therefore remains observable in the result,
    but is deliberately not valid for traction.
    """

    valid: bool
    traction_permitted: bool
    ma_limit_m: Optional[float]
    allowed_speed_kmh: Optional[float]
    distance_to_ma_m: Optional[float]
    permission: Optional[Permission]
    signal_state: Optional[SignalState]
    updated_at: Optional[float]
    age_sec: Optional[float]
    distance_source: DistanceSource
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def reason(self) -> Optional[str]:
        """Return the primary fail-safe reason, if any."""

        return self.errors[0] if self.errors else None


def calculate_distance_to_ma(
    position_m: object,
    ma_limit_m: object,
    direction_code: object = 1,
) -> float:
    """Return signed remaining distance to an absolute MA endpoint.

    The vehicle protocol uses ``1`` for forward and ``2`` for reverse.  The
    textual forms used elsewhere in the project are accepted as well.  A
    negative result means the authority endpoint is already behind the train;
    callers must not turn it into forward authority.
    """

    position = _require_finite_number(position_m, "position_m")
    ma_limit = _require_finite_number(ma_limit_m, "ma_limit_m")
    direction_sign = _direction_sign(direction_code)
    distance = (ma_limit - position) * direction_sign
    return 0.0 if distance == 0.0 else distance


def effective_allowed_speed(
    allowed_speed_kmh: object,
    track_speed_limit_kmh: object | None = None,
) -> float:
    """Return the conservative non-negative speed limit.

    Invalid or negative limits raise ``ValueError`` instead of being silently
    converted into a potentially unsafe value.  ``track_speed_limit_kmh`` is
    optional so this helper is usable before track data is wired into Train.
    """

    allowed_speed = _require_non_negative_number(
        allowed_speed_kmh, "allowed_speed_kmh"
    )
    if track_speed_limit_kmh is None:
        return allowed_speed
    track_speed = _require_non_negative_number(
        track_speed_limit_kmh, "track_speed_limit_kmh"
    )
    return min(allowed_speed, track_speed)


def validate_ma(
    *,
    position_m: object,
    ma_limit_m: object | None,
    allowed_speed_kmh: object,
    target_distance_m: object | None = None,
    permission: object,
    signal_state: object,
    updated_at: object,
    now: object,
    timeout_sec: object = DEFAULT_MA_TIMEOUT_SEC,
    direction_code: object = 1,
    consistency_tolerance_m: object = DEFAULT_DISTANCE_TOLERANCE_M,
    future_tolerance_sec: object = 0.0,
    source_ok: bool = True,
    communication_ok: bool = True,
) -> MaValidationResult:
    """Validate and normalize a movement-authority snapshot.

    When both relative and absolute MA distances are present, their consistency
    is checked and the smaller non-negative distance is always selected.  A
    mismatch is diagnostic rather than permission to use the larger value.

    ``timeout_sec`` is exclusive: an age exactly equal to the timeout is still
    valid, while an older snapshot is expired.  Future timestamps beyond the
    explicitly configured tolerance are invalid.
    """

    timeout = _require_non_negative_number(timeout_sec, "timeout_sec")
    tolerance = _require_non_negative_number(
        consistency_tolerance_m, "consistency_tolerance_m"
    )
    future_tolerance = _require_non_negative_number(
        future_tolerance_sec, "future_tolerance_sec"
    )
    current_time = _require_finite_number(now, "now")

    errors: list[str] = []
    warnings: list[str] = []

    position = _optional_finite_number(position_m)
    if position is None:
        errors.append("invalid_position")
    elif position < 0.0:
        errors.append("negative_position")

    ma_limit = _optional_finite_number(ma_limit_m)
    if ma_limit_m is not None and ma_limit is None:
        errors.append("invalid_ma_limit")
    elif ma_limit is not None and ma_limit < 0.0:
        errors.append("negative_ma_limit")

    target_distance = _optional_finite_number(target_distance_m)
    if target_distance_m is not None and target_distance is None:
        errors.append("invalid_target_distance")
    elif target_distance is not None and target_distance < 0.0:
        errors.append("negative_target_distance")

    if ma_limit_m is None and target_distance_m is None:
        errors.append("missing_authority_distance")

    allowed_speed = _optional_finite_number(allowed_speed_kmh)
    if allowed_speed is None:
        errors.append("invalid_allowed_speed")
    elif allowed_speed < 0.0:
        errors.append("negative_allowed_speed")

    timestamp = _optional_finite_number(updated_at)
    age_sec: Optional[float] = None
    if timestamp is None:
        errors.append("invalid_updated_at")
    else:
        raw_age = current_time - timestamp
        age_sec = max(0.0, raw_age)
        if raw_age < -future_tolerance:
            errors.append("ma_timestamp_in_future")
        elif raw_age > timeout:
            errors.append("ma_expired")

    normalized_permission = _normalize_permission(permission)
    if normalized_permission is None:
        errors.append("invalid_permission")

    normalized_signal = _normalize_signal_state(signal_state)
    if normalized_signal is None:
        errors.append("invalid_signal_state")

    if (
        normalized_permission is not None
        and normalized_signal is not None
        and _EXPECTED_SIGNAL[normalized_permission] != normalized_signal
    ):
        errors.append("permission_signal_conflict")

    if normalized_permission == "stop":
        errors.append("movement_not_permitted")
        if allowed_speed is not None and allowed_speed > 0.0:
            errors.append("stop_speed_conflict")
    elif (
        normalized_permission in {"allow", "restricted"}
        and allowed_speed == 0.0
    ):
        errors.append("movement_speed_conflict")

    if source_ok is not True:
        errors.append("source_unavailable")
    if communication_ok is not True:
        errors.append("communication_lost")

    direction_sign: Optional[int]
    try:
        direction_sign = _direction_sign(direction_code)
    except ValueError:
        direction_sign = None
        errors.append("invalid_direction")

    derived_distance: Optional[float] = None
    if (
        position is not None
        and position >= 0.0
        and ma_limit is not None
        and ma_limit >= 0.0
        and direction_sign is not None
    ):
        derived_distance = (ma_limit - position) * direction_sign
        if derived_distance < 0.0:
            errors.append("authority_behind_train")

    usable_target_distance = (
        target_distance
        if target_distance is not None and target_distance >= 0.0
        else None
    )
    usable_derived_distance = (
        max(0.0, derived_distance) if derived_distance is not None else None
    )

    if usable_target_distance is not None and usable_derived_distance is not None:
        distance_to_ma = min(usable_target_distance, usable_derived_distance)
        distance_source: DistanceSource = "conservative"
        if abs(usable_target_distance - usable_derived_distance) > tolerance:
            warnings.append("distance_mismatch")
    elif usable_target_distance is not None:
        distance_to_ma = usable_target_distance
        distance_source = "target_distance"
    elif usable_derived_distance is not None:
        distance_to_ma = usable_derived_distance
        distance_source = "ma_limit"
    else:
        distance_to_ma = None
        distance_source = "none"

    if (
        distance_to_ma == 0.0
        and normalized_permission in {"allow", "restricted"}
    ):
        errors.append("authority_exhausted_with_movement_permission")

    normalized_ma_limit = (
        ma_limit if ma_limit is not None and ma_limit >= 0.0 else None
    )
    normalized_allowed_speed = (
        allowed_speed
        if allowed_speed is not None and allowed_speed >= 0.0
        else None
    )
    valid = not errors
    traction_permitted = bool(
        valid
        and normalized_permission in {"allow", "restricted"}
        and normalized_allowed_speed is not None
        and normalized_allowed_speed > 0.0
        and distance_to_ma is not None
        and distance_to_ma > 0.0
    )

    return MaValidationResult(
        valid=valid,
        traction_permitted=traction_permitted,
        ma_limit_m=normalized_ma_limit,
        allowed_speed_kmh=normalized_allowed_speed,
        distance_to_ma_m=distance_to_ma,
        permission=normalized_permission,
        signal_state=normalized_signal,
        updated_at=timestamp,
        age_sec=age_sec,
        distance_source=distance_source,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _direction_sign(direction_code: object) -> int:
    if isinstance(direction_code, bool):
        raise ValueError("direction_code must describe forward or reverse travel")
    if isinstance(direction_code, str):
        normalized = direction_code.strip().lower()
        if normalized in {"1", "forward", "up"}:
            return 1
        if normalized in {"2", "-1", "reverse", "backward", "down"}:
            return -1
    elif isinstance(direction_code, Real):
        normalized_number = float(direction_code)
        if math.isfinite(normalized_number):
            if normalized_number == 1.0:
                return 1
            if normalized_number in {2.0, -1.0}:
                return -1
    raise ValueError("direction_code must describe forward or reverse travel")


def _normalize_permission(value: object) -> Optional[Permission]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in _EXPECTED_SIGNAL:
        return normalized  # type: ignore[return-value]
    return None


def _normalize_signal_state(value: object) -> Optional[SignalState]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"green", "yellow", "red"}:
        return normalized  # type: ignore[return-value]
    return None


def _optional_finite_number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    normalized = float(value)
    return normalized if math.isfinite(normalized) else None


def _require_finite_number(value: object, field_name: str) -> float:
    normalized = _optional_finite_number(value)
    if normalized is None:
        raise ValueError(f"{field_name} must be a finite number")
    return normalized


def _require_non_negative_number(value: object, field_name: str) -> float:
    normalized = _require_finite_number(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return normalized
