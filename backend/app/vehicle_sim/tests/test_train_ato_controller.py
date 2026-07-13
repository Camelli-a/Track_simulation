import math

import pytest

from app.vehicle_sim.controllers.train_ato_controller import (
    AtoControlInput,
    TrainAtoController,
)


def _controller():
    return TrainAtoController()


def _am_input(**overrides):
    data = {
        "vehicle_id": "TRAIN-001",
        "position_m": 1000.0,
        "speed_ms": 10.0,
        "ma_limit_m": 2000.0,
        "allowed_speed_kmh": 60.0,
        "stop_target_m": 1800.0,
        "driving_mode": "AM",
    }
    data.update(overrides)
    return AtoControlInput(**data)


def test_clamp_level_limits_to_zero_to_four():
    controller = _controller()

    assert controller.clamp_level(-1) == 0
    assert controller.clamp_level(0) == 0
    assert controller.clamp_level(2.4) == 2
    assert controller.clamp_level(3.6) == 4
    assert controller.clamp_level(10) == 4


def test_resolve_exclusive_levels_uses_brake_priority():
    controller = _controller()

    assert controller.resolve_exclusive_levels(3, 2) == (0, 2)
    assert controller.resolve_exclusive_levels(2, 0) == (2, 0)


def test_smooth_command_levels_brake_steps_up_gradually():
    controller = _controller()

    traction, brake = controller.smooth_command_levels(
        target_traction_level=0,
        target_brake_level=4,
        previous_traction_level=0,
        previous_brake_level=0,
        enabled=True,
    )

    assert traction == 0
    assert brake == 1


def test_smooth_command_levels_keeps_brake_priority():
    controller = _controller()

    traction, brake = controller.smooth_command_levels(
        target_traction_level=2,
        target_brake_level=3,
        previous_traction_level=2,
        previous_brake_level=0,
        enabled=True,
    )

    assert traction == 0
    assert 1 <= brake <= 3


def test_smooth_command_levels_releases_brake_before_traction():
    controller = _controller()

    traction, brake = controller.smooth_command_levels(
        target_traction_level=2,
        target_brake_level=0,
        previous_traction_level=0,
        previous_brake_level=3,
        enabled=True,
    )

    assert traction == 0
    assert brake == 2


def test_smooth_command_levels_bypass_outputs_target_immediately():
    controller = _controller()

    traction, brake = controller.smooth_command_levels(
        target_traction_level=0,
        target_brake_level=4,
        previous_traction_level=0,
        previous_brake_level=0,
        enabled=True,
        bypass=True,
    )

    assert traction == 0
    assert brake == 4


def test_am_normal_cruise_outputs_safe_levels():
    controller = _controller()

    output = controller.compute_control(_am_input())

    assert output.degraded is False
    assert output.ato_target_speed_kmh <= 60.0
    assert 0 <= output.traction_level <= 4
    assert 0 <= output.brake_level <= 4
    assert output.ato_traction_level == output.commanded_traction_level
    assert output.ato_brake_level == output.commanded_brake_level
    assert output.applied_traction_level == output.commanded_traction_level
    assert output.applied_brake_level == output.commanded_brake_level
    assert output.control_source == "ato"
    assert output.atp_intervened is False


def test_am_brakes_when_approaching_stop_target_too_fast():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1490.0, speed_ms=8.0, stop_target_m=1500.0)
    )

    assert output.ato_state in {"braking_to_stop", "creep", "approaching"}
    assert output.brake_level > 0
    assert output.traction_level == 0


def test_low_speed_target_decreases_with_distance():
    controller = _controller()

    assert controller.compute_low_speed_target_ms(10.0) > controller.compute_low_speed_target_ms(3.0)
    assert controller.compute_low_speed_target_ms(3.0) <= controller.CRAWL_SPEED_MS
    assert controller.compute_low_speed_target_ms(0.3) == 0.0
    assert controller.compute_low_speed_target_ms(-0.1) == 0.0


def test_compute_predicted_state_forward_without_acceleration():
    controller = _controller()

    position, speed = controller.compute_predicted_state(
        position_m=1000.0,
        speed_ms=10.0,
        acceleration_ms2=0.0,
        direction=1,
        control_delay_sec=0.3,
        enabled=True,
    )

    assert position == pytest.approx(1003.0)
    assert speed == pytest.approx(10.0)


def test_compute_predicted_state_with_acceleration():
    controller = _controller()

    position, speed = controller.compute_predicted_state(
        position_m=1000.0,
        speed_ms=10.0,
        acceleration_ms2=-1.0,
        direction=1,
        control_delay_sec=0.5,
        enabled=True,
    )

    assert position == pytest.approx(1004.875)
    assert speed == pytest.approx(9.5)


def test_compute_predicted_state_reverse_direction():
    controller = _controller()

    position, speed = controller.compute_predicted_state(
        position_m=1000.0,
        speed_ms=10.0,
        acceleration_ms2=0.0,
        direction=-1,
        control_delay_sec=0.3,
        enabled=True,
    )

    assert position == pytest.approx(997.0)
    assert speed == pytest.approx(10.0)


def test_compute_predicted_state_disabled_or_zero_delay_returns_actual_state():
    controller = _controller()

    assert controller.compute_predicted_state(
        position_m=1000.0,
        speed_ms=10.0,
        acceleration_ms2=-1.0,
        direction=1,
        control_delay_sec=0.3,
        enabled=False,
    ) == (1000.0, 10.0)
    assert controller.compute_predicted_state(
        position_m=1000.0,
        speed_ms=10.0,
        acceleration_ms2=-1.0,
        direction=1,
        control_delay_sec=0.0,
        enabled=True,
    ) == (1000.0, 10.0)


def test_gradient_adjusted_deceleration_helper():
    controller = _controller()
    base = controller.COMFORT_DECEL_MS2

    assert controller.compute_gradient_adjusted_decel(base, 30.0, enabled=False) == base
    assert controller.compute_gradient_adjusted_decel(base, 0.0, enabled=True) == pytest.approx(base)
    assert controller.compute_gradient_adjusted_decel(base, 30.0, enabled=True) > base
    assert controller.compute_gradient_adjusted_decel(base, -30.0, enabled=True) < base
    assert (
        controller.compute_gradient_adjusted_decel(base, 999.0, enabled=True)
        <= controller.MAX_EFFECTIVE_DECEL_MS2
    )
    assert (
        controller.compute_gradient_adjusted_decel(base, -999.0, enabled=True)
        >= controller.MIN_EFFECTIVE_DECEL_MS2
    )
    assert controller.compute_gradient_adjusted_decel(base, math.nan, enabled=True) == pytest.approx(base)
    assert controller.compute_gradient_adjusted_decel(base, math.inf, enabled=True) == pytest.approx(base)


def test_normalize_brake_bias_disabled_returns_default():
    controller = _controller()

    assert controller.normalize_brake_bias(1.5, enabled=False) == pytest.approx(1.0)


@pytest.mark.parametrize("invalid_bias", [None, math.nan, math.inf])
def test_normalize_brake_bias_invalid_values_fall_back_to_default(invalid_bias):
    controller = _controller()

    assert controller.normalize_brake_bias(invalid_bias, enabled=True) == pytest.approx(1.0)


@pytest.mark.parametrize("unsafe_bias", [-1.0, 0.0])
def test_normalize_brake_bias_non_positive_values_stay_safe(unsafe_bias):
    controller = _controller()

    assert controller.normalize_brake_bias(unsafe_bias, enabled=True) > 0.0
    assert controller.normalize_brake_bias(unsafe_bias, enabled=True) == pytest.approx(
        controller.MIN_BRAKE_BIAS
    )


def test_normalize_brake_bias_clamps_to_safe_range():
    controller = _controller()

    assert controller.normalize_brake_bias(0.1, enabled=True) == pytest.approx(
        controller.MIN_BRAKE_BIAS
    )
    assert controller.normalize_brake_bias(10.0, enabled=True) == pytest.approx(
        controller.MAX_BRAKE_BIAS
    )


def test_apply_brake_bias_to_decel_adjusts_effective_deceleration():
    controller = _controller()

    weak_brake_decel = controller.apply_brake_bias_to_decel(0.8, 1.2)
    strong_brake_decel = controller.apply_brake_bias_to_decel(0.8, 0.8)

    assert weak_brake_decel < 0.8
    assert strong_brake_decel > 0.8


def test_am_uses_low_speed_position_control_within_twelve_meters():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1489.0, speed_ms=3.0, stop_target_m=1500.0)
    )
    expected_target_kmh = controller.compute_low_speed_target_ms(11.0) * 3.6

    assert output.ato_state in {"approaching", "braking_to_stop"}
    assert output.ato_target_speed_kmh <= expected_target_kmh + 0.001
    assert 0 <= output.commanded_traction_level <= 4
    assert 0 <= output.commanded_brake_level <= 4
    assert not (
        output.commanded_traction_level > 0 and output.commanded_brake_level > 0
    )


def test_delay_compensation_makes_distance_and_target_speed_more_conservative():
    controller = _controller()

    without_delay = controller.compute_am_command(
        _am_input(
            position_m=1480.0,
            speed_ms=10.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=60.0,
            control_delay_sec=0.5,
            delay_compensation_enabled=False,
        )
    )
    with_delay = controller.compute_am_command(
        _am_input(
            position_m=1480.0,
            speed_ms=10.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=60.0,
            control_delay_sec=0.5,
            delay_compensation_enabled=True,
        )
    )

    assert with_delay.distance_to_stop_m < without_delay.distance_to_stop_m
    assert with_delay.ato_target_speed_kmh <= without_delay.ato_target_speed_kmh
    assert with_delay.commanded_brake_level >= without_delay.commanded_brake_level
    assert with_delay.commanded_traction_level <= without_delay.commanded_traction_level


def test_downhill_gradient_makes_am_target_speed_more_conservative():
    controller = _controller()

    flat = controller.compute_am_command(
        _am_input(
            position_m=1400.0,
            speed_ms=15.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            gradient_permille=0.0,
            gradient_compensation_enabled=True,
        )
    )
    downhill = controller.compute_am_command(
        _am_input(
            position_m=1400.0,
            speed_ms=15.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            gradient_permille=-30.0,
            gradient_compensation_enabled=True,
        )
    )

    assert downhill.ato_target_speed_kmh <= flat.ato_target_speed_kmh
    assert downhill.commanded_brake_level >= flat.commanded_brake_level
    assert downhill.commanded_traction_level <= flat.commanded_traction_level


def test_am_brake_command_is_smoothed_when_jerk_limit_enabled():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(
            position_m=1400.0,
            speed_ms=15.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            previous_commanded_brake_level=0,
            jerk_limit_enabled=True,
        )
    )

    assert output.ato_brake_level == 4
    assert output.commanded_brake_level <= output.ato_brake_level
    assert output.commanded_brake_level <= 1
    assert output.applied_brake_level == output.commanded_brake_level


def test_uphill_gradient_does_not_make_am_target_speed_more_conservative():
    controller = _controller()

    flat = controller.compute_am_command(
        _am_input(
            position_m=1400.0,
            speed_ms=15.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            gradient_permille=0.0,
            gradient_compensation_enabled=True,
        )
    )
    uphill = controller.compute_am_command(
        _am_input(
            position_m=1400.0,
            speed_ms=15.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            gradient_permille=30.0,
            gradient_compensation_enabled=True,
        )
    )

    assert uphill.ato_target_speed_kmh >= flat.ato_target_speed_kmh
    assert uphill.ato_target_speed_kmh <= 80.0


def test_am_brake_bias_above_one_makes_target_speed_more_conservative():
    controller = _controller()

    baseline = controller.compute_am_command(
        _am_input(
            position_m=1420.0,
            speed_ms=8.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            brake_bias=1.0,
            brake_bias_enabled=True,
        )
    )
    biased = controller.compute_am_command(
        _am_input(
            position_m=1420.0,
            speed_ms=8.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            brake_bias=1.3,
            brake_bias_enabled=True,
        )
    )

    assert biased.ato_target_speed_kmh < baseline.ato_target_speed_kmh


def test_am_brake_bias_below_one_does_not_make_target_speed_more_conservative():
    controller = _controller()

    baseline = controller.compute_am_command(
        _am_input(
            position_m=1420.0,
            speed_ms=8.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            brake_bias=1.0,
            brake_bias_enabled=True,
        )
    )
    biased = controller.compute_am_command(
        _am_input(
            position_m=1420.0,
            speed_ms=8.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            brake_bias=0.8,
            brake_bias_enabled=True,
        )
    )

    assert biased.ato_target_speed_kmh >= baseline.ato_target_speed_kmh
    assert biased.ato_target_speed_kmh <= 80.0


def test_am_creeps_near_stop_target():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1496.0, speed_ms=0.6, stop_target_m=1500.0)
    )

    assert "creep" in output.ato_state
    assert output.ato_target_speed_kmh <= controller.CRAWL_SPEED_MS * 3.6 + 0.001


def test_am_static_creep_uses_stronger_start_traction():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1496.8, speed_ms=0.0, stop_target_m=1500.0)
    )

    assert output.ato_state == "creep"
    assert output.ato_traction_level == controller.STATIC_CREEP_TRACTION_LEVEL
    assert output.commanded_traction_level == controller.STATIC_CREEP_TRACTION_LEVEL
    assert output.commanded_brake_level == 0


def test_am_static_creep_continues_until_stop_window():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1499.0, speed_ms=0.0, stop_target_m=1500.0)
    )

    assert output.ato_state == "creep"
    assert output.ato_traction_level == controller.STATIC_CREEP_TRACTION_LEVEL
    assert output.commanded_brake_level == 0


def test_am_creep_brakes_when_current_speed_exceeds_low_speed_target():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1496.0, speed_ms=0.8, stop_target_m=1500.0)
    )

    assert output.ato_state == "creep"
    assert output.ato_target_speed_kmh <= controller.CRAWL_SPEED_MS * 3.6 + 0.001
    assert output.commanded_brake_level > 0
    assert output.commanded_traction_level == 0


def test_am_holds_inside_stop_window_at_low_speed():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1499.7, speed_ms=0.1, stop_target_m=1500.0)
    )

    assert output.ato_state == "holding"
    assert output.holding_brake is True
    assert output.traction_level == 0
    assert output.brake_level == 4
    assert output.ato_traction_level == 0
    assert output.commanded_brake_level == 4


def test_holding_bypasses_jerk_limit():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(
            position_m=1499.7,
            speed_ms=0.1,
            stop_target_m=1500.0,
            previous_commanded_brake_level=0,
            jerk_limit_enabled=True,
        )
    )

    assert output.ato_state == "holding"
    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level == 4


def test_holding_is_not_weakened_by_brake_bias():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(
            position_m=1499.7,
            speed_ms=0.1,
            stop_target_m=1500.0,
            brake_bias=0.7,
            brake_bias_enabled=True,
        )
    )

    assert output.ato_state == "holding"
    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level == 4


def test_am_invalid_ma_degrades_without_traction():
    controller = _controller()

    output = controller.compute_am_command(_am_input(ma_limit_m=None))

    assert output.degraded is True
    assert output.traction_level == 0
    assert output.ato_traction_level == 0
    assert output.commanded_traction_level == 0
    assert output.applied_traction_level == 0
    assert output.brake_level >= 2
    assert output.control_source == "degraded"
    assert output.ato_target_speed_kmh == 0.0
    assert output.recommended_speed_kmh == 0.0


def test_degraded_bypasses_jerk_limit():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(
            ma_limit_m=None,
            previous_commanded_brake_level=0,
            jerk_limit_enabled=True,
        )
    )

    assert output.degraded is True
    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level >= 2


def test_degraded_is_not_weakened_by_brake_bias():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(
            ma_limit_m=None,
            brake_bias=0.7,
            brake_bias_enabled=True,
        )
    )

    assert output.degraded is True
    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level >= 2


def test_am_uses_ma_boundary_when_stop_target_is_beyond_ma():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1000.0, ma_limit_m=1200.0, stop_target_m=1500.0)
    )

    assert output.effective_target_m == 1200.0
    assert output.stop_target_m == 1500.0
    assert output.reason == "stop_target_beyond_ma"


def test_sm_only_recommends_speed_without_control_takeover():
    controller = _controller()

    output = controller.compute_control(
        AtoControlInput(
            vehicle_id="TRAIN-001",
            position_m=1000.0,
            speed_ms=10.0,
            ma_limit_m=2000.0,
            allowed_speed_kmh=50.0,
            stop_target_m=1500.0,
            driving_mode="SM",
        )
    )

    assert output.traction_level == 0
    assert output.brake_level == 0
    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level == 0
    assert output.applied_traction_level == 0
    assert output.applied_brake_level == 0
    assert output.control_source == "manual"
    assert output.recommended_speed_kmh <= 50.0
    assert "manual" in output.ato_state


def test_sm_does_not_apply_ato_jerk_limit_to_commanded_levels():
    controller = _controller()

    output = controller.compute_control(
        AtoControlInput(
            vehicle_id="TRAIN-001",
            position_m=1000.0,
            speed_ms=10.0,
            ma_limit_m=2000.0,
            allowed_speed_kmh=50.0,
            stop_target_m=1500.0,
            driving_mode="SM",
            previous_commanded_brake_level=4,
            jerk_limit_enabled=True,
        )
    )

    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level == 0
    assert output.control_source == "manual"
    assert output.recommended_speed_kmh >= 0.0


def test_unknown_driving_mode_falls_back_without_traction_takeover():
    controller = _controller()

    output = controller.compute_control(_am_input(driving_mode="UNKNOWN"))

    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level == 0
    assert output.control_source == "manual"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"ma_limit_m": None}, "missing_ma_limit"),
        ({"ma_limit_m": math.nan}, "invalid_ma_limit"),
        ({"ma_limit_m": math.inf}, "invalid_ma_limit"),
        ({"allowed_speed_kmh": None}, "missing_allowed_speed"),
        ({"allowed_speed_kmh": -1.0}, "invalid_allowed_speed"),
        ({"allowed_speed_kmh": 0.0}, "invalid_allowed_speed"),
        ({"ma_limit_m": 900.0}, "ma_behind_train"),
        ({"permission": "stop"}, "permission_denied"),
        ({"signal_state": "red"}, "signal_stop"),
        ({"target_distance_m": -1.0}, "negative_target_distance"),
        ({"ma_valid": False}, "ma_marked_invalid"),
        ({"comm_ok": False}, "comm_unhealthy"),
        ({"ma_age_sec": 2.0, "max_ma_age_sec": 1.0}, "ma_timeout"),
        ({"ma_age_sec": -1.0}, "invalid_ma_age"),
        ({"ma_age_sec": math.nan}, "invalid_ma_age"),
    ],
)
def test_am_ma_validity_failures_degrade(overrides, reason):
    controller = _controller()

    output = controller.compute_am_command(_am_input(**overrides))

    assert output.degraded is True
    assert output.ato_state == "degraded"
    assert output.reason == reason
    assert output.ato_traction_level == 0
    assert output.commanded_traction_level == 0
    assert output.applied_traction_level == 0
    assert output.commanded_brake_level >= 2
    assert output.recommended_speed_kmh == 0.0
    assert output.ato_target_speed_kmh == 0.0


def test_missing_ma_freshness_fields_keep_backward_compatibility():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(ma_valid=None, ma_age_sec=None, comm_ok=None)
    )

    assert output.degraded is False


def test_target_distance_falls_back_to_absolute_ma_distance():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1000.0, ma_limit_m=1500.0, target_distance_m=None)
    )

    assert output.distance_to_ma_m == 500.0


def test_target_distance_uses_more_conservative_value():
    controller = _controller()

    closer_target_distance = controller.compute_am_command(
        _am_input(position_m=1000.0, ma_limit_m=1500.0, target_distance_m=300.0)
    )
    farther_target_distance = controller.compute_am_command(
        _am_input(position_m=1000.0, ma_limit_m=1500.0, target_distance_m=700.0)
    )

    assert closer_target_distance.distance_to_ma_m == 300.0
    assert farther_target_distance.distance_to_ma_m == 500.0


def test_stop_target_uses_absolute_mileage_distance():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1000.0, stop_target_m=1500.0)
    )

    assert output.distance_to_stop_m == 500.0


def test_stop_target_behind_train_does_not_command_traction():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(position_m=1501.0, stop_target_m=1500.0, ma_limit_m=2000.0)
    )

    assert output.degraded is False
    assert output.reason == "stop_target_behind_train"
    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level >= 1
    assert output.ato_target_speed_kmh == 0.0


def test_delay_prediction_past_stop_target_does_not_command_traction():
    controller = _controller()

    output = controller.compute_am_command(
        _am_input(
            position_m=1499.0,
            speed_ms=5.0,
            stop_target_m=1500.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=60.0,
            control_delay_sec=0.5,
            delay_compensation_enabled=True,
        )
    )

    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level >= 1
    assert output.ato_target_speed_kmh == 0.0


def test_sm_low_speed_recommendation_uses_position_control():
    controller = _controller()

    output = controller.compute_control(
        AtoControlInput(
            vehicle_id="TRAIN-001",
            position_m=1496.0,
            speed_ms=0.8,
            ma_limit_m=1600.0,
            allowed_speed_kmh=60.0,
            stop_target_m=1500.0,
            driving_mode="SM",
        )
    )

    assert output.recommended_speed_kmh <= controller.CRAWL_SPEED_MS * 3.6 + 0.001
    assert output.commanded_traction_level == 0
    assert output.commanded_brake_level == 0
    assert output.control_source == "manual"


def test_sm_recommended_speed_uses_delay_prediction():
    controller = _controller()

    without_delay = controller.compute_control(
        AtoControlInput(
            vehicle_id="TRAIN-001",
            position_m=1480.0,
            speed_ms=10.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=60.0,
            stop_target_m=1500.0,
            driving_mode="SM",
            control_delay_sec=0.5,
            delay_compensation_enabled=False,
        )
    )
    with_delay = controller.compute_control(
        AtoControlInput(
            vehicle_id="TRAIN-001",
            position_m=1480.0,
            speed_ms=10.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=60.0,
            stop_target_m=1500.0,
            driving_mode="SM",
            control_delay_sec=0.5,
            delay_compensation_enabled=True,
        )
    )

    assert with_delay.recommended_speed_kmh <= without_delay.recommended_speed_kmh
    assert with_delay.commanded_traction_level == 0
    assert with_delay.commanded_brake_level == 0
    assert with_delay.control_source == "manual"


def test_sm_recommended_speed_uses_downhill_gradient_compensation():
    controller = _controller()

    flat = controller.compute_control(
        AtoControlInput(
            vehicle_id="TRAIN-001",
            position_m=1400.0,
            speed_ms=15.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            stop_target_m=1500.0,
            driving_mode="SM",
            gradient_permille=0.0,
            gradient_compensation_enabled=True,
        )
    )
    downhill = controller.compute_control(
        AtoControlInput(
            vehicle_id="TRAIN-001",
            position_m=1400.0,
            speed_ms=15.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            stop_target_m=1500.0,
            driving_mode="SM",
            gradient_permille=-30.0,
            gradient_compensation_enabled=True,
        )
    )

    assert downhill.recommended_speed_kmh <= flat.recommended_speed_kmh
    assert downhill.commanded_traction_level == 0
    assert downhill.commanded_brake_level == 0
    assert downhill.control_source == "manual"


def test_sm_recommended_speed_uses_brake_bias_without_control_takeover():
    controller = _controller()

    baseline = controller.compute_control(
        AtoControlInput(
            vehicle_id="TRAIN-001",
            position_m=1420.0,
            speed_ms=8.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            stop_target_m=1500.0,
            driving_mode="SM",
            brake_bias=1.0,
            brake_bias_enabled=True,
        )
    )
    biased = controller.compute_control(
        AtoControlInput(
            vehicle_id="TRAIN-001",
            position_m=1420.0,
            speed_ms=8.0,
            ma_limit_m=1600.0,
            allowed_speed_kmh=80.0,
            stop_target_m=1500.0,
            driving_mode="SM",
            brake_bias=1.3,
            brake_bias_enabled=True,
        )
    )

    assert biased.recommended_speed_kmh < baseline.recommended_speed_kmh
    assert biased.commanded_traction_level == 0
    assert biased.commanded_brake_level == 0
    assert biased.control_source == "manual"


def test_evaluate_stop_result_classifies_window_and_errors():
    controller = _controller()

    in_window = controller.evaluate_stop_result(
        vehicle_id="TRAIN-001",
        target_position_m=1500.0,
        actual_position_m=1500.3,
        speed_ms=0.05,
    )
    assert in_window.status == "in_window"
    assert in_window.qualified is True

    overshoot = controller.evaluate_stop_result(
        vehicle_id="TRAIN-001",
        target_position_m=1500.0,
        actual_position_m=1501.0,
        speed_ms=0.05,
    )
    assert overshoot.status == "overshoot"
    assert overshoot.qualified is False

    undershoot = controller.evaluate_stop_result(
        vehicle_id="TRAIN-001",
        target_position_m=1500.0,
        actual_position_m=1499.0,
        speed_ms=0.05,
    )
    assert undershoot.status == "undershoot"

    not_stopped = controller.evaluate_stop_result(
        vehicle_id="TRAIN-001",
        target_position_m=1500.0,
        actual_position_m=1500.0,
        speed_ms=1.0,
    )
    assert not_stopped.status == "not_stopped"
    assert not_stopped.qualified is False
