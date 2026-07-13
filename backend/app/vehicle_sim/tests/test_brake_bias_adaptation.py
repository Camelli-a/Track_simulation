import pytest

from app.vehicle_sim.controllers.train_ato_controller import AtoControlInput
from app.vehicle_sim.train_manager import TrainManager


def _train_with_stop_result(
    *,
    error_m: float,
    speed_ms: float = 0.0,
    target_position_m: float = 1000.0,
    driving_mode: str = "AM",
):
    manager = TrainManager(initial_count=0)
    manager.add_train(vehicle_id="TRAIN-001", slot=1, position=900.0)
    train = manager.get_train("TRAIN-001")
    train.driving_mode = driving_mode
    train.ato_brake_bias_enabled = True
    train.ato_brake_bias_adaptation_enabled = True
    train.ato_brake_bias = 1.0
    train.last_ato_output = train.train_ato_controller.compute_am_command(
        AtoControlInput(
            vehicle_id=train.state.vehicle_id,
            position_m=900.0,
            speed_ms=5.0,
            ma_limit_m=1200.0,
            allowed_speed_kmh=60.0,
            stop_target_m=target_position_m,
            driving_mode="AM",
        )
    )
    train.last_stop_result = train.train_ato_controller.evaluate_stop_result(
        vehicle_id=train.state.vehicle_id,
        target_position_m=target_position_m,
        actual_position_m=target_position_m + error_m,
        speed_ms=speed_ms,
    )
    return train


def test_overshoot_increases_brake_bias():
    train = _train_with_stop_result(error_m=0.5)

    train._maybe_adapt_brake_bias_from_stop_result()

    assert train.ato_brake_bias > 1.0
    assert train.last_brake_bias_adjustment is not None
    assert train.last_brake_bias_adjustment["delta"] > 0
    assert round(1000.0, 2) in train.ato_brake_bias_adapted_targets


def test_undershoot_decreases_brake_bias():
    train = _train_with_stop_result(error_m=-0.5)

    train._maybe_adapt_brake_bias_from_stop_result()

    assert train.ato_brake_bias < 1.0
    assert train.last_brake_bias_adjustment is not None
    assert train.last_brake_bias_adjustment["delta"] < 0


def test_error_inside_deadband_does_not_adjust_brake_bias():
    train = _train_with_stop_result(error_m=0.05)

    train._maybe_adapt_brake_bias_from_stop_result()

    assert train.ato_brake_bias == pytest.approx(1.0)
    assert train.last_brake_bias_adjustment is None
    assert train.ato_brake_bias_history == []


def test_same_stop_target_adjusts_only_once():
    train = _train_with_stop_result(error_m=0.5)

    train._maybe_adapt_brake_bias_from_stop_result()
    first_bias = train.ato_brake_bias
    first_history_length = len(train.ato_brake_bias_history)
    train._maybe_adapt_brake_bias_from_stop_result()

    assert train.ato_brake_bias == pytest.approx(first_bias)
    assert len(train.ato_brake_bias_history) == first_history_length


def test_atp_intervention_does_not_adjust_brake_bias():
    train = _train_with_stop_result(error_m=1.0)
    train.atp_intervened = True

    train._maybe_adapt_brake_bias_from_stop_result()

    assert train.ato_brake_bias == pytest.approx(1.0)


def test_degraded_ato_output_does_not_adjust_brake_bias():
    train = _train_with_stop_result(error_m=1.0)
    train.last_ato_output = train.train_ato_controller.compute_am_command(
        AtoControlInput(
            vehicle_id=train.state.vehicle_id,
            position_m=900.0,
            speed_ms=5.0,
            ma_limit_m=None,
            allowed_speed_kmh=60.0,
            stop_target_m=1000.0,
            driving_mode="AM",
        )
    )

    train._maybe_adapt_brake_bias_from_stop_result()

    assert train.ato_brake_bias == pytest.approx(1.0)


def test_emergency_does_not_adjust_brake_bias():
    train = _train_with_stop_result(error_m=1.0)
    train.state.emergency_brake = True

    train._maybe_adapt_brake_bias_from_stop_result()

    assert train.ato_brake_bias == pytest.approx(1.0)


def test_sm_mode_does_not_adjust_brake_bias():
    train = _train_with_stop_result(error_m=1.0, driving_mode="SM")

    train._maybe_adapt_brake_bias_from_stop_result()

    assert train.ato_brake_bias == pytest.approx(1.0)


def test_brake_bias_delta_is_limited_per_stop():
    train = _train_with_stop_result(error_m=10.0)

    train._maybe_adapt_brake_bias_from_stop_result()

    assert abs(train.last_brake_bias_adjustment["delta"]) <= 0.05
    assert train.ato_brake_bias == pytest.approx(1.05)


def test_brake_bias_is_clamped_to_safe_range():
    overshoot_train = _train_with_stop_result(error_m=10.0)
    overshoot_train.ato_brake_bias = 1.49

    overshoot_train._maybe_adapt_brake_bias_from_stop_result()

    assert overshoot_train.ato_brake_bias <= 1.5

    undershoot_train = _train_with_stop_result(error_m=-10.0)
    undershoot_train.ato_brake_bias = 0.71

    undershoot_train._maybe_adapt_brake_bias_from_stop_result()

    assert undershoot_train.ato_brake_bias >= 0.7


def test_train_state_outputs_brake_bias_adaptation_debug_fields():
    train = _train_with_stop_result(error_m=0.5)

    train._maybe_adapt_brake_bias_from_stop_result()
    train._sync_control_state_to_train_state()
    protocol = train.state.to_protocol()

    assert protocol["ato_brake_bias_adaptation_enabled"] is True
    assert protocol["last_brake_bias_adjustment"] is not None
    assert protocol["last_brake_bias_adjustment"]["error_m"] == pytest.approx(0.5)
    assert protocol["brake_bias_history_size"] == 1
