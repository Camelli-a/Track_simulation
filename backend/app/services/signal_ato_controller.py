from copy import deepcopy
import math

from app.services.signal_gradient import (
    calculate_effective_deceleration,
    find_gradient_at_position,
)
from app.services.signal_track_config import STOP_TARGETS


def kmh_to_mps(speed_kmh: float) -> float:
    return float(speed_kmh) / 3.6


def mps_to_kmh(speed_mps: float) -> float:
    return float(speed_mps) * 3.6


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def find_next_stop_target(train_state: dict, stop_targets=None) -> dict | None:
    targets = stop_targets if stop_targets is not None else STOP_TARGETS
    route_id = train_state.get("route_id")
    current_position = _to_float(train_state.get("position"), 0.0)
    matching_targets = []
    for target in targets:
        if target.get("route_id") != route_id:
            continue
        target_position = _to_float(target.get("position"), 0.0)
        if target_position >= current_position:
            matching_targets.append(deepcopy(target))

    if not matching_targets:
        return None

    return min(
        matching_targets,
        key=lambda item: _to_float(item.get("position"), 0.0) - current_position,
    )


def calculate_stop_curve_speed_limit(distance_to_target: float, deceleration: float = 0.8) -> float:
    distance = _to_float(distance_to_target, 0.0)
    deceleration = _to_float(deceleration, 0.0)
    if distance <= 0 or deceleration <= 0:
        return 0.0
    return round(mps_to_kmh(math.sqrt(2 * deceleration * distance)), 1)


def control_value_to_levels(control_value: float) -> tuple[int, int]:
    value = _to_float(control_value, 0.0)
    if value > 0:
        return _value_to_level(value), 0
    if value < 0:
        return 0, _value_to_level(abs(value))
    return 0, 0


class AtoStrategyOptimizer:
    WEIGHTS = {
        "approach_station": {"stop": 0.25, "comfort": 0.30, "energy": 0.20, "efficiency": 0.25},
        "braking_to_stop": {"stop": 0.40, "comfort": 0.30, "energy": 0.15, "efficiency": 0.15},
        "creep": {"stop": 0.65, "comfort": 0.20, "energy": 0.10, "efficiency": 0.05},
        "cruise": {"stop": 0.05, "comfort": 0.25, "energy": 0.35, "efficiency": 0.35},
    }
    TIE_BREAK_PRIORITY = {
        "precise_stop": 0,
        "comfort_brake": 1,
        "energy_saving": 2,
        "conservative_brake": 3,
    }
    STRATEGY_BIAS = {
        "cruise": {
            "energy_saving": 0.20,
            "comfort_brake": 0.05,
            "conservative_brake": -0.10,
            "precise_stop": -0.20,
        },
        "approach_station": {
            "comfort_brake": 0.16,
            "energy_saving": 0.05,
            "conservative_brake": -0.08,
            "precise_stop": -0.15,
        },
        "braking_to_stop": {
            "comfort_brake": 0.08,
            "conservative_brake": 0.03,
            "energy_saving": -0.05,
        },
        "creep": {
            "precise_stop": 0.25,
            "energy_saving": -0.20,
        },
    }

    def generate_candidate_strategies(
        self,
        *,
        safe_speed_limit: float,
        stop_curve_speed_limit: float,
        current_speed: float,
        distance_to_target: float | None,
        approach_distance: float | None,
        ato_state: str,
        creep_speed_limit: float = 5.0,
    ) -> list[dict]:
        del distance_to_target, approach_distance, ato_state
        safe_limit = max(_to_float(safe_speed_limit), 0.0)
        curve_limit = max(_to_float(stop_curve_speed_limit), 0.0)
        current_speed = max(_to_float(current_speed), 0.0)
        raw_candidates = [
            ("conservative_brake", curve_limit * 0.75, "Earlier braking with a lower target speed."),
            ("comfort_brake", curve_limit * 0.90, "Balanced, smooth braking for station approach."),
            ("energy_saving", max(curve_limit * 0.95, current_speed * 0.90), "Coast-oriented target."),
            ("precise_stop", min(curve_limit * 0.55, creep_speed_limit), "Low-speed target for stopping accuracy."),
        ]
        candidates = []
        for strategy, target_speed, description in raw_candidates:
            target_speed = min(target_speed, safe_limit, curve_limit)
            candidates.append(
                {
                    "strategy": strategy,
                    "target_speed": round(max(target_speed, 0.0), 1),
                    "description": description,
                }
            )
        return candidates

    def score_strategy(self, candidate: dict, context: dict) -> dict:
        target_speed = max(_to_float(candidate.get("target_speed")), 0.0)
        safe_speed_limit = max(_to_float(context.get("safe_speed_limit")), 0.0)
        stop_curve_speed_limit = max(_to_float(context.get("stop_curve_speed_limit")), 0.0)
        current_speed = max(_to_float(context.get("current_speed")), 0.0)
        distance_to_target = context.get("distance_to_target")
        distance_to_target = None if distance_to_target is None else max(_to_float(distance_to_target), 0.0)
        approach_distance = max(_to_float(context.get("approach_distance"), 600.0), 1.0)
        ato_state = context.get("ato_state", "cruise")
        weights = self.WEIGHTS.get(ato_state, self.WEIGHTS["cruise"])

        proximity = 0.0
        if distance_to_target is not None:
            proximity = clamp(1.0 - distance_to_target / approach_distance, 0.0, 1.0)
        low_speed_score = 1.0 - self._ratio(target_speed, max(stop_curve_speed_limit, 1.0))
        curve_score = 1.0 - abs(target_speed - stop_curve_speed_limit) / max(stop_curve_speed_limit, 1.0)
        stop_accuracy_score = clamp(proximity * low_speed_score + (1.0 - proximity) * curve_score, 0.0, 1.0)
        comfort_score = clamp(1.0 - abs(target_speed - current_speed) / max(safe_speed_limit, current_speed, 1.0), 0.0, 1.0)
        energy_score = comfort_score
        efficiency_score = clamp(self._ratio(target_speed, max(safe_speed_limit, 1.0)), 0.0, 1.0)
        overspeed_penalty = 1.0 if target_speed > safe_speed_limit else 0.0
        ma_violation_penalty = 1.0 if safe_speed_limit <= 0 or stop_curve_speed_limit < 0 else 0.0
        score = (
            weights["stop"] * stop_accuracy_score
            + weights["comfort"] * comfort_score
            + weights["energy"] * energy_score
            + weights["efficiency"] * efficiency_score
            - 5.0 * overspeed_penalty
            - 5.0 * ma_violation_penalty
        )
        score += self.STRATEGY_BIAS.get(ato_state, {}).get(candidate.get("strategy"), 0.0)
        return {
            "strategy": candidate.get("strategy"),
            "target_speed": target_speed,
            "score": round(clamp(score, -10.0, 1.0), 3),
        }

    def select_strategy(self, candidates: list[dict], context: dict) -> dict:
        strategy_scores = [self.score_strategy(candidate, context) for candidate in candidates]
        selected = max(
            strategy_scores,
            key=lambda item: (item["score"], -self.TIE_BREAK_PRIORITY.get(item["strategy"], 99)),
        )
        return {
            "selected_strategy": selected["strategy"],
            "score": selected["score"],
            "target_speed": selected["target_speed"],
            "strategy_scores": strategy_scores,
            "reason": "strategy_optimized",
        }

    def optimize(
        self,
        *,
        safe_speed_limit: float,
        stop_curve_speed_limit: float,
        current_speed: float,
        distance_to_target: float | None,
        approach_distance: float | None,
        ato_state: str,
        creep_speed_limit: float = 5.0,
    ) -> dict:
        context = {
            "safe_speed_limit": safe_speed_limit,
            "stop_curve_speed_limit": stop_curve_speed_limit,
            "current_speed": current_speed,
            "distance_to_target": distance_to_target,
            "approach_distance": approach_distance,
            "ato_state": ato_state,
        }
        candidates = self.generate_candidate_strategies(
            safe_speed_limit=safe_speed_limit,
            stop_curve_speed_limit=stop_curve_speed_limit,
            current_speed=current_speed,
            distance_to_target=distance_to_target,
            approach_distance=approach_distance,
            ato_state=ato_state,
            creep_speed_limit=creep_speed_limit,
        )
        return self.select_strategy(candidates, context)

    def _ratio(self, value: float, denominator: float) -> float:
        if denominator <= 0:
            return 0.0
        return value / denominator


class PIDController:
    def __init__(
        self,
        kp=2.0,
        ki=0.1,
        kd=0.05,
        output_min=-100.0,
        output_max=100.0,
        integral_min=-100.0,
        integral_max=100.0,
        deadband=0.3,
    ):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_min = integral_min
        self.integral_max = integral_max
        self.deadband = deadband
        self.integral = 0.0
        self.previous_error = None

    def reset(self) -> None:
        self.integral = 0.0
        self.previous_error = None

    def update(self, target_speed: float, current_speed: float, dt: float = 0.25) -> float:
        dt = _to_float(dt, 0.25)
        if dt <= 0:
            dt = 0.25

        error = _to_float(target_speed, 0.0) - _to_float(current_speed, 0.0)
        if abs(error) < self.deadband:
            self.previous_error = error
            return 0.0

        self.integral = clamp(
            self.integral + error * dt,
            self.integral_min,
            self.integral_max,
        )
        derivative = 0.0 if self.previous_error is None else (error - self.previous_error) / dt
        self.previous_error = error

        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        return round(clamp(output, self.output_min, self.output_max), 3)


class AtoController:
    def __init__(
        self,
        stop_targets=None,
        pid_controller_factory=None,
        strategy_optimizer=None,
        gradient_profile=None,
        low_speed_threshold=0.5,
        creep_speed_limit=5.0,
        stop_deceleration=0.8,
    ):
        self.stop_targets = stop_targets if stop_targets is not None else STOP_TARGETS
        self.pid_controller_factory = pid_controller_factory or PIDController
        self.strategy_optimizer = strategy_optimizer or AtoStrategyOptimizer()
        self.gradient_profile = gradient_profile
        self.low_speed_threshold = low_speed_threshold
        self.creep_speed_limit = creep_speed_limit
        self.stop_deceleration = stop_deceleration
        self.pid_controllers_by_vehicle = {}

    def build_ato_commands(
        self,
        train_states: list[dict],
        ma_limits: list[dict],
        route_states: list[dict] | None = None,
    ) -> list[dict]:
        ma_limit_by_vehicle_id = {
            item.get("vehicle_id"): item
            for item in ma_limits
            if item.get("vehicle_id") is not None
        }
        route_state_by_vehicle_id = {
            item.get("vehicle_id"): item
            for item in (route_states or [])
            if item.get("vehicle_id") is not None
        }

        commands = []
        for train_state in train_states:
            vehicle_id = train_state.get("vehicle_id")
            ma_limit = ma_limit_by_vehicle_id.get(vehicle_id)
            if ma_limit is None:
                commands.append(self._degraded_command(train_state, reason="missing_ma_limit"))
                continue
            commands.append(
                self.build_ato_command_for_train(
                    train_state,
                    ma_limit,
                    route_state_by_vehicle_id.get(vehicle_id),
                )
            )
        return commands

    def build_ato_command_for_train(
        self,
        train_state: dict,
        ma_limit: dict,
        route_state: dict | None = None,
    ) -> dict:
        del route_state
        vehicle_id = train_state.get("vehicle_id")
        current_position = _to_float(train_state.get("position"), 0.0)
        current_speed = _to_float(train_state.get("speed"), 0.0)
        safe_speed_limit = max(_to_float(ma_limit.get("speed_limit"), 0.0), 0.0)
        gradient_info, effective_deceleration = self._gradient_context(current_position)

        if ma_limit.get("permission") == "stop" or safe_speed_limit <= 0:
            return self._degraded_command(
                train_state,
                ma_limit=ma_limit,
                reason=ma_limit.get("reason") or "signal_stop",
                safe_speed_limit=safe_speed_limit,
                gradient_info=gradient_info,
                effective_deceleration=effective_deceleration,
            )

        stop_target = find_next_stop_target(train_state, self.stop_targets)
        if stop_target is None:
            stop_target = self._nearest_stop_target_on_route(train_state)
        if stop_target is None:
            return self._command_with_pid(
                train_state=train_state,
                ma_limit=ma_limit,
                ato_state="cruise",
                target_speed=safe_speed_limit,
                safe_speed_limit=safe_speed_limit,
                stop_curve_speed_limit=safe_speed_limit,
                stop_target=None,
                distance_to_target=None,
                holding_brake=False,
                reason="no_stop_target",
                selected_strategy="cruise",
                strategy_scores=[],
                gradient_info=gradient_info,
                effective_deceleration=effective_deceleration,
            )

        target_position = _to_float(stop_target.get("position"), 0.0)
        distance_to_target = target_position - current_position
        window_before = _to_float(stop_target.get("window_before"), 0.5)
        window_after = _to_float(stop_target.get("window_after"), 0.5)
        stop_window_half_width = max(window_before, window_after)
        approach_distance = _to_float(stop_target.get("approach_distance"), 600.0)

        if distance_to_target < -window_after:
            return self._degraded_command(
                train_state,
                ma_limit=ma_limit,
                stop_target=stop_target,
                distance_to_target=distance_to_target,
                reason="overshoot",
                safe_speed_limit=safe_speed_limit,
                gradient_info=gradient_info,
                effective_deceleration=effective_deceleration,
            )

        if abs(distance_to_target) <= stop_window_half_width and current_speed <= self.low_speed_threshold:
            return self._base_command(
                train_state=train_state,
                ma_limit=ma_limit,
                ato_state="holding",
                target_speed=0.0,
                safe_speed_limit=safe_speed_limit,
                stop_curve_speed_limit=0.0,
                stop_target=stop_target,
                distance_to_target=distance_to_target,
                traction_level=0,
                brake_level=0,
                holding_brake=True,
                reason="stopped_in_window",
                selected_strategy="holding",
                strategy_scores=[],
                gradient_info=gradient_info,
                effective_deceleration=effective_deceleration,
            )

        if 0 <= distance_to_target <= 5.0:
            stop_curve_speed_limit = min(self.creep_speed_limit, safe_speed_limit)
            return self._command_with_pid(
                train_state=train_state,
                ma_limit=ma_limit,
                ato_state="creep",
                target_speed=stop_curve_speed_limit,
                safe_speed_limit=safe_speed_limit,
                stop_curve_speed_limit=stop_curve_speed_limit,
                stop_target=stop_target,
                distance_to_target=distance_to_target,
                holding_brake=False,
                reason="creep_to_stop",
                optimize_context={
                    "safe_speed_limit": safe_speed_limit,
                    "stop_curve_speed_limit": stop_curve_speed_limit,
                    "current_speed": current_speed,
                    "distance_to_target": distance_to_target,
                    "approach_distance": approach_distance,
                    "ato_state": "creep",
                },
                gradient_info=gradient_info,
                effective_deceleration=effective_deceleration,
            )

        if 5.0 < distance_to_target <= approach_distance:
            stop_curve_speed_limit = calculate_stop_curve_speed_limit(
                distance_to_target,
                effective_deceleration,
            )
            target_speed = min(safe_speed_limit, stop_curve_speed_limit)
            ato_state = "braking_to_stop" if target_speed < current_speed else "approach_station"
            reason = "stop_curve_braking" if ato_state == "braking_to_stop" else "approaching_station"
            return self._command_with_pid(
                train_state=train_state,
                ma_limit=ma_limit,
                ato_state=ato_state,
                target_speed=target_speed,
                safe_speed_limit=safe_speed_limit,
                stop_curve_speed_limit=stop_curve_speed_limit,
                stop_target=stop_target,
                distance_to_target=distance_to_target,
                holding_brake=False,
                reason=reason,
                optimize_context={
                    "safe_speed_limit": safe_speed_limit,
                    "stop_curve_speed_limit": stop_curve_speed_limit,
                    "current_speed": current_speed,
                    "distance_to_target": distance_to_target,
                    "approach_distance": approach_distance,
                    "ato_state": ato_state,
                },
                gradient_info=gradient_info,
                effective_deceleration=effective_deceleration,
            )

        return self._command_with_pid(
            train_state=train_state,
            ma_limit=ma_limit,
            ato_state="cruise",
            target_speed=safe_speed_limit,
            safe_speed_limit=safe_speed_limit,
            stop_curve_speed_limit=safe_speed_limit,
            stop_target=stop_target,
            distance_to_target=distance_to_target,
            holding_brake=False,
            reason="far_from_stop_target",
            selected_strategy="energy_saving",
            strategy_scores=[],
            gradient_info=gradient_info,
            effective_deceleration=effective_deceleration,
        )

    def _command_with_pid(
        self,
        train_state,
        ma_limit,
        ato_state,
        target_speed,
        safe_speed_limit,
        stop_curve_speed_limit,
        stop_target,
        distance_to_target,
        holding_brake,
        reason,
        optimize_context=None,
        selected_strategy="pid_basic",
        score=None,
        strategy_scores=None,
        gradient_info=None,
        effective_deceleration=None,
    ) -> dict:
        vehicle_id = train_state.get("vehicle_id")
        current_speed = _to_float(train_state.get("speed"), 0.0)
        target_speed = self._clamp_target_speed(target_speed, safe_speed_limit, stop_curve_speed_limit)
        if optimize_context is not None:
            optimization = self.strategy_optimizer.optimize(
                **optimize_context,
                creep_speed_limit=self.creep_speed_limit,
            )
            target_speed = self._clamp_target_speed(
                optimization["target_speed"],
                safe_speed_limit,
                stop_curve_speed_limit,
            )
            selected_strategy = optimization["selected_strategy"]
            score = optimization["score"]
            strategy_scores = optimization["strategy_scores"]
        pid = self._pid_for_vehicle(vehicle_id)
        control_value = pid.update(target_speed, current_speed, dt=0.25)
        traction_level, brake_level = control_value_to_levels(control_value)
        if target_speed == 0 and current_speed > self.low_speed_threshold:
            brake_level = max(brake_level, 1)
        return self._base_command(
            train_state=train_state,
            ma_limit=ma_limit,
            ato_state=ato_state,
            target_speed=target_speed,
            safe_speed_limit=safe_speed_limit,
            stop_curve_speed_limit=stop_curve_speed_limit,
            stop_target=stop_target,
            distance_to_target=distance_to_target,
            traction_level=traction_level,
            brake_level=brake_level,
            holding_brake=holding_brake,
            reason=reason,
            selected_strategy=selected_strategy,
            score=score,
            strategy_scores=strategy_scores or [],
            gradient_info=gradient_info,
            effective_deceleration=effective_deceleration,
        )

    def _degraded_command(
        self,
        train_state,
        ma_limit=None,
        stop_target=None,
        distance_to_target=None,
        reason="signal_stop",
        safe_speed_limit=0.0,
        gradient_info=None,
        effective_deceleration=None,
    ) -> dict:
        return self._base_command(
            train_state=train_state,
            ma_limit=ma_limit or {},
            ato_state="degraded",
            target_speed=0.0,
            safe_speed_limit=safe_speed_limit,
            stop_curve_speed_limit=0.0,
            stop_target=stop_target,
            distance_to_target=distance_to_target,
            traction_level=0,
            brake_level=5,
            holding_brake=False,
            reason=reason,
            selected_strategy="safety_stop",
            strategy_scores=[],
            gradient_info=gradient_info,
            effective_deceleration=effective_deceleration,
        )

    def _base_command(
        self,
        train_state,
        ma_limit,
        ato_state,
        target_speed,
        safe_speed_limit,
        stop_curve_speed_limit,
        stop_target,
        distance_to_target,
        traction_level,
        brake_level,
        holding_brake,
        reason,
        selected_strategy="pid_basic",
        score=None,
        strategy_scores=None,
        gradient_info=None,
        effective_deceleration=None,
    ) -> dict:
        target_speed = self._clamp_target_speed(target_speed, safe_speed_limit, stop_curve_speed_limit)
        if effective_deceleration is None:
            effective_deceleration = calculate_effective_deceleration(self.stop_deceleration, None)
        if stop_target:
            target_position = _to_float(stop_target.get("position"), 0.0)
            window_before = _to_float(stop_target.get("window_before"), 0.5)
            window_after = _to_float(stop_target.get("window_after"), 0.5)
            stop_window = {
                "lower": round(target_position - window_before, 3),
                "upper": round(target_position + window_after, 3),
            }
        else:
            target_position = None
            stop_window = None

        return {
            "vehicle_id": train_state.get("vehicle_id"),
            "control_mode": "ATO",
            "ato_state": ato_state,
            "target_speed": target_speed,
            "safe_speed_limit": round(max(safe_speed_limit, 0.0), 1),
            "stop_curve_speed_limit": round(max(stop_curve_speed_limit, 0.0), 1),
            "current_speed": round(_to_float(train_state.get("speed"), 0.0), 1),
            "target_position": target_position,
            "distance_to_target": round(distance_to_target, 3) if distance_to_target is not None else None,
            "target_id": stop_target.get("target_id") if stop_target else None,
            "station_id": stop_target.get("station_id") if stop_target else None,
            "station_name": stop_target.get("station_name") if stop_target else None,
            "platform_id": stop_target.get("platform_id") if stop_target else None,
            "platform_name": stop_target.get("platform_name") if stop_target else None,
            "stop_target_source": stop_target.get("source") if stop_target else None,
            "stop_window": stop_window,
            "traction_level": traction_level,
            "brake_level": brake_level,
            "holding_brake": holding_brake,
            "selected_strategy": selected_strategy,
            "score": score,
            "strategy_scores": strategy_scores or [],
            "reason": reason,
            "speed_limit_reason": ma_limit.get("speed_limit_reason"),
            "gradient": round(float(gradient_info["gradient"]), 3) if gradient_info else None,
            "gradient_id": gradient_info.get("gradient_id") if gradient_info else None,
            "gradient_unit": gradient_info.get("gradient_unit") if gradient_info else None,
            "effective_deceleration": round(max(float(effective_deceleration), 0.0), 3),
        }

    def _pid_for_vehicle(self, vehicle_id):
        if vehicle_id not in self.pid_controllers_by_vehicle:
            self.pid_controllers_by_vehicle[vehicle_id] = self.pid_controller_factory()
        return self.pid_controllers_by_vehicle[vehicle_id]

    def _nearest_stop_target_on_route(self, train_state: dict) -> dict | None:
        route_id = train_state.get("route_id")
        current_position = _to_float(train_state.get("position"), 0.0)
        matching_targets = [
            deepcopy(target)
            for target in self.stop_targets
            if target.get("route_id") == route_id
        ]
        if not matching_targets:
            return None
        return min(
            matching_targets,
            key=lambda item: abs(_to_float(item.get("position"), 0.0) - current_position),
        )

    def _gradient_context(self, position: float) -> tuple[dict | None, float]:
        gradient_info = find_gradient_at_position(position, self.gradient_profile)
        gradient_value = gradient_info.get("gradient") if gradient_info else None
        return (
            gradient_info,
            calculate_effective_deceleration(self.stop_deceleration, gradient_value),
        )

    def _clamp_target_speed(self, target_speed, safe_speed_limit, stop_curve_speed_limit) -> float:
        safe_limit = max(_to_float(safe_speed_limit, 0.0), 0.0)
        curve_limit = max(_to_float(stop_curve_speed_limit, 0.0), 0.0)
        return round(max(min(_to_float(target_speed, 0.0), safe_limit, curve_limit), 0.0), 1)


def _value_to_level(value: float) -> int:
    value = clamp(_to_float(value, 0.0), 0.0, 100.0)
    if value == 0:
        return 0
    if value <= 20:
        return 1
    if value <= 40:
        return 2
    if value <= 60:
        return 3
    if value <= 80:
        return 4
    return 5


def _to_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
