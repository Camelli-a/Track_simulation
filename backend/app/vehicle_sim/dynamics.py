"""Longitudinal train dynamics using the supplied DKZ33 motor curves."""

from bisect import bisect_right
from math import pi

from .vehicle_parameters import (
    BRAKE_TORQUE_NM_52,
    DAVIS_AXLE_COUNT,
    DAVIS_CAR_COUNT,
    DAVIS_FRONTAL_AREA_M2,
    DAVIS_MASS_T,
    GEAR_RATIO,
    MAX_CONTROL_LEVEL,
    MOTOR_COUNT,
    MOTOR_SPEED_RPM_52,
    TRACTION_TORQUE_NM_52,
    TRAIN_MASS_KG,
    WHEEL_RADIUS_M,
)

# Backward-compatible aliases for callers that imported the old constants.
TRAIN_MASS = TRAIN_MASS_KG
MAX_LEVEL = MAX_CONTROL_LEVEL


def clamp_level(level: int) -> int:
    return max(0, min(int(level), MAX_CONTROL_LEVEL))


def vehicle_speed_to_motor_rpm(speed_ms: float) -> float:
    """Convert vehicle speed in m/s to motor speed in r/min."""
    wheel_rpm = max(0.0, speed_ms) / (2.0 * pi * WHEEL_RADIUS_M) * 60.0
    return wheel_rpm * GEAR_RATIO


def motor_rpm_to_vehicle_speed(motor_rpm: float) -> float:
    """Convert motor speed in r/min to vehicle speed in m/s."""
    wheel_rpm = max(0.0, motor_rpm) / GEAR_RATIO
    return wheel_rpm * (2.0 * pi * WHEEL_RADIUS_M) / 60.0


def interpolate_curve(motor_rpm: float, values: tuple[float, ...]) -> float:
    """Linearly interpolate a 52-point motor curve and clamp its endpoints."""
    rpm = max(0.0, float(motor_rpm))
    if rpm <= MOTOR_SPEED_RPM_52[0]:
        return values[0]
    if rpm >= MOTOR_SPEED_RPM_52[-1]:
        return values[-1]

    upper = bisect_right(MOTOR_SPEED_RPM_52, rpm)
    lower = upper - 1
    rpm0 = MOTOR_SPEED_RPM_52[lower]
    rpm1 = MOTOR_SPEED_RPM_52[upper]
    if rpm1 == rpm0:
        return values[upper]
    ratio = (rpm - rpm0) / (rpm1 - rpm0)
    return values[lower] + ratio * (values[upper] - values[lower])


def torque_to_wheel_force(torque_nm: float) -> float:
    """Convert per-motor torque to total wheel-rail longitudinal force."""
    return max(0.0, torque_nm) * GEAR_RATIO / WHEEL_RADIUS_M * MOTOR_COUNT


def calc_traction_force(
    level: int,
    speed_ms: float = 0.0,
    power_factor: float = 1.0,
) -> float:
    """Calculate traction force from control level and the motor curve."""
    level_factor = clamp_level(level) / MAX_CONTROL_LEVEL
    available_power = max(0.0, min(float(power_factor), 1.0))
    torque_nm = interpolate_curve(
        vehicle_speed_to_motor_rpm(speed_ms), TRACTION_TORQUE_NM_52
    )
    return torque_to_wheel_force(torque_nm) * level_factor * available_power


def calc_traction_force_percent(
    percent: float,
    speed_ms: float = 0.0,
    power_factor: float = 1.0,
) -> float:
    """Calculate traction force from the canonical 0..100% control request."""
    request = max(0.0, min(float(percent), 100.0)) / 100.0
    available_power = max(0.0, min(float(power_factor), 1.0))
    torque_nm = interpolate_curve(
        vehicle_speed_to_motor_rpm(speed_ms), TRACTION_TORQUE_NM_52
    )
    return torque_to_wheel_force(torque_nm) * request * available_power


def calc_brake_force(level: int, speed_ms: float = 0.0) -> float:
    """Calculate braking force from control level and the motor curve."""
    level_factor = clamp_level(level) / MAX_CONTROL_LEVEL
    torque_nm = interpolate_curve(
        vehicle_speed_to_motor_rpm(speed_ms), BRAKE_TORQUE_NM_52
    )
    return torque_to_wheel_force(torque_nm) * level_factor


def calc_brake_force_percent(percent: float, speed_ms: float = 0.0) -> float:
    """Calculate service-brake force from the canonical 0..100% request."""
    request = max(0.0, min(float(percent), 100.0)) / 100.0
    torque_nm = interpolate_curve(
        vehicle_speed_to_motor_rpm(speed_ms), BRAKE_TORQUE_NM_52
    )
    return torque_to_wheel_force(torque_nm) * request


def calc_running_resistance(speed_ms: float) -> float:
    """Calculate Davis running resistance in N (formula speed is km/h)."""
    speed_kmh = max(0.0, float(speed_ms)) * 3.6
    return (
        6.4 * DAVIS_MASS_T
        + 130.0 * DAVIS_AXLE_COUNT
        + 0.14 * DAVIS_MASS_T * speed_kmh
        + (0.046 + 0.0065 * (DAVIS_CAR_COUNT - 1))
        * DAVIS_FRONTAL_AREA_M2
        * speed_kmh**2
    )


def calc_gradient_resistance(gradient_permille: float) -> float:
    """Gradient resistance in N; positive is uphill, negative downhill."""
    return TRAIN_MASS_KG * 9.80665 * (float(gradient_permille) / 1000.0)


def update_dynamics(
    speed_ms: float,
    position: float,
    traction_level: int,
    brake_level: int,
    gradient: float,
    dt: float,
    power_factor: float = 1.0,
    emergency_brake: bool = False,
    traction_percent: float | None = None,
    brake_percent: float | None = None,
    direction_sign: int = 1,
):
    """Update SI-unit speed and position for one simulation tick."""
    if dt <= 0:
        raise ValueError("dt must be positive")

    if emergency_brake:
        traction_force = 0.0
        brake_force = calc_brake_force_percent(100.0, speed_ms)
    else:
        resolved_traction_percent = (
            clamp_level(traction_level) / MAX_CONTROL_LEVEL * 100.0
            if traction_percent is None
            else max(0.0, min(float(traction_percent), 100.0))
        )
        resolved_brake_percent = (
            clamp_level(brake_level) / MAX_CONTROL_LEVEL * 100.0
            if brake_percent is None
            else max(0.0, min(float(brake_percent), 100.0))
        )
        if resolved_brake_percent > 0.0:  # Brake wins on conflicting commands.
            traction_level = 0
            resolved_traction_percent = 0.0
        traction_force = calc_traction_force_percent(
            resolved_traction_percent, speed_ms, power_factor
        )
        brake_force = calc_brake_force_percent(resolved_brake_percent, speed_ms)

    running_resistance = calc_running_resistance(speed_ms)
    gradient_resistance = calc_gradient_resistance(gradient)
    net_force = traction_force - brake_force - running_resistance - gradient_resistance
    acceleration = net_force / TRAIN_MASS_KG

    new_speed_ms = max(0.0, speed_ms + acceleration * dt)
    travel_sign = -1 if int(direction_sign) < 0 else 1
    new_position = position + travel_sign * new_speed_ms * dt
    if new_speed_ms <= 0.001:
        new_speed_ms = 0.0
        acceleration = 0.0

    return new_speed_ms, new_position, acceleration, traction_force, brake_force
