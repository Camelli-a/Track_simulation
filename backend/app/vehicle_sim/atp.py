import time
from dataclasses import dataclass
from typing import Optional, Tuple

from .models import TrainState


@dataclass(frozen=True)
class AtpConfig:
    service_deceleration_ms2: float = 0.85
    emergency_deceleration_ms2: float = 1.25
    reaction_time_sec: float = 0.6
    safety_margin_m: float = 4.0
    warning_margin_m: float = 20.0
    overspeed_warning_margin_kmh: float = 3.0
    overspeed_eb_margin_kmh: float = 8.0
    movement_stop_speed_ms: float = 0.05
    comm_timeout_sec: float = 1.6


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
    timeout_sec: float = 1.6,
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
        if distance_to_authority <= 0 and state.speed_ms > config.movement_stop_speed_ms:
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

        if distance_to_authority <= emergency_stop_distance:
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

        if distance_to_authority <= service_stop_distance:
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

        if distance_to_authority <= service_stop_distance + config.warning_margin_m:
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
        return float(ma_limit) - state.position
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
