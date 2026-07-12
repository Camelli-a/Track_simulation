import math
from dataclasses import dataclass


@dataclass(frozen=True)
class AtoControlInput:
    position_m: float = 0.0
    speed_ms: float = 0.0
    vehicle_id: str | None = None
    ma_limit_m: float | None = None
    allowed_speed_kmh: float | None = None
    stop_target_m: float | None = None
    target_distance_m: float | None = None
    permission: str | None = None
    signal_state: str | None = None
    driving_mode: str = "SM"
    direction: int | str | None = None
    ma_valid: bool | None = None
    ma_age_sec: float | None = None
    max_ma_age_sec: float = 1.0
    comm_ok: bool | None = None
    dt: float = 0.1
    acceleration_ms2: float = 0.0
    control_delay_sec: float = 0.0
    delay_compensation_enabled: bool = False


@dataclass(frozen=True)
class AtoControlOutput:
    vehicle_id: str | None
    driving_mode: str
    ato_state: str
    ato_traction_level: int
    ato_brake_level: int
    commanded_traction_level: int
    commanded_brake_level: int
    applied_traction_level: int
    applied_brake_level: int
    control_source: str
    atp_intervened: bool
    recommended_speed_kmh: float
    ato_target_speed_kmh: float
    safe_speed_limit_kmh: float
    stop_target_m: float | None
    effective_target_m: float | None
    distance_to_stop_m: float | None
    distance_to_ma_m: float | None
    holding_brake: bool
    degraded: bool
    reason: str | None

    @property
    def traction_level(self) -> int:
        return self.commanded_traction_level

    @property
    def brake_level(self) -> int:
        return self.commanded_brake_level


@dataclass(frozen=True)
class StopResult:
    vehicle_id: str | None
    target_position_m: float
    actual_position_m: float
    error_m: float
    error_cm: float
    qualified: bool
    status: str
    speed_ms: float


class TrainAtoController:
    MAX_LEVEL = 4
    STOP_WINDOW_M = 0.5
    CREEP_DISTANCE_M = 5.0
    HOLD_DISTANCE_M = 0.5
    HOLD_SPEED_MS = 0.15
    CRAWL_SPEED_MS = 0.5
    POSITION_CONTROL_DISTANCE_M = 12.0
    POSITION_KP = 0.28
    MIN_CREEP_SPEED_MS = 0.12
    LOW_SPEED_DEADBAND_MS = 0.08
    COMFORT_DECEL_MS2 = 0.65
    MIN_DECEL_MS2 = 0.2
    MAX_DECEL_MS2 = 0.9
    SPEED_DEADBAND_KMH = 1.0
    DEFAULT_CONTROL_DELAY_SEC = 0.3
    MAX_CONTROL_DELAY_SEC = 1.0

    def clamp_level(self, level) -> int:
        return max(0, min(self.MAX_LEVEL, int(round(float(level)))))

    def resolve_exclusive_levels(
        self,
        traction_level: float,
        brake_level: float,
    ) -> tuple[int, int]:
        traction_level = self.clamp_level(traction_level)
        brake_level = self.clamp_level(brake_level)
        if brake_level > 0:
            traction_level = 0
        return traction_level, brake_level

    def is_finite_number(self, value) -> bool:
        if value is None:
            return False
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    def ms_to_kmh(self, value: float) -> float:
        return max(0.0, float(value)) * 3.6

    def kmh_to_ms(self, value: float) -> float:
        return max(0.0, float(value)) / 3.6

    def compute_low_speed_target_ms(self, distance_to_stop_m: float) -> float:
        distance_to_stop_m = float(distance_to_stop_m)
        if distance_to_stop_m <= self.HOLD_DISTANCE_M:
            return 0.0

        target_speed_ms = self.POSITION_KP * distance_to_stop_m
        if distance_to_stop_m <= self.CREEP_DISTANCE_M:
            return min(
                self.CRAWL_SPEED_MS,
                max(self.MIN_CREEP_SPEED_MS, target_speed_ms),
            )

        return min(1.5, max(self.CRAWL_SPEED_MS, target_speed_ms))

    def compute_predicted_state(
        self,
        position_m: float,
        speed_ms: float,
        acceleration_ms2: float,
        direction: int | str | None,
        control_delay_sec: float,
        enabled: bool,
    ) -> tuple[float, float]:
        position_m = self._finite_or_default(position_m, 0.0)
        speed_ms = max(0.0, self._finite_or_default(speed_ms, 0.0))
        acceleration_ms2 = self._finite_or_default(acceleration_ms2, 0.0)
        delay = self._normalized_delay(control_delay_sec)
        if not enabled or delay <= 0.0:
            return position_m, speed_ms

        predicted_speed_ms = max(0.0, speed_ms + acceleration_ms2 * delay)
        delta_m = speed_ms * delay + 0.5 * acceleration_ms2 * delay * delay
        if self._is_reverse_direction(direction):
            predicted_position_m = position_m - delta_m
        else:
            predicted_position_m = position_m + delta_m

        if not math.isfinite(predicted_position_m):
            predicted_position_m = position_m
        if not math.isfinite(predicted_speed_ms):
            predicted_speed_ms = speed_ms
        return predicted_position_m, predicted_speed_ms

    def compute_control(self, control_input: AtoControlInput) -> AtoControlOutput:
        driving_mode = str(control_input.driving_mode).upper()
        if driving_mode == "AM":
            return self.compute_am_command(control_input)
        if driving_mode == "SM":
            return self.compute_sm_recommendation(control_input)
        return self.compute_sm_recommendation(control_input)

    def compute_am_command(self, control_input: AtoControlInput) -> AtoControlOutput:
        _, invalid_reason = self.validate_ma_context(control_input)
        if invalid_reason is not None:
            return self._degraded_output(control_input, "AM", invalid_reason)

        control_position_m, control_speed_ms = self.compute_predicted_state(
            position_m=control_input.position_m,
            speed_ms=control_input.speed_ms,
            acceleration_ms2=control_input.acceleration_ms2,
            direction=control_input.direction,
            control_delay_sec=control_input.control_delay_sec,
            enabled=control_input.delay_compensation_enabled,
        )
        control_input_for_decision = self._replace_control_state(
            control_input, control_position_m, control_speed_ms
        )

        ma_context = self._ma_context(control_input_for_decision)
        distance_to_ma_m = ma_context["distance_to_ma_m"]
        safe_speed_limit_kmh = float(control_input.allowed_speed_kmh)
        stop_target_m = control_input.stop_target_m
        actual_distance_to_stop_m = self._distance_to_stop(control_input)
        predicted_distance_to_stop_m = self._distance_to_stop(control_input_for_decision)
        distance_to_stop_m = self._more_conservative_distance(
            actual_distance_to_stop_m,
            predicted_distance_to_stop_m,
        )
        if distance_to_ma_m is not None and distance_to_ma_m <= 0.0:
            return self._degraded_output(
                control_input_for_decision,
                "AM",
                "predicted_ma_overrun",
            )
        stop_target_is_safe = (
            stop_target_m is not None
            and distance_to_stop_m is not None
            and distance_to_stop_m >= 0.0
            and stop_target_m <= ma_context["effective_ma_limit_m"] + 1e-6
        )

        effective_target_m = (
            stop_target_m if stop_target_is_safe else ma_context["effective_ma_limit_m"]
        )
        effective_distance_m = max(0.0, effective_target_m - control_position_m)

        if (
            stop_target_is_safe
            and abs(distance_to_stop_m) <= self.HOLD_DISTANCE_M
            and control_speed_ms <= self.HOLD_SPEED_MS
        ):
            return self._build_output(
                vehicle_id=control_input.vehicle_id,
                driving_mode="AM",
                ato_state="holding",
                ato_traction_level=0,
                ato_brake_level=self.MAX_LEVEL,
                commanded_traction_level=0,
                commanded_brake_level=self.MAX_LEVEL,
                control_source="ato",
                recommended_speed_kmh=0.0,
                ato_target_speed_kmh=0.0,
                safe_speed_limit_kmh=safe_speed_limit_kmh,
                stop_target_m=stop_target_m,
                effective_target_m=effective_target_m,
                distance_to_stop_m=predicted_distance_to_stop_m,
                distance_to_ma_m=distance_to_ma_m,
                holding_brake=True,
                degraded=False,
                reason="stopped_in_window",
            )

        target_speed_kmh = self._curve_target_speed_kmh(
            effective_distance_m, safe_speed_limit_kmh
        )
        target_speed_ms = self.kmh_to_ms(target_speed_kmh)
        ato_state = "approaching"
        use_low_speed_levels = False

        if distance_to_stop_m is not None and distance_to_stop_m < 0.0:
            target_speed_ms = 0.0
            target_speed_kmh = 0.0
            ato_state = "braking_to_stop"
            use_low_speed_levels = True

        if (
            stop_target_is_safe
            and distance_to_stop_m is not None
            and 0.0 <= distance_to_stop_m <= self.POSITION_CONTROL_DISTANCE_M
        ):
            low_speed_target_ms = self.compute_low_speed_target_ms(distance_to_stop_m)
            target_speed_ms = min(target_speed_ms, low_speed_target_ms)
            target_speed_kmh = min(target_speed_ms * 3.6, safe_speed_limit_kmh)
            use_low_speed_levels = True
            if distance_to_stop_m <= self.CREEP_DISTANCE_M:
                ato_state = "creep"

        if use_low_speed_levels:
            traction_level, brake_level = self._levels_for_low_speed_error(
                current_speed_ms=control_speed_ms,
                target_speed_ms=target_speed_ms,
            )
        else:
            current_speed_kmh = self.ms_to_kmh(control_speed_ms)
            traction_level, brake_level = self._levels_for_speed_error(
                current_speed_kmh=current_speed_kmh,
                target_speed_kmh=target_speed_kmh,
            )
        traction_level, brake_level = self.resolve_exclusive_levels(
            traction_level, brake_level
        )
        if brake_level > 0 and ato_state != "creep":
            ato_state = "braking_to_stop"

        reason = "normal"
        if (
            control_input.stop_target_m is not None
            and control_input.stop_target_m > ma_context["effective_ma_limit_m"]
        ):
            reason = "stop_target_beyond_ma"
        elif distance_to_stop_m is not None and distance_to_stop_m < 0.0:
            reason = "stop_target_behind_train"

        return self._build_output(
            vehicle_id=control_input.vehicle_id,
            driving_mode="AM",
            ato_state=ato_state,
            ato_traction_level=traction_level,
            ato_brake_level=brake_level,
            commanded_traction_level=traction_level,
            commanded_brake_level=brake_level,
            control_source="ato",
            recommended_speed_kmh=round(target_speed_kmh, 3),
            ato_target_speed_kmh=round(target_speed_kmh, 3),
            safe_speed_limit_kmh=safe_speed_limit_kmh,
            stop_target_m=stop_target_m,
            effective_target_m=effective_target_m,
            distance_to_stop_m=predicted_distance_to_stop_m,
            distance_to_ma_m=distance_to_ma_m,
            holding_brake=False,
            degraded=False,
            reason=reason,
        )

    def compute_sm_recommendation(self, control_input: AtoControlInput) -> AtoControlOutput:
        if (
            control_input.allowed_speed_kmh is None
            or not self.is_finite_number(control_input.allowed_speed_kmh)
            or float(control_input.allowed_speed_kmh) <= 0.0
        ):
            return self._degraded_output(control_input, "SM", "invalid_allowed_speed")

        safe_speed_limit_kmh = float(control_input.allowed_speed_kmh)
        control_position_m, control_speed_ms = self.compute_predicted_state(
            position_m=control_input.position_m,
            speed_ms=control_input.speed_ms,
            acceleration_ms2=control_input.acceleration_ms2,
            direction=control_input.direction,
            control_delay_sec=control_input.control_delay_sec,
            enabled=control_input.delay_compensation_enabled,
        )
        control_input_for_decision = self._replace_control_state(
            control_input, control_position_m, control_speed_ms
        )
        distance_to_ma_m = self._ma_context(control_input_for_decision)["distance_to_ma_m"]
        distance_to_stop_m = self._distance_to_stop(control_input_for_decision)
        recommended_speed_kmh = safe_speed_limit_kmh
        ato_state = "manual_recommend"

        if distance_to_stop_m is not None and distance_to_stop_m >= 0.0:
            recommended_speed_kmh = self._curve_target_speed_kmh(
                distance_to_stop_m, safe_speed_limit_kmh
            )
            if distance_to_stop_m <= self.POSITION_CONTROL_DISTANCE_M:
                low_speed_target_ms = self.compute_low_speed_target_ms(distance_to_stop_m)
                recommended_speed_kmh = min(
                    recommended_speed_kmh,
                    low_speed_target_ms * 3.6,
                )
            if distance_to_stop_m <= self.CREEP_DISTANCE_M:
                ato_state = "manual_creep_recommend"

        current_speed_kmh = self.ms_to_kmh(control_speed_ms)
        ato_traction_level, ato_brake_level = self._levels_for_speed_error(
            current_speed_kmh=current_speed_kmh,
            target_speed_kmh=recommended_speed_kmh,
        )
        ato_traction_level, ato_brake_level = self.resolve_exclusive_levels(
            ato_traction_level, ato_brake_level
        )

        return self._build_output(
            vehicle_id=control_input.vehicle_id,
            driving_mode="SM",
            ato_state=ato_state,
            ato_traction_level=ato_traction_level,
            ato_brake_level=ato_brake_level,
            commanded_traction_level=0,
            commanded_brake_level=0,
            control_source="manual",
            recommended_speed_kmh=round(recommended_speed_kmh, 3),
            ato_target_speed_kmh=round(recommended_speed_kmh, 3),
            safe_speed_limit_kmh=safe_speed_limit_kmh,
            stop_target_m=control_input.stop_target_m,
            effective_target_m=control_input.stop_target_m,
            distance_to_stop_m=distance_to_stop_m,
            distance_to_ma_m=distance_to_ma_m,
            holding_brake=False,
            degraded=False,
            reason="manual_recommendation_only",
        )

    def validate_ma_context(self, control_input: AtoControlInput) -> tuple[bool, str | None]:
        if control_input.ma_valid is False:
            return False, "ma_marked_invalid"
        if control_input.comm_ok is False:
            return False, "comm_unhealthy"
        if control_input.ma_age_sec is not None:
            if not self.is_finite_number(control_input.ma_age_sec):
                return False, "invalid_ma_age"
            if float(control_input.ma_age_sec) < 0.0:
                return False, "invalid_ma_age"
            if float(control_input.ma_age_sec) > float(control_input.max_ma_age_sec):
                return False, "ma_timeout"

        if control_input.ma_limit_m is None:
            return False, "missing_ma_limit"
        if not self.is_finite_number(control_input.ma_limit_m):
            return False, "invalid_ma_limit"
        if control_input.allowed_speed_kmh is None:
            return False, "missing_allowed_speed"
        if not self.is_finite_number(control_input.allowed_speed_kmh):
            return False, "invalid_allowed_speed"
        if float(control_input.allowed_speed_kmh) <= 0.0:
            return False, "invalid_allowed_speed"
        if float(control_input.ma_limit_m) <= float(control_input.position_m):
            return False, "ma_behind_train"

        if control_input.target_distance_m is not None:
            if not self.is_finite_number(control_input.target_distance_m):
                return False, "invalid_target_distance"
            if float(control_input.target_distance_m) < 0.0:
                return False, "negative_target_distance"

        permission = "" if control_input.permission is None else str(control_input.permission).lower()
        if permission in {"stop", "denied", "forbidden", "none"}:
            return False, "permission_denied"

        signal_state = "" if control_input.signal_state is None else str(control_input.signal_state).lower()
        if signal_state in {"red", "stop"}:
            return False, "signal_stop"

        return True, None

    def evaluate_stop_result(
        self,
        vehicle_id: str | None,
        target_position_m: float,
        actual_position_m: float,
        speed_ms: float,
    ) -> StopResult:
        error_m = float(actual_position_m) - float(target_position_m)
        if speed_ms > self.HOLD_SPEED_MS:
            status = "not_stopped"
            qualified = False
        elif abs(error_m) <= self.STOP_WINDOW_M:
            status = "in_window"
            qualified = True
        elif error_m > self.STOP_WINDOW_M:
            status = "overshoot"
            qualified = False
        else:
            status = "undershoot"
            qualified = False

        return StopResult(
            vehicle_id=vehicle_id,
            target_position_m=float(target_position_m),
            actual_position_m=float(actual_position_m),
            error_m=round(error_m, 3),
            error_cm=round(error_m * 100.0, 1),
            qualified=qualified,
            status=status,
            speed_ms=float(speed_ms),
        )

    def _curve_target_speed_kmh(self, distance_m: float, safe_speed_limit_kmh: float) -> float:
        decel = max(self.MIN_DECEL_MS2, min(self.COMFORT_DECEL_MS2, self.MAX_DECEL_MS2))
        target_speed_ms = math.sqrt(max(0.0, 2.0 * decel * max(0.0, distance_m)))
        return max(0.0, min(target_speed_ms * 3.6, float(safe_speed_limit_kmh)))

    def _levels_for_speed_error(
        self,
        current_speed_kmh: float,
        target_speed_kmh: float,
    ) -> tuple[int, int]:
        speed_error_kmh = current_speed_kmh - target_speed_kmh
        if speed_error_kmh > 10.0:
            return 0, 4
        if speed_error_kmh > 6.0:
            return 0, 3
        if speed_error_kmh > 3.0:
            return 0, 2
        if speed_error_kmh > self.SPEED_DEADBAND_KMH:
            return 0, 1

        if current_speed_kmh < target_speed_kmh - 3.0 and target_speed_kmh > 1.0:
            traction_level = 2 if target_speed_kmh - current_speed_kmh > 10.0 else 1
            return self.clamp_level(traction_level), 0

        return 0, 0

    def _levels_for_low_speed_error(
        self,
        current_speed_ms: float,
        target_speed_ms: float,
    ) -> tuple[int, int]:
        speed_error_ms = current_speed_ms - target_speed_ms
        if speed_error_ms > 0.8:
            return 0, 4
        if speed_error_ms > 0.45:
            return 0, 3
        if speed_error_ms > 0.25:
            return 0, 2
        if speed_error_ms > self.LOW_SPEED_DEADBAND_MS:
            return 0, 1

        if (
            current_speed_ms < target_speed_ms - 0.25
            and target_speed_ms > 0.3
        ):
            return 1, 0

        return 0, 0

    def _ma_context(self, control_input: AtoControlInput) -> dict:
        distance_from_absolute_ma = None
        effective_ma_limit_m = None
        if control_input.ma_limit_m is not None:
            distance_from_absolute_ma = max(
                0.0,
                float(control_input.ma_limit_m) - float(control_input.position_m),
            )
            effective_ma_limit_m = float(control_input.ma_limit_m)

        if control_input.target_distance_m is not None:
            target_distance_m = float(control_input.target_distance_m)
            if distance_from_absolute_ma is None:
                distance_to_ma_m = target_distance_m
            else:
                distance_to_ma_m = min(distance_from_absolute_ma, target_distance_m)
            effective_ma_limit_m = float(control_input.position_m) + distance_to_ma_m
        else:
            distance_to_ma_m = distance_from_absolute_ma

        return {
            "distance_to_ma_m": distance_to_ma_m,
            "effective_ma_limit_m": effective_ma_limit_m,
        }

    def _distance_to_stop(self, control_input: AtoControlInput) -> float | None:
        if control_input.stop_target_m is None:
            return None
        return float(control_input.stop_target_m) - float(control_input.position_m)

    def _finite_or_default(self, value, default: float) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        return value if math.isfinite(value) else default

    def _normalized_delay(self, control_delay_sec) -> float:
        delay = self._finite_or_default(control_delay_sec, 0.0)
        return max(0.0, min(delay, self.MAX_CONTROL_DELAY_SEC))

    def _is_reverse_direction(self, direction) -> bool:
        if isinstance(direction, str):
            return direction.strip().lower() in {"backward", "reverse", "-1"}
        try:
            return int(direction) == -1
        except (TypeError, ValueError):
            return False

    def _replace_control_state(
        self,
        control_input: AtoControlInput,
        position_m: float,
        speed_ms: float,
    ) -> AtoControlInput:
        return AtoControlInput(
            **{
                **control_input.__dict__,
                "position_m": position_m,
                "speed_ms": speed_ms,
            }
        )

    def _more_conservative_distance(self, actual_distance, predicted_distance):
        if actual_distance is None:
            return predicted_distance
        if predicted_distance is None:
            return actual_distance
        return min(actual_distance, predicted_distance)

    def _degraded_output(
        self,
        control_input: AtoControlInput,
        driving_mode: str,
        reason: str,
    ) -> AtoControlOutput:
        distance_to_ma_m = self._ma_context(control_input)["distance_to_ma_m"]
        brake_level = 2 if driving_mode == "AM" else 0
        return self._build_output(
            vehicle_id=control_input.vehicle_id,
            driving_mode=driving_mode,
            ato_state="degraded",
            ato_traction_level=0,
            ato_brake_level=brake_level,
            commanded_traction_level=0,
            commanded_brake_level=brake_level,
            control_source="degraded",
            recommended_speed_kmh=0.0,
            ato_target_speed_kmh=0.0,
            safe_speed_limit_kmh=0.0,
            stop_target_m=control_input.stop_target_m,
            effective_target_m=None,
            distance_to_stop_m=self._distance_to_stop(control_input),
            distance_to_ma_m=distance_to_ma_m,
            holding_brake=False,
            degraded=True,
            reason=reason,
        )

    def _build_output(
        self,
        *,
        vehicle_id,
        driving_mode,
        ato_state,
        ato_traction_level,
        ato_brake_level,
        commanded_traction_level,
        commanded_brake_level,
        control_source,
        recommended_speed_kmh,
        ato_target_speed_kmh,
        safe_speed_limit_kmh,
        stop_target_m,
        effective_target_m,
        distance_to_stop_m,
        distance_to_ma_m,
        holding_brake,
        degraded,
        reason,
    ) -> AtoControlOutput:
        ato_traction_level, ato_brake_level = self.resolve_exclusive_levels(
            ato_traction_level, ato_brake_level
        )
        commanded_traction_level, commanded_brake_level = self.resolve_exclusive_levels(
            commanded_traction_level, commanded_brake_level
        )
        applied_traction_level, applied_brake_level = commanded_traction_level, commanded_brake_level

        return AtoControlOutput(
            vehicle_id=vehicle_id,
            driving_mode=driving_mode,
            ato_state=ato_state,
            ato_traction_level=ato_traction_level,
            ato_brake_level=ato_brake_level,
            commanded_traction_level=commanded_traction_level,
            commanded_brake_level=commanded_brake_level,
            applied_traction_level=applied_traction_level,
            applied_brake_level=applied_brake_level,
            control_source=control_source,
            atp_intervened=False,
            recommended_speed_kmh=recommended_speed_kmh,
            ato_target_speed_kmh=ato_target_speed_kmh,
            safe_speed_limit_kmh=safe_speed_limit_kmh,
            stop_target_m=stop_target_m,
            effective_target_m=effective_target_m,
            distance_to_stop_m=distance_to_stop_m,
            distance_to_ma_m=distance_to_ma_m,
            holding_brake=holding_brake,
            degraded=degraded,
            reason=reason,
        )
