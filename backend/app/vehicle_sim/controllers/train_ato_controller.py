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
    gradient_permille: float = 0.0
    gradient_compensation_enabled: bool = False
    previous_commanded_traction_level: int = 0
    previous_commanded_brake_level: int = 0
    jerk_limit_enabled: bool = False
    brake_bias: float = 1.0
    brake_bias_enabled: bool = False


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
    HOLD_DISTANCE_M = 0.35
    HOLD_SPEED_MS = 0.15
    CRAWL_SPEED_MS = 0.5
    POSITION_CONTROL_DISTANCE_M = 12.0
    POSITION_KP = 0.28
    MIN_CREEP_SPEED_MS = 0.12
    LOW_SPEED_DEADBAND_MS = 0.08
    STATIC_CREEP_START_SPEED_MS = 0.05
    STATIC_CREEP_TRACTION_LEVEL = 2
    COMFORT_DECEL_MS2 = 0.65
    MIN_DECEL_MS2 = 0.2
    MAX_DECEL_MS2 = 0.9
    SPEED_DEADBAND_KMH = 1.0
    DEFAULT_CONTROL_DELAY_SEC = 0.3
    MAX_CONTROL_DELAY_SEC = 1.0
    GRAVITY_MS2 = 9.81
    MAX_GRADIENT_PERMILLE = 60.0
    MIN_EFFECTIVE_DECEL_MS2 = 0.25
    MAX_EFFECTIVE_DECEL_MS2 = 1.1
    DEFAULT_BRAKE_BIAS = 1.0
    MIN_BRAKE_BIAS = 0.7
    MAX_BRAKE_BIAS = 1.5
    MAX_BRAKE_STEP_UP_PER_TICK = 1
    MAX_BRAKE_STEP_DOWN_PER_TICK = 1
    MAX_TRACTION_STEP_UP_PER_TICK = 1
    MAX_TRACTION_STEP_DOWN_PER_TICK = 1
    JERK_BYPASS_REASONS = {
        "missing_ma_limit",
        "missing_allowed_speed",
        "invalid_allowed_speed",
        "ma_behind_train",
        "permission_denied",
        "signal_stop",
        "comm_unhealthy",
        "ma_timeout",
        "negative_target_distance",
        "predicted_ma_overrun",
    }

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

    def smooth_command_levels(
        self,
        target_traction_level: int,
        target_brake_level: int,
        previous_traction_level: int,
        previous_brake_level: int,
        enabled: bool,
        bypass: bool = False,
    ) -> tuple[int, int]:
        target_traction_level, target_brake_level = self.resolve_exclusive_levels(
            target_traction_level,
            target_brake_level,
        )
        previous_traction_level, previous_brake_level = self.resolve_exclusive_levels(
            previous_traction_level,
            previous_brake_level,
        )
        if not enabled or bypass:
            return target_traction_level, target_brake_level

        if target_brake_level > 0:
            brake_level = self._step_level_toward(
                previous_brake_level,
                target_brake_level,
                self.MAX_BRAKE_STEP_UP_PER_TICK,
                self.MAX_BRAKE_STEP_DOWN_PER_TICK,
            )
            return self.resolve_exclusive_levels(0, brake_level)

        if target_traction_level > 0:
            if previous_brake_level > 0:
                brake_level = self._step_level_toward(
                    previous_brake_level,
                    0,
                    self.MAX_BRAKE_STEP_UP_PER_TICK,
                    self.MAX_BRAKE_STEP_DOWN_PER_TICK,
                )
                return self.resolve_exclusive_levels(0, brake_level)
            traction_level = self._step_level_toward(
                previous_traction_level,
                target_traction_level,
                self.MAX_TRACTION_STEP_UP_PER_TICK,
                self.MAX_TRACTION_STEP_DOWN_PER_TICK,
            )
            return self.resolve_exclusive_levels(traction_level, 0)

        brake_level = self._step_level_toward(
            previous_brake_level,
            0,
            self.MAX_BRAKE_STEP_UP_PER_TICK,
            self.MAX_BRAKE_STEP_DOWN_PER_TICK,
        )
        traction_level = 0
        if brake_level == 0:
            traction_level = self._step_level_toward(
                previous_traction_level,
                0,
                self.MAX_TRACTION_STEP_UP_PER_TICK,
                self.MAX_TRACTION_STEP_DOWN_PER_TICK,
            )
        return self.resolve_exclusive_levels(traction_level, brake_level)

    def should_bypass_jerk_limit(
        self,
        *,
        ato_state: str,
        degraded: bool,
        reason: str | None,
        distance_to_stop_m: float | None,
        distance_to_ma_m: float | None,
        target_brake_level: int,
        current_speed_kmh: float,
        target_speed_kmh: float,
    ) -> bool:
        if ato_state == "holding" or degraded:
            return True
        if reason in self.JERK_BYPASS_REASONS:
            return True
        if distance_to_stop_m is not None and distance_to_stop_m < 0.0:
            return True
        if distance_to_ma_m is not None and distance_to_ma_m <= self.HOLD_DISTANCE_M:
            return True
        return target_brake_level == self.MAX_LEVEL and (
            current_speed_kmh - target_speed_kmh
        ) > 25.0

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

    def compute_gradient_adjusted_decel(
        self,
        base_decel_ms2: float,
        gradient_permille: float,
        enabled: bool,
    ) -> float:
        base_decel_ms2 = self._finite_or_default(
            base_decel_ms2, self.COMFORT_DECEL_MS2
        )
        if not enabled:
            return base_decel_ms2

        gradient_permille = self._finite_or_default(gradient_permille, 0.0)
        gradient_permille = max(
            -self.MAX_GRADIENT_PERMILLE,
            min(self.MAX_GRADIENT_PERMILLE, gradient_permille),
        )
        gradient_acc_ms2 = self.GRAVITY_MS2 * gradient_permille / 1000.0
        effective_decel_ms2 = base_decel_ms2 + gradient_acc_ms2
        return max(
            self.MIN_EFFECTIVE_DECEL_MS2,
            min(self.MAX_EFFECTIVE_DECEL_MS2, effective_decel_ms2),
        )

    def normalize_brake_bias(self, brake_bias: float, enabled: bool) -> float:
        if not enabled:
            return self.DEFAULT_BRAKE_BIAS
        if not self.is_finite_number(brake_bias):
            return self.DEFAULT_BRAKE_BIAS
        brake_bias = float(brake_bias)
        return max(self.MIN_BRAKE_BIAS, min(self.MAX_BRAKE_BIAS, brake_bias))

    def apply_brake_bias_to_decel(
        self,
        effective_decel_ms2: float,
        brake_bias: float,
    ) -> float:
        effective_decel_ms2 = self._finite_or_default(
            effective_decel_ms2, self.COMFORT_DECEL_MS2
        )
        brake_bias = self.normalize_brake_bias(brake_bias, enabled=True)
        biased_decel_ms2 = effective_decel_ms2 / brake_bias
        return max(
            self.MIN_EFFECTIVE_DECEL_MS2,
            min(self.MAX_EFFECTIVE_DECEL_MS2, biased_decel_ms2),
        )

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
        effective_decel_ms2 = self.compute_gradient_adjusted_decel(
            base_decel_ms2=self.COMFORT_DECEL_MS2,
            gradient_permille=control_input.gradient_permille,
            enabled=control_input.gradient_compensation_enabled,
        )
        brake_bias = self.normalize_brake_bias(
            control_input.brake_bias,
            control_input.brake_bias_enabled,
        )
        effective_decel_ms2 = self.apply_brake_bias_to_decel(
            effective_decel_ms2,
            brake_bias,
        )
        stop_target_m = control_input.stop_target_m
        actual_distance_to_stop_m = self._distance_to_stop(control_input)
        predicted_distance_to_stop_m = self._distance_to_stop(control_input_for_decision)
        distance_to_stop_m = self._more_conservative_distance(
            actual_distance_to_stop_m,
            predicted_distance_to_stop_m,
        )
        direction_sign = self._direction_sign(control_input_for_decision.direction)
        if distance_to_ma_m is not None and distance_to_ma_m <= 0.0:
            return self._degraded_output(
                control_input_for_decision,
                "AM",
                "predicted_ma_overrun",
            )
        stop_target_within_ma = False
        if (
            stop_target_m is not None
            and ma_context["effective_ma_limit_m"] is not None
        ):
            stop_target_within_ma = (
                (ma_context["effective_ma_limit_m"] - float(stop_target_m))
                * direction_sign
            ) >= -1e-6
        stop_target_is_safe = (
            stop_target_m is not None
            and distance_to_stop_m is not None
            and distance_to_stop_m >= 0.0
            and stop_target_within_ma
        )

        effective_target_m = (
            stop_target_m if stop_target_is_safe else ma_context["effective_ma_limit_m"]
        )
        effective_distance_m = max(
            0.0,
            (float(effective_target_m) - control_position_m) * direction_sign,
        )

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
            effective_distance_m,
            self._tracking_speed_limit_kmh(safe_speed_limit_kmh),
            effective_decel_ms2,
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
                distance_to_stop_m=distance_to_stop_m,
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
        traction_level, brake_level = self._apply_speed_limit_guard(
            current_speed_kmh=self.ms_to_kmh(control_speed_ms),
            safe_speed_limit_kmh=safe_speed_limit_kmh,
            traction_level=traction_level,
            brake_level=brake_level,
        )
        if brake_level > 0 and ato_state != "creep":
            ato_state = "braking_to_stop"

        reason = "normal"
        if (
            control_input.stop_target_m is not None
            and ma_context["effective_ma_limit_m"] is not None
            and (
                (ma_context["effective_ma_limit_m"] - float(control_input.stop_target_m))
                * direction_sign
            )
            < -1e-6
        ):
            reason = "stop_target_beyond_ma"
        elif distance_to_stop_m is not None and distance_to_stop_m < 0.0:
            reason = "stop_target_behind_train"

        current_speed_kmh = self.ms_to_kmh(control_speed_ms)
        bypass_jerk_limit = self.should_bypass_jerk_limit(
            ato_state=ato_state,
            degraded=False,
            reason=reason,
            distance_to_stop_m=distance_to_stop_m,
            distance_to_ma_m=distance_to_ma_m,
            target_brake_level=brake_level,
            current_speed_kmh=current_speed_kmh,
            target_speed_kmh=target_speed_kmh,
        )
        commanded_traction_level, commanded_brake_level = self.smooth_command_levels(
            target_traction_level=traction_level,
            target_brake_level=brake_level,
            previous_traction_level=control_input.previous_commanded_traction_level,
            previous_brake_level=control_input.previous_commanded_brake_level,
            enabled=control_input.jerk_limit_enabled,
            bypass=bypass_jerk_limit,
        )

        return self._build_output(
            vehicle_id=control_input.vehicle_id,
            driving_mode="AM",
            ato_state=ato_state,
            ato_traction_level=traction_level,
            ato_brake_level=brake_level,
            commanded_traction_level=commanded_traction_level,
            commanded_brake_level=commanded_brake_level,
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
        effective_decel_ms2 = self.compute_gradient_adjusted_decel(
            base_decel_ms2=self.COMFORT_DECEL_MS2,
            gradient_permille=control_input.gradient_permille,
            enabled=control_input.gradient_compensation_enabled,
        )
        brake_bias = self.normalize_brake_bias(
            control_input.brake_bias,
            control_input.brake_bias_enabled,
        )
        effective_decel_ms2 = self.apply_brake_bias_to_decel(
            effective_decel_ms2,
            brake_bias,
        )

        if distance_to_stop_m is not None and distance_to_stop_m >= 0.0:
            recommended_speed_kmh = self._curve_target_speed_kmh(
                distance_to_stop_m,
                safe_speed_limit_kmh,
                effective_decel_ms2,
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
            if self._is_reverse_direction(control_input.direction) and float(
                control_input.ma_limit_m
            ) < float(control_input.position_m):
                pass
            else:
                return False, "ma_behind_train"
        if self._is_reverse_direction(control_input.direction) and float(
            control_input.ma_limit_m
        ) >= float(control_input.position_m):
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

    def _curve_target_speed_kmh(
        self,
        distance_m: float,
        safe_speed_limit_kmh: float,
        deceleration_ms2: float | None = None,
    ) -> float:
        if deceleration_ms2 is None:
            decel = max(
                self.MIN_DECEL_MS2,
                min(self.COMFORT_DECEL_MS2, self.MAX_DECEL_MS2),
            )
        else:
            decel = max(
                0.001,
                self._finite_or_default(deceleration_ms2, self.COMFORT_DECEL_MS2),
            )
        target_speed_ms = math.sqrt(max(0.0, 2.0 * decel * max(0.0, distance_m)))
        return max(0.0, min(target_speed_ms * 3.6, float(safe_speed_limit_kmh)))

    def _step_level_toward(
        self,
        current_level: int,
        target_level: int,
        step_up: int,
        step_down: int,
    ) -> int:
        current_level = self.clamp_level(current_level)
        target_level = self.clamp_level(target_level)
        if target_level > current_level:
            return min(target_level, current_level + max(0, int(step_up)))
        if target_level < current_level:
            return max(target_level, current_level - max(0, int(step_down)))
        return current_level

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

        underspeed_kmh = target_speed_kmh - current_speed_kmh
        if underspeed_kmh > 3.0 and target_speed_kmh > 1.0:
            if underspeed_kmh > 25.0:
                traction_level = 4
            elif underspeed_kmh > 15.0:
                traction_level = 3
            elif underspeed_kmh > 6.0:
                traction_level = 2
            else:
                traction_level = 1
            return self.clamp_level(traction_level), 0

        return 0, 0

    def _apply_speed_limit_guard(
        self,
        *,
        current_speed_kmh: float,
        safe_speed_limit_kmh: float,
        traction_level: int,
        brake_level: int,
    ) -> tuple[int, int]:
        """Prevent ATO from relying on ATP emergency braking for speed limits."""

        if not self.is_finite_number(safe_speed_limit_kmh) or safe_speed_limit_kmh <= 0.0:
            return self.resolve_exclusive_levels(0, max(brake_level, 2))
        overspeed_kmh = current_speed_kmh - safe_speed_limit_kmh
        if overspeed_kmh > 4.0:
            return 0, 4
        if overspeed_kmh > 2.0:
            return 0, max(brake_level, 3)
        if overspeed_kmh > 0.5:
            return 0, max(brake_level, 2)
        if overspeed_kmh > -1.0:
            return 0, max(brake_level, 1)
        if current_speed_kmh >= safe_speed_limit_kmh - 5.0:
            return 0, brake_level
        return self.resolve_exclusive_levels(traction_level, brake_level)

    def _tracking_speed_limit_kmh(self, safe_speed_limit_kmh: float) -> float:
        if not self.is_finite_number(safe_speed_limit_kmh):
            return 0.0
        safe_speed_limit_kmh = max(0.0, float(safe_speed_limit_kmh))
        margin = min(5.0, safe_speed_limit_kmh * 0.2)
        return max(0.0, safe_speed_limit_kmh - margin)

    def _levels_for_low_speed_error(
        self,
        current_speed_ms: float,
        target_speed_ms: float,
        distance_to_stop_m: float | None = None,
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
            distance_to_stop_m is not None
            and self.HOLD_DISTANCE_M < distance_to_stop_m <= self.CREEP_DISTANCE_M
            and current_speed_ms <= self.STATIC_CREEP_START_SPEED_MS
        ):
            return self.STATIC_CREEP_TRACTION_LEVEL, 0

        if (
            current_speed_ms < target_speed_ms - 0.25
            and target_speed_ms > self.MIN_CREEP_SPEED_MS
        ):
            if current_speed_ms <= self.STATIC_CREEP_START_SPEED_MS:
                return self.STATIC_CREEP_TRACTION_LEVEL, 0
            return 1, 0

        return 0, 0

    def _ma_context(self, control_input: AtoControlInput) -> dict:
        distance_from_absolute_ma = None
        effective_ma_limit_m = None
        direction_sign = self._direction_sign(control_input.direction)
        if control_input.ma_limit_m is not None:
            distance_from_absolute_ma = max(
                0.0,
                (float(control_input.ma_limit_m) - float(control_input.position_m))
                * direction_sign,
            )
            effective_ma_limit_m = float(control_input.ma_limit_m)

        if control_input.target_distance_m is not None:
            target_distance_m = float(control_input.target_distance_m)
            if distance_from_absolute_ma is None:
                distance_to_ma_m = target_distance_m
            else:
                distance_to_ma_m = min(distance_from_absolute_ma, target_distance_m)
            effective_ma_limit_m = (
                float(control_input.position_m) + distance_to_ma_m * direction_sign
            )
        else:
            distance_to_ma_m = distance_from_absolute_ma

        return {
            "distance_to_ma_m": distance_to_ma_m,
            "effective_ma_limit_m": effective_ma_limit_m,
        }

    def _distance_to_stop(self, control_input: AtoControlInput) -> float | None:
        if control_input.stop_target_m is None:
            return None
        return (
            float(control_input.stop_target_m) - float(control_input.position_m)
        ) * self._direction_sign(control_input.direction)

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
            return direction.strip().lower() in {
                "backward",
                "reverse",
                "down",
                "-1",
                "2",
                "0xaa",
                "aa",
            }
        try:
            return int(direction) in {-1, 2, 0xAA}
        except (TypeError, ValueError):
            return False

    def _direction_sign(self, direction) -> int:
        return -1 if self._is_reverse_direction(direction) else 1

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
