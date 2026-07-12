import math

import pytest

from app.vehicle_sim.atp import (
    AtpConfig,
    cached_dynamic_stop_distance,
    check_atp,
    dynamic_stop_distance,
    evaluate_atp,
)
from app.vehicle_sim.dynamics import update_dynamics
from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.models import TrainState
from app.vehicle_sim.train_manager import TrainManager


def _state(speed_ms=20.0, position=100.0):
    return TrainState(
        vehicle_id="TRAIN-001",
        line_id="LINE-1",
        position=position,
        speed_ms=speed_ms,
        acceleration=0.0,
        mode="manual",
        is_running=speed_ms > 0,
        emergency_brake=False,
    )


def test_overspeed_triggers_atp():
    state = _state()

    should_brake, alarm = check_atp(
        state=state,
        speed_limit=30.0,
        ma_limit=1000.0,
        power_fault=False,
        comm_ok=True,
    )

    assert should_brake is True
    assert alarm is not None
    assert alarm["source"] == "ATP"


def test_allowed_speed_warning_does_not_apply_eb_before_eb_margin():
    decision = evaluate_atp(
        state=_state(speed_ms=12.0),
        speed_limit=80.0,
        ma_limit=1000.0,
        power_fault=False,
        comm_ok=True,
        allowed_speed_kmh=40.0,
        eb_trigger_speed_kmh=55.0,
    )

    assert decision.emergency_brake is False
    assert decision.supervision_state == "overspeed_warning"
    assert decision.alarm is not None
    assert decision.alarm["level"] == "warning"


def test_eb_trigger_speed_applies_emergency_brake():
    decision = evaluate_atp(
        state=_state(speed_ms=16.0),
        speed_limit=80.0,
        ma_limit=1000.0,
        power_fault=False,
        comm_ok=True,
        allowed_speed_kmh=40.0,
        eb_trigger_speed_kmh=45.0,
    )

    assert decision.emergency_brake is True
    assert decision.reason == "eb_speed_exceeded"


def test_emergency_braking_curve_applies_eb_near_ma():
    decision = evaluate_atp(
        state=_state(speed_ms=20.0, position=100.0),
        speed_limit=80.0,
        ma_limit=130.0,
        power_fault=False,
        comm_ok=True,
    )

    assert decision.emergency_brake is True
    assert decision.reason == "emergency_braking_curve_exceeded"
    assert decision.distance_to_authority_m == 30.0


def test_service_braking_curve_warns_before_emergency_curve():
    decision = evaluate_atp(
        state=_state(speed_ms=10.0, position=100.0),
        speed_limit=80.0,
        ma_limit=170.0,
        power_fault=False,
        comm_ok=True,
    )

    assert decision.emergency_brake is False
    assert decision.supervision_state in {"service_brake_warning", "warning"}
    assert decision.alarm["level"] == "warning"


def test_comm_timeout_applies_emergency_brake():
    decision = evaluate_atp(
        state=_state(speed_ms=5.0),
        speed_limit=80.0,
        ma_limit=1000.0,
        power_fault=False,
        comm_ok=True,
        last_message_at=100.0,
        now=102.0,
    )

    assert decision.emergency_brake is True
    assert decision.reason == "communication_lost"


def test_router_maps_signal_ma_fields_into_vehicle_atp_envelope():
    manager = TrainManager()
    router = MessageRouter(manager)
    router.handle(
        {
            "type": "ma_state",
            "ma_limits": [
                {
                    "vehicle_id": "TRAIN-001",
                    "ma_limit": 500.0,
                    "distance_to_ma": 120.0,
                    "speed_limit": 35.0,
                    "target_speed": 30.0,
                    "permission": "restricted",
                    "signal_state": "yellow",
                }
            ],
        }
    )

    train = manager.get_train("TRAIN-001")
    assert train.target_distance_m == 120.0
    assert train.allowed_speed_kmh == 35.0
    assert train.target_speed_kmh == 30.0
    assert train.permission == "restricted"
    assert train.signal_state == "yellow"


def _simulate_full_brake_distance(speed_ms: float, gradient_permille: float = 0.0) -> float:
    speed = speed_ms
    position = 0.0
    dt = 0.02
    for _ in range(int(180.0 / dt)):
        if speed <= 0.05:
            return position
        speed, position, _, _, _ = update_dynamics(
            speed_ms=speed,
            position=position,
            traction_level=0,
            brake_level=4,
            gradient=gradient_permille,
            dt=dt,
        )
    return math.inf


@pytest.mark.parametrize("speed_ms", [1.0, 5.0, 10.0, 15.0, 20.0, 22.222])
def test_dynamic_emergency_curve_matches_new_vehicle_dynamics(speed_ms):
    predicted_without_reaction_or_margin = dynamic_stop_distance(
        speed_ms=speed_ms,
        brake_level=4,
        reaction_time_sec=0.0,
        safety_margin_m=0.0,
    )
    simulated = _simulate_full_brake_distance(speed_ms)

    assert predicted_without_reaction_or_margin == pytest.approx(simulated, abs=0.25)


def test_dynamic_service_curve_is_longer_than_emergency_curve():
    service = dynamic_stop_distance(20.0, brake_level=3)
    emergency = dynamic_stop_distance(20.0, brake_level=4)

    assert service > emergency > 0.0


def test_downhill_gradient_increases_dynamic_stop_distance():
    flat = dynamic_stop_distance(15.0, brake_level=4, gradient_permille=0.0)
    downhill = dynamic_stop_distance(15.0, brake_level=4, gradient_permille=-3.0)

    assert downhill > flat


def test_unprovable_electric_brake_stop_returns_infinity():
    distance = dynamic_stop_distance(
        2.0,
        brake_level=4,
        gradient_permille=-30.0,
        max_simulation_sec=30.0,
    )

    assert math.isinf(distance)


def test_atp_can_use_analytic_fallback_for_compatibility():
    decision = evaluate_atp(
        state=_state(speed_ms=10.0),
        speed_limit=80.0,
        ma_limit=1000.0,
        power_fault=False,
        comm_ok=True,
        config=AtpConfig(use_dynamic_braking_model=False),
    )

    expected = 10.0 * 0.6 + 10.0**2 / (2.0 * 1.10) + 4.0
    assert decision.emergency_stop_distance_m == pytest.approx(expected, abs=0.001)


def test_dynamic_curve_rejects_non_finite_input():
    with pytest.raises(ValueError):
        dynamic_stop_distance(float("nan"), brake_level=4)


def test_realtime_curve_cache_quantisation_is_conservative():
    exact = dynamic_stop_distance(
        10.01,
        brake_level=4,
        gradient_permille=-1.01,
        integration_dt_sec=0.05,
    )
    cached = cached_dynamic_stop_distance(
        10.01,
        brake_level=4,
        gradient_permille=-1.01,
        integration_dt_sec=0.05,
    )

    assert cached >= exact


def test_train_stopped_at_authority_endpoint_does_not_latch_emergency():
    decision = evaluate_atp(
        state=_state(speed_ms=0.0, position=100.0),
        speed_limit=80.0,
        ma_limit=100.0,
        target_distance_m=0.0,
        power_fault=False,
        comm_ok=True,
    )

    assert decision.emergency_brake is False
    assert decision.supervision_state == "normal"
