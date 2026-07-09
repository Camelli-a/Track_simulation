from app.vehicle_sim.controllers.fallback_ato import FallbackAtoController


def test_fallback_ato_tractions_when_far_and_below_curve():
    controller = FallbackAtoController(target_position=1500.0, target_speed_kmh=35.0)

    traction, brake, phase = controller.compute(position=1200.0, speed_kmh=10.0)

    assert traction > 0
    assert brake == 0
    assert phase in {"fallback_recover_traction", "fallback_cruise_traction"}


def test_fallback_ato_brakes_when_above_braking_curve():
    controller = FallbackAtoController(target_position=1500.0, target_speed_kmh=35.0)

    traction, brake, phase = controller.compute(position=1485.0, speed_kmh=30.0)

    assert traction == 0
    assert brake >= 2
    assert phase.startswith("fallback_")


def test_fallback_ato_creeps_when_stopped_short_of_target():
    controller = FallbackAtoController(target_position=1500.0, target_speed_kmh=35.0)

    traction, brake, phase = controller.compute(position=1490.0, speed_kmh=0.0)

    assert traction == 1
    assert brake == 0
    assert phase == "fallback_precision_creep"


def test_fallback_ato_holds_inside_precision_window():
    controller = FallbackAtoController(target_position=1500.0, target_speed_kmh=35.0)

    traction, brake, phase = controller.compute(position=1499.5, speed_kmh=0.2)

    assert traction == 0
    assert brake == 1
    assert phase == "fallback_stop_hold"


def test_fallback_ato_uses_full_brake_after_overshoot():
    controller = FallbackAtoController(target_position=1500.0, target_speed_kmh=35.0)

    traction, brake, phase = controller.compute(position=1502.0, speed_kmh=3.0)

    assert traction == 0
    assert brake == 4
    assert phase == "fallback_overshoot_emergency_brake"
