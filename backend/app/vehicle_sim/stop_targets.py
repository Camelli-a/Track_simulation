"""Vehicle-side stop-target data and lookup helpers.

Stop target positions are absolute line mileages in metres.  They are not
remaining distances.  This module deliberately has no dependency on the
signal service; signal-side dictionaries must be injected through
``StopTarget.from_dict`` or ``StopTargetProvider.from_dicts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Any, Iterable, Mapping


FORWARD = "forward"
REVERSE = "reverse"

_MISSING = object()
_FORWARD_DIRECTIONS = {
    1,
    0x55,
    "+1",
    "1",
    "0x55",
    "forward",
    "up",
}
_REVERSE_DIRECTIONS = {
    -1,
    2,
    0xAA,
    "-1",
    "2",
    "0xaa",
    "reverse",
    "backward",
    "down",
}


def normalize_direction(direction: object) -> str:
    """Return the canonical travel direction used by stop-target queries.

    The aliases reflect the direction conventions already used by the vehicle
    and signal adapters.  Neutral or unknown directions are rejected because
    there is no meaningful "next" target without a travel direction.
    """

    if isinstance(direction, bool):
        raise ValueError("direction must identify forward or reverse travel")

    normalized = direction.strip().lower() if isinstance(direction, str) else direction
    if normalized in _FORWARD_DIRECTIONS:
        return FORWARD
    if normalized in _REVERSE_DIRECTIONS:
        return REVERSE
    raise ValueError(f"unsupported stop-target direction: {direction!r}")


@dataclass(frozen=True, slots=True)
class StopTarget:
    """An operational stopping point in an absolute line coordinate system."""

    target_id: str
    line_id: str
    route_id: str
    direction: str
    position_m: float
    station_id: str | None = None
    station_name: str | None = None
    platform_id: str | None = None
    platform_name: str | None = None
    window_before_m: float = 0.5
    window_after_m: float = 0.5
    approach_distance_m: float = 600.0
    source: str = "injected"
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", _required_text(self.target_id, "target_id"))
        object.__setattr__(self, "line_id", _required_text(self.line_id, "line_id"))
        object.__setattr__(self, "route_id", _required_text(self.route_id, "route_id"))
        object.__setattr__(self, "direction", normalize_direction(self.direction))
        object.__setattr__(self, "position_m", _nonnegative_finite(self.position_m, "position_m"))
        object.__setattr__(
            self,
            "window_before_m",
            _nonnegative_finite(self.window_before_m, "window_before_m"),
        )
        object.__setattr__(
            self,
            "window_after_m",
            _nonnegative_finite(self.window_after_m, "window_after_m"),
        )
        object.__setattr__(
            self,
            "approach_distance_m",
            _nonnegative_finite(self.approach_distance_m, "approach_distance_m"),
        )
        object.__setattr__(self, "source", _required_text(self.source, "source"))

        for field_name in ("station_id", "station_name", "platform_id", "platform_name"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _required_text(value, field_name))

        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        default_line_id: str | None = None,
        default_route_id: str | None = None,
    ) -> "StopTarget":
        """Build a validated target from modern or legacy configuration fields.

        Modern vehicle-side fields carry a unit suffix (``position_m``).  The
        legacy signal configuration names (``position``, ``window_before``,
        ``window_after`` and ``approach_distance``) are accepted only here, at
        the injection boundary.
        """

        if not isinstance(data, Mapping):
            raise TypeError("stop target configuration must be a mapping")

        line_id = data.get("line_id", default_line_id)
        route_id = data.get("route_id", default_route_id)
        position_m = _aliased_number(data, "position_m", "position", required=True)
        window_before_m = _aliased_number(
            data,
            "window_before_m",
            "window_before",
            default=0.5,
        )
        window_after_m = _aliased_number(
            data,
            "window_after_m",
            "window_after",
            default=0.5,
        )
        approach_distance_m = _aliased_number(
            data,
            "approach_distance_m",
            "approach_distance",
            default=600.0,
        )

        known_fields = {
            "target_id",
            "line_id",
            "route_id",
            "direction",
            "position_m",
            "position",
            "station_id",
            "station_name",
            "platform_id",
            "platform_name",
            "window_before_m",
            "window_before",
            "window_after_m",
            "window_after",
            "approach_distance_m",
            "approach_distance",
            "source",
            "metadata",
        }
        supplied_metadata = data.get("metadata", {})
        if not isinstance(supplied_metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        metadata = dict(supplied_metadata)
        metadata.update({key: value for key, value in data.items() if key not in known_fields})

        return cls(
            target_id=data.get("target_id"),
            line_id=line_id,
            route_id=route_id,
            direction=data.get("direction"),
            position_m=position_m,
            station_id=data.get("station_id"),
            station_name=data.get("station_name"),
            platform_id=data.get("platform_id"),
            platform_name=data.get("platform_name"),
            window_before_m=window_before_m,
            window_after_m=window_after_m,
            approach_distance_m=approach_distance_m,
            source=data.get("source", "injected"),
            metadata=metadata,
        )

    def signed_distance_m(self, position_m: float) -> float:
        """Return distance in the travel direction; negative means passed."""

        current_position_m = _nonnegative_finite(position_m, "position_m")
        if self.direction == FORWARD:
            return self.position_m - current_position_m
        return current_position_m - self.position_m

    def matches_context(self, *, line_id: str, route_id: str, direction: object) -> bool:
        """Return whether this target belongs to a train's active path."""

        return (
            self.line_id == line_id
            and self.route_id == route_id
            and self.direction == normalize_direction(direction)
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize with explicit vehicle-side metre suffixes."""

        result: dict[str, Any] = {
            "target_id": self.target_id,
            "line_id": self.line_id,
            "route_id": self.route_id,
            "direction": self.direction,
            "position_m": self.position_m,
            "window_before_m": self.window_before_m,
            "window_after_m": self.window_after_m,
            "approach_distance_m": self.approach_distance_m,
            "source": self.source,
        }
        for field_name in ("station_id", "station_name", "platform_id", "platform_name"):
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result


class StopTargetProvider:
    """Immutable, deterministic lookup over injected stop targets."""

    def __init__(self, targets: Iterable[StopTarget] = ()) -> None:
        target_tuple = tuple(targets)
        if any(not isinstance(target, StopTarget) for target in target_tuple):
            raise TypeError("targets must contain only StopTarget instances")

        targets_by_id: dict[str, StopTarget] = {}
        for target in target_tuple:
            if target.target_id in targets_by_id:
                raise ValueError(f"duplicate stop target id: {target.target_id}")
            targets_by_id[target.target_id] = target

        self._targets = target_tuple
        self._targets_by_id = MappingProxyType(targets_by_id)

    @classmethod
    def from_dicts(
        cls,
        configs: Iterable[Mapping[str, Any]],
        *,
        default_line_id: str | None = None,
        default_route_id: str | None = None,
    ) -> "StopTargetProvider":
        return cls(
            StopTarget.from_dict(
                config,
                default_line_id=default_line_id,
                default_route_id=default_route_id,
            )
            for config in configs
        )

    def __len__(self) -> int:
        return len(self._targets)

    @property
    def targets(self) -> tuple[StopTarget, ...]:
        return self._targets

    def get(self, target_id: str | None) -> StopTarget | None:
        if target_id is None:
            return None
        return self._targets_by_id.get(target_id)

    def targets_for(
        self,
        *,
        line_id: str | None,
        route_id: str | None,
        direction: object | None,
    ) -> tuple[StopTarget, ...]:
        """Return matching targets ordered in their direction of travel."""

        context = _normalize_runtime_context(line_id, route_id, direction)
        if context is None:
            return ()
        normalized_line_id, normalized_route_id, normalized_direction = context
        matching = [
            target
            for target in self._targets
            if target.matches_context(
                line_id=normalized_line_id,
                route_id=normalized_route_id,
                direction=normalized_direction,
            )
        ]
        position_factor = 1.0 if normalized_direction == FORWARD else -1.0
        return tuple(sorted(matching, key=lambda item: (position_factor * item.position_m, item.target_id)))

    def find_next(
        self,
        *,
        line_id: str | None,
        route_id: str | None,
        direction: object | None,
        position_m: float | None,
        include_current: bool = True,
        exclude_target_ids: Iterable[str] = (),
    ) -> StopTarget | None:
        """Find the nearest not-passed target for the active line and route.

        Missing runtime context fails closed with ``None``.  Completed targets
        can be excluded explicitly so a caller can switch to the next target
        even while the train is still inside the completed target's window.
        """

        if position_m is None:
            return None
        current_position_m = _nonnegative_finite(position_m, "position_m")
        excluded = frozenset(exclude_target_ids)
        candidates: list[tuple[float, StopTarget]] = []
        for target in self.targets_for(line_id=line_id, route_id=route_id, direction=direction):
            if target.target_id in excluded:
                continue
            distance_m = target.signed_distance_m(current_position_m)
            if distance_m > 0.0 or (include_current and distance_m == 0.0):
                candidates.append((distance_m, target))

        if not candidates:
            return None
        return min(candidates, key=lambda item: (item[0], item[1].target_id))[1]

    def resolve_target(
        self,
        *,
        line_id: str | None,
        route_id: str | None,
        direction: object | None,
        position_m: float | None,
        current_target_id: str | None = None,
        completed_target_ids: Iterable[str] = (),
    ) -> StopTarget | None:
        """Keep a selected target stable until the caller marks it completed.

        This small, stateless primitive lets the future ATO retain an overshot
        target long enough to publish its stop result, then switch by adding its
        id to ``completed_target_ids``.  A direction or route change immediately
        invalidates the retained target.
        """

        completed = frozenset(completed_target_ids)
        current = self.get(current_target_id)
        context = _normalize_runtime_context(line_id, route_id, direction)
        if current is not None and current.target_id not in completed and context is not None:
            normalized_line_id, normalized_route_id, normalized_direction = context
            if current.matches_context(
                line_id=normalized_line_id,
                route_id=normalized_route_id,
                direction=normalized_direction,
            ):
                return current

        return self.find_next(
            line_id=line_id,
            route_id=route_id,
            direction=direction,
            position_m=position_m,
            exclude_target_ids=completed,
        )


def find_next_stop_target(
    targets: Iterable[StopTarget],
    *,
    line_id: str | None,
    route_id: str | None,
    direction: object | None,
    position_m: float | None,
    include_current: bool = True,
    exclude_target_ids: Iterable[str] = (),
) -> StopTarget | None:
    """Pure convenience wrapper for one-off stop-target lookup."""

    return StopTargetProvider(targets).find_next(
        line_id=line_id,
        route_id=route_id,
        direction=direction,
        position_m=position_m,
        include_current=include_current,
        exclude_target_ids=exclude_target_ids,
    )


def _normalize_runtime_context(
    line_id: str | None,
    route_id: str | None,
    direction: object | None,
) -> tuple[str, str, str] | None:
    if line_id is None or route_id is None or direction is None:
        return None
    if not isinstance(line_id, str) or not line_id.strip():
        return None
    if not isinstance(route_id, str) or not route_id.strip():
        return None
    return line_id.strip(), route_id.strip(), normalize_direction(direction)


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _nonnegative_finite(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite non-negative number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite non-negative number") from exc
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{field_name} must be a finite non-negative number")
    return number


def _aliased_number(
    data: Mapping[str, Any],
    modern_name: str,
    legacy_name: str,
    *,
    required: bool = False,
    default: float | object = _MISSING,
) -> object:
    modern_value = data.get(modern_name, _MISSING)
    legacy_value = data.get(legacy_name, _MISSING)

    if modern_value is not _MISSING and legacy_value is not _MISSING:
        modern_number = _nonnegative_finite(modern_value, modern_name)
        legacy_number = _nonnegative_finite(legacy_value, legacy_name)
        if not math.isclose(modern_number, legacy_number, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"conflicting {modern_name} and {legacy_name} values")
        return modern_number
    if modern_value is not _MISSING:
        return modern_value
    if legacy_value is not _MISSING:
        return legacy_value
    if default is not _MISSING:
        return default
    if required:
        raise ValueError(f"missing required field: {modern_name}")
    return None
