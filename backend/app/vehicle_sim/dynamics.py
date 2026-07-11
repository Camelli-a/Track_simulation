MAX_TRACTION_FORCE = 80000.0
MAX_BRAKE_FORCE = 100000.0
MAX_EMERGENCY_BRAKE_FORCE = 140000.0
TRAIN_MASS = 40000.0
MAX_LEVEL = 4


def clamp_level(level: int) -> int:
    return max(0, min(level, MAX_LEVEL))


def calc_traction_force(level: int, power_factor: float = 1.0) -> float:
    """Map traction level 0..4 to traction force in N."""
    level = clamp_level(level)
    power_factor = max(0.0, min(power_factor, 1.0))
    return MAX_TRACTION_FORCE * (level / MAX_LEVEL) * power_factor


def calc_brake_force(level: int) -> float:
    """Map brake level 0..4 to brake force in N."""
    level = clamp_level(level)
    return MAX_BRAKE_FORCE * (level / MAX_LEVEL)


def calc_running_resistance(speed_ms: float) -> float:
    """Simplified running resistance; grows with speed."""
    return 1000.0 + 30.0 * speed_ms + 5.0 * speed_ms * speed_ms


def calc_gradient_resistance(gradient_permille: float) -> float:
    """Gradient resistance in N. Positive means uphill, negative downhill."""
    return TRAIN_MASS * 9.8 * (gradient_permille / 1000.0)


def update_dynamics(
    speed_ms: float,
    position: float,
    traction_level: int,
    brake_level: int,
    gradient: float,
    dt: float,
    power_factor: float = 1.0,
    emergency_brake: bool = False,
):
    """Update train speed and position for one simulation tick."""
    if dt <= 0:
        raise ValueError("dt must be positive")

    if emergency_brake:
        traction_force = 0.0
        brake_force = MAX_EMERGENCY_BRAKE_FORCE
    else:
        # Brake wins if traction and brake commands conflict.
        if brake_level > 0:
            traction_level = 0

        traction_force = calc_traction_force(traction_level, power_factor)
        brake_force = calc_brake_force(brake_level)

    running_resistance = calc_running_resistance(speed_ms)
    gradient_resistance = calc_gradient_resistance(gradient)

    net_force = traction_force - brake_force - running_resistance - gradient_resistance
    acceleration = net_force / TRAIN_MASS

    new_speed_ms = max(0.0, speed_ms + acceleration * dt)
    new_position = position + new_speed_ms * dt

    # Avoid tiny negative/near-zero drift after braking to a stop.
    if new_speed_ms <= 0.001:
        new_speed_ms = 0.0
        acceleration = 0.0

    return new_speed_ms, new_position, acceleration, traction_force, brake_force
