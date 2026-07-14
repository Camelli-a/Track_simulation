import pytest

from app.vehicle_sim.models import MaLimit
from app.vehicle_sim.train_manager import TrainManager


def _single_train(vehicle_id="TRAIN-001", slot=1, position=100.0):
    manager = TrainManager(initial_count=0)
    manager.add_train(vehicle_id=vehicle_id, slot=slot, position=position)
    return manager, manager.get_train(vehicle_id)


def _apply_ma(train, ma_limit=500.0, allowed_speed=80.0, distance=400.0):
    train.apply_ma_state(
        MaLimit(
            vehicle_id=train.state.vehicle_id,
            ma_limit=ma_limit,
            target_speed=allowed_speed,
            reason="test",
            allowed_speed_kmh=allowed_speed,
            eb_trigger_speed_kmh=allowed_speed + 10.0,
            target_distance_m=distance,
            permission="allow",
            signal_state="green",
        )
    )


def test_step_tick_generates_curve_point():
    _, train = _single_train()
    train.state.speed_ms = 5.0
    train.next_stop_target_m = 300.0
    _apply_ma(train)

    train.step_tick(0.1)

    curve_point = train.last_curve_point
    assert curve_point is not None
    assert curve_point["vehicle_id"] == "TRAIN-001"
    assert "position_m" in curve_point
    assert "speed_mps" in curve_point
    assert "speed_kmh" in curve_point
    assert curve_point["time_s"] >= 0.1


def test_curve_point_speed_units_are_consistent():
    _, train = _single_train()
    train.state.speed_ms = 10.0

    curve_point = train._build_curve_point()

    assert curve_point["speed_mps"] == 10.0
    assert curve_point["speed_kmh"] == 36.0


def test_curve_point_recommended_and_target_speed_units_are_consistent():
    _, train = _single_train()
    train.recommended_speed = 36.0
    train.ato_target_speed = 18.0

    curve_point = train._build_curve_point()

    assert curve_point["recommended_speed_kmh"] == 36.0
    assert curve_point["recommended_speed_mps"] == 10.0
    assert curve_point["ato_target_speed_kmh"] == 18.0
    assert curve_point["ato_target_speed_mps"] == 5.0


def test_curve_point_ma_safety_boundary_fields():
    _, train = _single_train(position=100.0)
    train.ma_limit = 500.0
    train.allowed_speed_kmh = 80.0
    train.eb_trigger_speed_kmh = 90.0

    curve_point = train._build_curve_point()

    assert train.track.get_speed_limit(100.0) == pytest.approx(47.988)
    assert curve_point["allowed_speed_kmh"] == pytest.approx(80.0)
    assert curve_point["ma_allowed_speed_kmh"] == 80.0
    assert curve_point["track_speed_limit_kmh"] == pytest.approx(90.0)
    assert curve_point["eb_trigger_speed_kmh"] == 90.0
    assert curve_point["ma_limit_m"] == 500.0
    assert curve_point["distance_to_ma_m"] == 400.0


def test_curve_point_exposes_speed_limit_preview_warning():
    _, train = _single_train(position=2035.0)
    train.apply_ma_state(
        MaLimit(
            vehicle_id="TRAIN-001",
            ma_limit=2500.0,
            target_speed=35.0,
            reason="route_end",
            allowed_speed_kmh=35.0,
            target_distance_m=465.0,
            permission="allow",
            signal_state="green",
            speed_limit_reason="static_limit_preview",
            speed_limit_warning=True,
            upcoming_speed_limit_kmh=35.0,
            speed_limit_warning_distance_m=19.9,
        )
    )

    curve_point = train._build_curve_point()

    assert curve_point["speed_limit_reason"] == "static_limit_preview"
    assert curve_point["speed_limit_warning"] is True
    assert curve_point["upcoming_speed_limit_kmh"] == pytest.approx(35.0)
    assert curve_point["speed_limit_warning_distance_m"] == pytest.approx(19.9)


def test_curve_point_stop_target_fields():
    _, train = _single_train(position=100.0)
    train.next_stop_target_m = 300.0

    curve_point = train._build_curve_point()

    assert curve_point["stop_target_m"] == 300.0
    assert curve_point["distance_to_stop_m"] == 200.0


def test_curve_point_contains_control_level_fields():
    _, train = _single_train()

    curve_point = train._build_curve_point()

    for field in [
        "ato_traction_level",
        "ato_brake_level",
        "commanded_traction_level",
        "commanded_brake_level",
        "applied_traction_level",
        "applied_brake_level",
    ]:
        assert field in curve_point


def test_curve_point_contains_control_state_fields():
    _, train = _single_train()

    curve_point = train._build_curve_point()

    for field in [
        "driving_mode",
        "control_source",
        "ato_state",
        "atp_intervened",
        "emergency_brake",
        "degraded",
    ]:
        assert field in curve_point


def test_curve_history_is_limited_to_configured_size():
    _, train = _single_train()
    train.curve_history_size = 3
    train.state.speed_ms = 1.0
    train.next_stop_target_m = 300.0
    _apply_ma(train)

    for _ in range(5):
        train.step_tick(0.1)

    assert len(train.curve_history) == 3
    assert train.last_curve_point == train.curve_history[-1]


def test_train_state_protocol_outputs_curve_point():
    manager, train = _single_train()
    train.state.speed_ms = 1.0
    train.next_stop_target_m = 300.0
    _apply_ma(train)

    states = manager.step_all(0.1)
    state = states[0]

    assert state["curve_output_enabled"] is True
    assert state["curve_history_size"] == 300
    assert state["curve_point"] is not None
    assert state["curve_point"]["vehicle_id"] == state["vehicle_id"]


def test_single_train_process_outputs_only_owned_curve_point():
    manager, train = _single_train(vehicle_id="TRAIN-002", slot=2, position=300.0)
    train.state.speed_ms = 1.0
    train.next_stop_target_m = 500.0
    _apply_ma(train, ma_limit=700.0, distance=400.0)

    states = manager.step_all(0.1)

    assert len(states) == 1
    assert states[0]["vehicle_id"] == "TRAIN-002"
    assert states[0]["curve_point"]["vehicle_id"] == "TRAIN-002"
