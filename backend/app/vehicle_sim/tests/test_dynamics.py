from math import isfinite

import pytest

from app.vehicle_sim.dynamics import (
    calc_brake_force,
    calc_gradient_resistance,
    calc_running_resistance,
    calc_traction_force,
    clamp_level,
    interpolate_curve,
    motor_rpm_to_vehicle_speed,
    torque_to_wheel_force,
    update_dynamics,
    vehicle_speed_to_motor_rpm,
)
from app.vehicle_sim.vehicle_parameters import (
    BRAKE_TORQUE_NM_52,
    GEAR_RATIO,
    MOTOR_COUNT,
    MOTOR_SPEED_RPM_52,
    TRACTION_TORQUE_NM_52,
    TRAIN_LENGTH_M,
    TRAIN_MASS_KG,
    WHEEL_RADIUS_M,
)


def test_supplied_vehicle_parameters_are_used():
    assert TRAIN_MASS_KG == 225_000.0
    assert TRAIN_LENGTH_M == 118.0
    assert WHEEL_RADIUS_M == 0.46
    assert MOTOR_COUNT == 16
    assert len(MOTOR_SPEED_RPM_52) == 52
    assert len(TRACTION_TORQUE_NM_52) == 52
    assert len(BRAKE_TORQUE_NM_52) == 52


def test_estimated_ratio_maps_curve_endpoint_to_speed_margin():
    speed_kmh = motor_rpm_to_vehicle_speed(4160.1) * 3.6
    assert speed_kmh == pytest.approx(92.6, abs=0.2)
    assert vehicle_speed_to_motor_rpm(speed_kmh / 3.6) == pytest.approx(4160.1)


@pytest.mark.parametrize("speed_ms", [0.0, 1.0, 10.0, 25.0])
def test_speed_and_motor_rpm_conversion_round_trips_si_units(speed_ms):
    motor_rpm = vehicle_speed_to_motor_rpm(speed_ms)
    assert motor_rpm_to_vehicle_speed(motor_rpm) == pytest.approx(speed_ms)


def test_negative_speed_and_motor_rpm_are_clamped_to_zero():
    assert vehicle_speed_to_motor_rpm(-1.0) == 0.0
    assert motor_rpm_to_vehicle_speed(-1.0) == 0.0


def test_curve_interpolation_uses_adjacent_52_point_values():
    rpm = (2496.1 + 2579.3) / 2.0
    expected = (1036.8 + 971.0) / 2.0
    assert interpolate_curve(rpm, TRACTION_TORQUE_NM_52) == pytest.approx(expected)


def test_curve_interpolation_clamps_values_outside_rpm_range():
    assert interpolate_curve(-100.0, TRACTION_TORQUE_NM_52) == pytest.approx(
        TRACTION_TORQUE_NM_52[0]
    )
    assert interpolate_curve(10_000.0, TRACTION_TORQUE_NM_52) == pytest.approx(
        TRACTION_TORQUE_NM_52[-1]
    )


def test_torque_is_converted_to_total_wheel_force():
    expected = 1042.9 * GEAR_RATIO / WHEEL_RADIUS_M * MOTOR_COUNT
    assert torque_to_wheel_force(1042.9) == pytest.approx(expected)
    assert calc_traction_force(4, speed_ms=0.0) == pytest.approx(expected)


@pytest.mark.parametrize("level", range(5))
def test_traction_levels_zero_to_four_scale_force_linearly(level):
    full_force = calc_traction_force(4, speed_ms=10.0)
    assert calc_traction_force(level, speed_ms=10.0) == pytest.approx(
        full_force * level / 4
    )


@pytest.mark.parametrize("level", range(5))
def test_brake_levels_zero_to_four_scale_force_linearly(level):
    full_force = calc_brake_force(4, speed_ms=10.0)
    assert calc_brake_force(level, speed_ms=10.0) == pytest.approx(
        full_force * level / 4
    )


def test_control_levels_are_clamped_to_zero_through_four():
    assert clamp_level(-1) == 0
    assert clamp_level(5) == 4
    assert calc_traction_force(-1, speed_ms=10.0) == 0.0
    assert calc_traction_force(5, speed_ms=10.0) == pytest.approx(
        calc_traction_force(4, speed_ms=10.0)
    )
    assert calc_brake_force(-1, speed_ms=10.0) == 0.0
    assert calc_brake_force(5, speed_ms=10.0) == pytest.approx(
        calc_brake_force(4, speed_ms=10.0)
    )


def test_traction_force_follows_speed_dependent_curve():
    forces = [calc_traction_force(4, speed_ms=speed) for speed in (10.0, 20.0, 25.0)]
    assert forces[0] > forces[1] > forces[2] > 0.0


@pytest.mark.parametrize(
    ("power_factor", "expected_ratio"),
    [(-1.0, 0.0), (0.0, 0.0), (0.25, 0.25), (1.0, 1.0), (2.0, 1.0)],
)
def test_power_factor_scales_and_clamps_traction(power_factor, expected_ratio):
    full_force = calc_traction_force(4, speed_ms=10.0, power_factor=1.0)
    actual = calc_traction_force(4, speed_ms=10.0, power_factor=power_factor)
    assert actual == pytest.approx(full_force * expected_ratio)


def test_brake_curve_builds_force_from_zero_at_low_speed():
    assert calc_brake_force(4, speed_ms=0.0) == 0.0

    zero_force_speed = motor_rpm_to_vehicle_speed(83.2)
    transition_speed = motor_rpm_to_vehicle_speed((83.2 + 166.4) / 2.0)
    full_force_speed = motor_rpm_to_vehicle_speed(166.4)
    rated_force = torque_to_wheel_force(977.7)

    assert calc_brake_force(4, speed_ms=zero_force_speed) == 0.0
    assert calc_brake_force(4, speed_ms=transition_speed) == pytest.approx(
        rated_force / 2.0
    )
    assert calc_brake_force(4, speed_ms=full_force_speed) == pytest.approx(
        rated_force
    )


def test_davis_resistance_uses_speed_in_kmh():
    speed_ms = 10.0
    speed_kmh = 36.0
    expected = (
        6.4 * 225.0
        + 130.0 * 24
        + 0.14 * 225.0 * speed_kmh
        + (0.046 + 0.0065 * 5) * 10.6 * speed_kmh**2
    )
    assert calc_running_resistance(speed_ms) == pytest.approx(expected)


@pytest.mark.parametrize("gradient_permille", [-20.0, 0.0, 20.0])
def test_gradient_resistance_uses_permille_units(gradient_permille):
    expected = TRAIN_MASS_KG * 9.80665 * gradient_permille / 1000.0
    assert calc_gradient_resistance(gradient_permille) == pytest.approx(expected)


def test_uphill_and_downhill_gradients_change_acceleration_directionally():
    results = {}
    for gradient in (-20.0, 0.0, 20.0):
        results[gradient] = update_dynamics(
            speed_ms=10.0,
            position=100.0,
            traction_level=0,
            brake_level=0,
            gradient=gradient,
            dt=0.1,
        )

    downhill_speed, downhill_position, downhill_acceleration, _, _ = results[-20.0]
    flat_speed, flat_position, flat_acceleration, _, _ = results[0.0]
    uphill_speed, uphill_position, uphill_acceleration, _, _ = results[20.0]

    assert downhill_acceleration > flat_acceleration > uphill_acceleration
    assert downhill_speed > flat_speed > uphill_speed
    assert downhill_position > flat_position > uphill_position


def test_brake_overrides_traction_and_reduces_speed():
    new_speed, _, acceleration, traction_force, brake_force = update_dynamics(
        speed_ms=10.0,
        position=100.0,
        traction_level=4,
        brake_level=4,
        gradient=0.0,
        dt=0.1,
    )
    assert traction_force == 0.0
    assert brake_force > 0.0
    assert acceleration < 0.0
    assert new_speed < 10.0


def test_zero_power_factor_disables_traction_in_dynamics_update():
    _, _, _, traction_force, _ = update_dynamics(
        speed_ms=10.0,
        position=100.0,
        traction_level=4,
        brake_level=0,
        gradient=0.0,
        dt=0.1,
        power_factor=0.0,
    )
    assert traction_force == 0.0


def test_emergency_brake_uses_full_brake_and_clears_traction():
    new_speed, _, acceleration, traction_force, brake_force = update_dynamics(
        speed_ms=10.0,
        position=100.0,
        traction_level=4,
        brake_level=0,
        gradient=0.0,
        dt=0.1,
        emergency_brake=True,
    )
    assert traction_force == 0.0
    assert brake_force == pytest.approx(calc_brake_force(4, speed_ms=10.0))
    assert acceleration < 0.0
    assert new_speed < 10.0


def test_position_integrates_new_speed_in_metres_and_seconds():
    dt = 0.02
    position = 123.0
    new_speed, new_position, _, _, _ = update_dynamics(
        speed_ms=10.0,
        position=position,
        traction_level=0,
        brake_level=0,
        gradient=0.0,
        dt=dt,
    )
    assert new_position == pytest.approx(position + new_speed * dt)


def test_twenty_millisecond_long_run_remains_finite_and_stops_safely():
    dt = 0.02
    speed = 0.0
    position = 0.0

    for traction_level, brake_level in ((4, 0), (0, 4)):
        for _ in range(3_000):
            previous_position = position
            speed, position, acceleration, traction_force, brake_force = update_dynamics(
                speed_ms=speed,
                position=position,
                traction_level=traction_level,
                brake_level=brake_level,
                gradient=0.0,
                dt=dt,
            )
            assert all(
                isfinite(value)
                for value in (speed, position, acceleration, traction_force, brake_force)
            )
            assert speed >= 0.0
            assert position >= previous_position

        if traction_level == 4:
            assert 20.0 < speed < 50.0

    assert speed == 0.0
    assert position > 0.0


@pytest.mark.parametrize("dt", [0.0, -0.02])
def test_non_positive_dt_is_rejected(dt):
    with pytest.raises(ValueError):
        update_dynamics(0.0, 0.0, 0, 0, 0.0, dt)
