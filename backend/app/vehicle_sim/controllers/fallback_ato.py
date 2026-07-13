import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FallbackAtoProfile:
    cruise_speed_kmh: float = 35.0
    service_deceleration_ms2: float = 0.85
    reaction_time_sec: float = 0.6
    stop_margin_m: float = 4.0
    precision_window_m: float = 0.8
    hold_speed_kmh: float = 0.5
    min_creep_distance_m: float = 2.0


class FallbackAtoController:
    """Local station-stop ATO used only when no external ATO is available."""

    def __init__(
        self,
        target_position: float,
        target_speed_kmh: float = 30.0,
        profile: FallbackAtoProfile | None = None,
    ):
        self.target_position = target_position
        self.profile = profile or FallbackAtoProfile(
            cruise_speed_kmh=max(5.0, target_speed_kmh)
        )
        self.last_phase = "fallback_init"

    def compute(self, position: float, speed_kmh: float) -> tuple[int, int, str]:
        distance = self.target_position - position
        speed_ms = max(speed_kmh, 0.0) / 3.6

        if distance <= -self.profile.precision_window_m:
            return self._phase(0, 4, "fallback_overshoot_emergency_brake")

        if distance <= self.profile.precision_window_m:
            if speed_kmh <= self.profile.hold_speed_kmh:
                return self._phase(0, 1, "fallback_stop_hold")
            return self._phase(0, 3, "fallback_final_stop_brake")

        if self._should_creep(distance, speed_kmh):
            return self._phase(1, 0, "fallback_precision_creep")

        target_speed = self._target_speed_for_distance(distance)
        speed_error = speed_kmh - target_speed

        if distance <= 5.0:
            if speed_kmh > 2.0:
                return self._phase(0, 3, "fallback_docking_strong_brake")
            if speed_kmh > self.profile.hold_speed_kmh:
                return self._phase(0, 2, "fallback_docking_medium_brake")
            return self._phase(0, 0, "fallback_docking_coast")

        if speed_error > 12.0:
            return self._phase(0, 4, "fallback_curve_urgent_brake")
        if speed_error > 6.0:
            return self._phase(0, 3, "fallback_curve_strong_brake")
        if speed_error > 2.0:
            return self._phase(0, 2, "fallback_curve_service_brake")
        if speed_error > 0.5:
            return self._phase(0, 1, "fallback_curve_trim_brake")

        if speed_error < -8.0 and distance > self._release_margin(distance):
            return self._phase(3, 0, "fallback_recover_traction")
        if speed_error < -3.0 and distance > 25.0:
            return self._phase(2, 0, "fallback_cruise_traction")

        return self._phase(0, 0, "fallback_coast_on_curve")

    def _target_speed_for_distance(self, distance: float) -> float:
        available_distance = max(0.0, distance - self.profile.stop_margin_m)
        curve_speed_ms = max(
            0.0,
            -self.profile.service_deceleration_ms2 * self.profile.reaction_time_sec
            + math.sqrt(
                (self.profile.service_deceleration_ms2 * self.profile.reaction_time_sec) ** 2
                + 2 * self.profile.service_deceleration_ms2 * available_distance
            ),
        )
        curve_speed_kmh = curve_speed_ms * 3.6
        return min(
            self.profile.cruise_speed_kmh,
            self._approach_cap(distance),
            curve_speed_kmh,
        )

    def _approach_cap(self, distance: float) -> float:
        if distance <= 8.0:
            return 5.0
        if distance <= 20.0:
            return 10.0
        if distance <= 50.0:
            return 18.0
        if distance <= 100.0:
            return 28.0
        return self.profile.cruise_speed_kmh

    def _should_creep(self, distance: float, speed_kmh: float) -> bool:
        return (
            distance > self.profile.min_creep_distance_m
            and distance <= 15.0
            and speed_kmh < 1.0
        )

    def _release_margin(self, distance: float) -> float:
        if distance > 120.0:
            return 60.0
        if distance > 60.0:
            return 35.0
        return 25.0

    def _phase(self, traction_level: int, brake_level: int, phase: str) -> tuple[int, int, str]:
        self.last_phase = phase
        return traction_level, brake_level, phase
