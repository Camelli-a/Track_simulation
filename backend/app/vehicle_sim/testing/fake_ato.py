"""Deterministic ATO test double used before the real controller is integrated."""

from dataclasses import dataclass, replace
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class FakeAtoDecision:
    ato_state: str = "running"
    ato_target_speed_kmh: float = 0.0
    recommended_speed_kmh: float = 0.0
    traction_level: int = 0
    brake_level: int = 0
    distance_to_stop_m: float | None = None
    degraded_reason: str | None = None

    def normalized(self) -> "FakeAtoDecision":
        """Apply the production command contract: 0..4 and brake priority."""
        traction = max(0, min(4, int(self.traction_level)))
        brake = max(0, min(4, int(self.brake_level)))
        if brake > 0:
            traction = 0
        return replace(self, traction_level=traction, brake_level=brake)


class FakeAtoController:
    """Return scripted decisions while recording each compute input.

    This class deliberately has no dependency on ``Train`` or the message bus.
    It can be replaced by the real ``TrainAtoController`` without changing the
    surrounding MVP scenario assertions.
    """

    def __init__(
        self,
        decisions: list[FakeAtoDecision] | None = None,
        default: FakeAtoDecision | None = None,
    ) -> None:
        self.decisions = list(decisions or [])
        self.default = default or FakeAtoDecision()
        self.calls: list[dict[str, Any]] = []

    def compute(
        self,
        *,
        dt: float,
        speed_ms: float,
        position_m: float,
        gradient_permille: float,
        driving_mode: str,
        ma_state: Any,
        stop_target_m: float | None,
    ) -> FakeAtoDecision:
        numeric_inputs = (dt, speed_ms, position_m, gradient_permille)
        if not all(isfinite(float(value)) for value in numeric_inputs):
            raise ValueError("fake ATO numeric inputs must be finite")
        if dt <= 0.0:
            raise ValueError("dt must be positive")

        self.calls.append(
            {
                "dt": dt,
                "speed_ms": speed_ms,
                "position_m": position_m,
                "gradient_permille": gradient_permille,
                "driving_mode": driving_mode,
                "ma_state": ma_state,
                "stop_target_m": stop_target_m,
            }
        )
        index = len(self.calls) - 1
        decision = self.decisions[index] if index < len(self.decisions) else self.default
        return decision.normalized()
