import time
from dataclasses import dataclass
from functools import lru_cache
from math import isfinite
from math import ceil, floor
from typing import Optional, Tuple

from .dynamics import (
    calc_brake_force,
    calc_gradient_resistance,
    calc_running_resistance,
)
from .models import TrainState
from .vehicle_parameters import TRAIN_MASS_KG

DRIVER_WARNING_TIMEOUT_SEC = 0.3
DRIVER_EMERGENCY_TIMEOUT_SEC = 0.5


@dataclass(frozen=True)
class AtpConfig:
    # Conservative analytic fallbacks.  The default path below uses the
    # supplied 52-point motor curves instead of assuming constant force.
    service_deceleration_ms2: float = 0.80
    emergency_deceleration_ms2: float = 1.10
    service_brake_level: int = 3
    emergency_brake_level: int = 4
    use_dynamic_braking_model: bool = True
    braking_integration_dt_sec: float = 0.05
    max_braking_simulation_sec: float = 180.0
    reaction_time_sec: float = 0.6
    safety_margin_m: float = 4.0
    warning_margin_m: float = 20.0
    overspeed_warning_margin_kmh: float = 3.0
    overspeed_eb_margin_kmh: float = 8.0
    movement_stop_speed_ms: float = 0.05
    comm_warning_timeout_sec: float = DRIVER_WARNING_TIMEOUT_SEC
    comm_timeout_sec: float = DRIVER_EMERGENCY_TIMEOUT_SEC


@dataclass(frozen=True)
class AtpDecision:
    emergency_brake: bool
    supervision_state: str
    reason: str
    alarm: Optional[dict]
    allowed_speed_kmh: float
    eb_trigger_speed_kmh: float
    distance_to_authority_m: Optional[float]
    service_stop_distance_m: float
    emergency_stop_distance_m: float


def build_alarm(vehicle_id: str, level: str, message: str, reason: str | None = None) -> dict:
    alarm = {
        "type": "alarm_event",
        "timestamp": time.time(),
        "alarm_id": f"ALM-{int(time.time() * 1000)}",
        "level": level,
        "source": "ATP",
        "vehicle_id": vehicle_id,
        "message": message,
    }
    if reason is not None:
        alarm["reason"] = reason
    return alarm


def check_atp(
    state: TrainState,
    speed_limit: float,
    ma_limit: Optional[float],
    power_fault: bool,
    comm_ok: bool,
    allowed_speed_kmh: Optional[float] = None,
    eb_trigger_speed_kmh: Optional[float] = None,
    target_distance_m: Optional[float] = None,
    last_message_at: Optional[float] = None,
    now: Optional[float] = None,
    timeout_sec: float = DRIVER_EMERGENCY_TIMEOUT_SEC,
    gradient_permille: float = 0.0,
) -> Tuple[bool, Optional[dict]]:
    """Compatibility wrapper returning whether ATP should apply EB."""
    decision = evaluate_atp(
        state=state,
        speed_limit=speed_limit,
        ma_limit=ma_limit,
        power_fault=power_fault,
        comm_ok=comm_ok,
        allowed_speed_kmh=allowed_speed_kmh,
        eb_trigger_speed_kmh=eb_trigger_speed_kmh,
        target_distance_m=target_distance_m,
        last_message_at=last_message_at,
        now=now,
        gradient_permille=gradient_permille,
        config=AtpConfig(comm_timeout_sec=timeout_sec),
    )
    return decision.emergency_brake, decision.alarm


def evaluate_atp(
    state: TrainState,
    speed_limit: float,
    ma_limit: Optional[float],
    power_fault: bool,
    comm_ok: bool,
    allowed_speed_kmh: Optional[float] = None,
    eb_trigger_speed_kmh: Optional[float] = None,
    target_distance_m: Optional[float] = None,
    last_message_at: Optional[float] = None,
    now: Optional[float] = None,
    gradient_permille: float = 0.0,
    config: AtpConfig | None = None,
) -> AtpDecision:
    """Evaluate ATP supervision using speed and movement-authority curves."""
    config = config or AtpConfig()
    now = time.time() if now is None else now

    effective_allowed_speed = _effective_allowed_speed(
        track_speed_limit=speed_limit,
        allowed_speed_kmh=allowed_speed_kmh,
    )
    effective_eb_speed = _effective_eb_speed(
        allowed_speed_kmh=effective_allowed_speed,
        eb_trigger_speed_kmh=eb_trigger_speed_kmh,
        config=config,
    )
    distance_to_authority = _distance_to_authority(
        state=state,
        ma_limit=ma_limit,
        target_distance_m=target_distance_m,
    )
    if config.use_dynamic_braking_model:
        service_stop_distance = cached_dynamic_stop_distance(
            speed_ms=state.speed_ms,
            brake_level=config.service_brake_level,
            gradient_permille=gradient_permille,
            reaction_time_sec=config.reaction_time_sec,
            safety_margin_m=config.safety_margin_m,
            integration_dt_sec=config.braking_integration_dt_sec,
            stop_speed_ms=config.movement_stop_speed_ms,
            max_simulation_sec=config.max_braking_simulation_sec,
        )
        emergency_stop_distance = cached_dynamic_stop_distance(
            speed_ms=state.speed_ms,
            brake_level=config.emergency_brake_level,
            gradient_permille=gradient_permille,
            reaction_time_sec=config.reaction_time_sec,
            safety_margin_m=config.safety_margin_m,
            integration_dt_sec=config.braking_integration_dt_sec,
            stop_speed_ms=config.movement_stop_speed_ms,
            max_simulation_sec=config.max_braking_simulation_sec,
        )
    else:
        service_stop_distance = stop_distance(
            speed_ms=state.speed_ms,
            deceleration_ms2=config.service_deceleration_ms2,
            reaction_time_sec=config.reaction_time_sec,
            safety_margin_m=config.safety_margin_m,
        )
        emergency_stop_distance = stop_distance(
            speed_ms=state.speed_ms,
            deceleration_ms2=config.emergency_deceleration_ms2,
            reaction_time_sec=config.reaction_time_sec,
            safety_margin_m=config.safety_margin_m,
        )

    if power_fault:
        return _decision(
            state,
            True,
            "emergency",
            "power_fault",
            "Power fault, emergency brake triggered",
            effective_allowed_speed,
            effective_eb_speed,
            distance_to_authority,
            service_stop_distance,
            emergency_stop_distance,
        )

    if not comm_ok or is_comm_timeout(last_message_at, now, config.comm_timeout_sec):
        return _decision(
            state,
            True,
            "emergency",
            "communication_lost",
            "Communication lost, emergency brake triggered",
            effective_allowed_speed,
            effective_eb_speed,
            distance_to_authority,
            service_stop_distance,
            emergency_stop_distance,
        )

    if is_comm_timeout(last_message_at, now, config.comm_warning_timeout_sec):
        return _decision(
            state,
            False,
            "warning",
            "communication_delayed",
            "Driver console message delayed",
            effective_allowed_speed,
            effective_eb_speed,
            distance_to_authority,
            service_stop_distance,
            emergency_stop_distance,
        )

    if state.speed_kmh > effective_eb_speed:
        return _decision(
            state,
            True,
            "emergency",
            "eb_speed_exceeded",
            "Train exceeded EB trigger speed, emergency brake triggered",
            effective_allowed_speed,
            effective_eb_speed,
            distance_to_authority,
            service_stop_distance,
            emergency_stop_distance,
        )

    if distance_to_authority is not None:
        train_is_moving = state.speed_ms > config.movement_stop_speed_ms
        if distance_to_authority <= 0 and train_is_moving:
            return _decision(
                state,
                True,
                "emergency",
                "authority_overrun",
                "Train exceeded movement authority, emergency brake triggered",
                effective_allowed_speed,
                effective_eb_speed,
                distance_to_authority,
                service_stop_distance,
                emergency_stop_distance,
            )

        if train_is_moving and distance_to_authority <= emergency_stop_distance:
            return _decision(
                state,
                True,
                "emergency",
                "emergency_braking_curve_exceeded",
                "Train exceeded ATP emergency braking curve",
                effective_allowed_speed,
                effective_eb_speed,
                distance_to_authority,
                service_stop_distance,
                emergency_stop_distance,
            )

        if train_is_moving and distance_to_authority <= service_stop_distance:
            return _decision(
                state,
                False,
                "service_brake_warning",
                "service_braking_curve_warning",
                "Train is inside ATP service braking curve",
                effective_allowed_speed,
                effective_eb_speed,
                distance_to_authority,
                service_stop_distance,
                emergency_stop_distance,
                alarm_level="warning",
            )

        if (
            train_is_moving
            and distance_to_authority <= service_stop_distance + config.warning_margin_m
        ):
            return _decision(
                state,
                False,
                "warning",
                "approaching_braking_curve",
                "Train is approaching ATP braking curve",
                effective_allowed_speed,
                effective_eb_speed,
                distance_to_authority,
                service_stop_distance,
                emergency_stop_distance,
                alarm_level="warning",
            )

    if state.speed_kmh > effective_allowed_speed + config.overspeed_warning_margin_kmh:
        return _decision(
            state,
            False,
            "overspeed_warning",
            "allowed_speed_exceeded",
            "Train exceeded ATP allowed speed",
            effective_allowed_speed,
            effective_eb_speed,
            distance_to_authority,
            service_stop_distance,
            emergency_stop_distance,
            alarm_level="warning",
        )

    return AtpDecision(
        emergency_brake=False,
        supervision_state="normal",
        reason="normal",
        alarm=None,
        allowed_speed_kmh=effective_allowed_speed,
        eb_trigger_speed_kmh=effective_eb_speed,
        distance_to_authority_m=distance_to_authority,
        service_stop_distance_m=round(service_stop_distance, 3),
        emergency_stop_distance_m=round(emergency_stop_distance, 3),
    )


def stop_distance(
    speed_ms: float,
    deceleration_ms2: float,
    reaction_time_sec: float,
    safety_margin_m: float,
) -> float:
    speed_ms = max(speed_ms, 0.0)
    deceleration_ms2 = max(deceleration_ms2, 0.001)
    return (
        speed_ms * reaction_time_sec
        + speed_ms * speed_ms / (2 * deceleration_ms2)
        + safety_margin_m
    )


def dynamic_stop_distance(
    speed_ms: float,
    brake_level: int,
    gradient_permille: float = 0.0,
    reaction_time_sec: float = 0.6,
    safety_margin_m: float = 4.0,
    integration_dt_sec: float = 0.02,
    stop_speed_ms: float = 0.05,
    max_simulation_sec: float = 180.0,
) -> float:
    """Estimate stopping distance with the same force model as vehicle dynamics.

    The reaction phase retains the existing ATP constant-speed assumption.  The
    braking phase numerically integrates the 52-point brake curve, Davis
    resistance and gradient resistance.  ``inf`` means that the current
    electric-brake-only model cannot prove a stop on the supplied gradient.
    """
    values = (
        speed_ms,
        gradient_permille,
        reaction_time_sec,
        safety_margin_m,
        integration_dt_sec,
        stop_speed_ms,
        max_simulation_sec,
    )
    if not all(isfinite(float(value)) for value in values):
        raise ValueError("dynamic stop-distance inputs must be finite")
    if integration_dt_sec <= 0.0:
        raise ValueError("integration_dt_sec must be positive")
    if max_simulation_sec <= 0.0:
        raise ValueError("max_simulation_sec must be positive")

    speed = max(0.0, float(speed_ms))
    distance = speed * max(0.0, reaction_time_sec) + max(0.0, safety_margin_m)
    elapsed = 0.0
    stop_threshold = max(0.0, stop_speed_ms)

    while speed > stop_threshold and elapsed < max_simulation_sec:
        resisting_force = (
            calc_brake_force(brake_level, speed)
            + calc_running_resistance(speed)
            + calc_gradient_resistance(gradient_permille)
        )
        deceleration = resisting_force / TRAIN_MASS_KG
        if deceleration <= 0.0:
            return float("inf")

        next_speed = max(0.0, speed - deceleration * integration_dt_sec)
        distance += (speed + next_speed) * 0.5 * integration_dt_sec
        speed = next_speed
        elapsed += integration_dt_sec

    if speed > stop_threshold:
        return float("inf")
    return distance


def cached_dynamic_stop_distance(
    speed_ms: float,
    brake_level: int,
    gradient_permille: float = 0.0,
    reaction_time_sec: float = 0.6,
    safety_margin_m: float = 4.0,
    integration_dt_sec: float = 0.05,
    stop_speed_ms: float = 0.05,
    max_simulation_sec: float = 180.0,
) -> float:
    """Return a conservative cached model distance for the real-time ATP loop.

    Speed is rounded upward to 0.1 m/s and gradient downward to 0.1 permille,
    so cache quantisation never shortens the estimated stopping distance.
    """
    speed_bin = ceil(max(0.0, float(speed_ms)) * 10.0) / 10.0
    gradient_bin = floor(float(gradient_permille) * 10.0) / 10.0
    return _cached_dynamic_stop_distance(
        speed_bin,
        int(brake_level),
        gradient_bin,
        float(reaction_time_sec),
        float(safety_margin_m),
        float(integration_dt_sec),
        float(stop_speed_ms),
        float(max_simulation_sec),
    )


@lru_cache(maxsize=8192)
def _cached_dynamic_stop_distance(
    speed_ms: float,
    brake_level: int,
    gradient_permille: float,
    reaction_time_sec: float,
    safety_margin_m: float,
    integration_dt_sec: float,
    stop_speed_ms: float,
    max_simulation_sec: float,
) -> float:
    return dynamic_stop_distance(
        speed_ms=speed_ms,
        brake_level=brake_level,
        gradient_permille=gradient_permille,
        reaction_time_sec=reaction_time_sec,
        safety_margin_m=safety_margin_m,
        integration_dt_sec=integration_dt_sec,
        stop_speed_ms=stop_speed_ms,
        max_simulation_sec=max_simulation_sec,
    )


def is_comm_timeout(
    last_message_at: Optional[float],
    now: Optional[float] = None,
    timeout_sec: float = 1.6,
) -> bool:
    if last_message_at is None:
        return False
    if now is None:
        now = time.time()
    return now - last_message_at > timeout_sec


def _effective_allowed_speed(
    track_speed_limit: float,
    allowed_speed_kmh: Optional[float],
) -> float:
    if allowed_speed_kmh is None:
        return max(0.0, float(track_speed_limit))
    return max(0.0, min(float(track_speed_limit), float(allowed_speed_kmh)))


def _effective_eb_speed(
    allowed_speed_kmh: float,
    eb_trigger_speed_kmh: Optional[float],
    config: AtpConfig,
) -> float:
    fallback_eb_speed = allowed_speed_kmh + config.overspeed_eb_margin_kmh
    if eb_trigger_speed_kmh is None:
        return fallback_eb_speed
    return max(0.0, min(float(eb_trigger_speed_kmh), fallback_eb_speed))


def _distance_to_authority(
    state: TrainState,
    ma_limit: Optional[float],
    target_distance_m: Optional[float],
) -> Optional[float]:
    if target_distance_m is not None:
        return float(target_distance_m)
    if ma_limit is not None:
        direction_sign = -1 if int(getattr(state, "direction_code", 1) or 1) < 0 else 1
        return (float(ma_limit) - state.position) * direction_sign
    return None


def _decision(
    state: TrainState,
    emergency_brake: bool,
    supervision_state: str,
    reason: str,
    message: str,
    allowed_speed_kmh: float,
    eb_trigger_speed_kmh: float,
    distance_to_authority: Optional[float],
    service_stop_distance: float,
    emergency_stop_distance: float,
    alarm_level: str = "critical",
) -> AtpDecision:
    return AtpDecision(
        emergency_brake=emergency_brake,
        supervision_state=supervision_state,
        reason=reason,
        alarm=build_alarm(state.vehicle_id, alarm_level, message, reason),
        allowed_speed_kmh=round(allowed_speed_kmh, 3),
        eb_trigger_speed_kmh=round(eb_trigger_speed_kmh, 3),
        distance_to_authority_m=(
            None if distance_to_authority is None else round(distance_to_authority, 3)
        ),
        service_stop_distance_m=round(service_stop_distance, 3),
        emergency_stop_distance_m=round(emergency_stop_distance, 3),
    )
