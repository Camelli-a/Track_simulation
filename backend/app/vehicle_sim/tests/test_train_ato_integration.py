import pytest

from app.vehicle_sim.models import MaLimit
from app.vehicle_sim.train_manager import TrainManager


def _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=30.0, distance=600.0):
    train.apply_ma_state(
        MaLimit(
            vehicle_id=train.state.vehicle_id,
            ma_limit=ma_limit,
            target_speed=allowed_speed,
            reason="test",
            allowed_speed_kmh=allowed_speed,
            eb_trigger_speed_kmh=allowed_speed + 8.0,
            target_distance_m=distance,
            permission="allow",
            signal_state="green",
        )
    )


def test_train_initializes_train_ato_controller_and_control_fields():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")

    assert train.train_ato_controller is not None
    assert train.driving_mode == "SM"
    assert train.last_ato_output is None
    assert train.commanded_traction_level == 0
    assert train.commanded_brake_level == 0
    assert train.applied_traction_level == 0
    assert train.applied_brake_level == 0
    assert train.control_source == "manual"
    assert train.atp_intervened is False
    assert train.ato_brake_bias_enabled is True
    assert train.ato_brake_bias == pytest.approx(1.0)


def test_step_tick_am_uses_train_ato_controller_command():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1000.0
    train.driving_mode = "AM"
    train.cached_traction_level = 4
    train.cached_brake_level = 0
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=30.0, distance=600.0)

    train.step_tick(0.1)

    assert train.last_ato_output is not None
    assert train.control_source == "ato"
    assert train.commanded_traction_level == train.last_ato_output.commanded_traction_level
    assert train.commanded_brake_level == train.last_ato_output.commanded_brake_level
    assert train.commanded_traction_level != 4
    assert train.state.mode == "ato"


def test_step_tick_sm_uses_cached_driver_command_but_computes_recommendation():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1000.0
    train.driving_mode = "SM"
    train.cached_traction_level = 2
    train.cached_brake_level = 0
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=30.0, distance=600.0)

    train.step_tick(0.1)

    assert train.last_ato_output is not None
    assert train.recommended_speed > 0.0
    assert train.commanded_traction_level == 2
    assert train.commanded_brake_level == 0
    assert train.control_source == "manual"
    assert train.state.mode == "manual"


def test_step_tick_am_degraded_does_not_continue_traction():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.driving_mode = "AM"
    train.cached_traction_level = 4
    train.cached_brake_level = 0

    train.step_tick(0.1)

    assert train.last_ato_output is not None
    assert train.last_ato_output.degraded is True
    assert train.commanded_traction_level == 0
    assert train.commanded_brake_level >= 2
    assert train.control_source == "degraded"


def test_step_tick_emergency_does_not_modify_driving_mode():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.driving_mode = "AM"
    train.state.emergency_brake = True
    _apply_valid_ma(train)

    train.step_tick(0.1)

    assert train.driving_mode == "AM"
    assert train.state.mode == "emergency"
    assert train.control_source == "emergency"
    assert train.applied_traction_level == 0
    assert train.applied_brake_level == 4


def test_step_tick_records_applied_levels_after_atp_intervention():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.speed_ms = 30.0
    train.cached_traction_level = 2
    train.cached_brake_level = 0
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=20.0, distance=600.0)

    train.step_tick(0.1)

    assert train.atp_intervened is True
    assert train.applied_traction_level == 0
    assert train.applied_brake_level == 4
    assert train.control_source == "emergency"
    assert train.state.mode == "emergency"


def test_step_tick_passes_acceleration_and_delay_to_ato_controller():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1480.0
    train.state.speed_ms = 10.0
    train.state.acceleration = -1.0
    train.driving_mode = "AM"
    train.next_stop_target_m = 1500.0
    train.ato_control_delay_sec = 0.5
    train.ato_delay_compensation_enabled = True
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=60.0, distance=120.0)

    train.step_tick(0.1)

    assert train.last_ato_output is not None
    assert train.last_ato_output.distance_to_stop_m == pytest.approx(15.125)
    assert train.ato_delay_compensation_enabled is True


def test_step_tick_uses_track_gradient_when_available():
    flat_manager = TrainManager()
    flat_train = flat_manager.get_train("TRAIN-001")
    flat_train.state.position = 600.0
    flat_train.state.speed_ms = 5.0
    flat_train.driving_mode = "AM"
    flat_train.next_stop_target_m = 900.0
    flat_train.ato_gradient_compensation_enabled = False
    _apply_valid_ma(flat_train, ma_limit=1200.0, allowed_speed=120.0, distance=600.0)

    graded_manager = TrainManager()
    graded_train = graded_manager.get_train("TRAIN-001")
    graded_train.state.position = 600.0
    graded_train.state.speed_ms = 5.0
    graded_train.driving_mode = "AM"
    graded_train.next_stop_target_m = 900.0
    graded_train.ato_gradient_compensation_enabled = True
    _apply_valid_ma(graded_train, ma_limit=1200.0, allowed_speed=120.0, distance=600.0)

    flat_train.step_tick(0.1)
    graded_train.step_tick(0.1)

    assert graded_train.last_ato_output is not None
    assert graded_train.ato_gradient_compensation_enabled is True
    assert (
        graded_train.last_ato_output.ato_target_speed_kmh
        >= flat_train.last_ato_output.ato_target_speed_kmh - 0.001
    )


def test_step_tick_passes_previous_commanded_levels_for_jerk_limit():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1488.0
    train.state.speed_ms = 8.0
    train.driving_mode = "AM"
    train.next_stop_target_m = 1500.0
    train.ato_jerk_limit_enabled = True
    train.commanded_traction_level = 0
    train.commanded_brake_level = 0
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=80.0, distance=200.0)

    train.step_tick(0.1)
    first_brake_level = train.commanded_brake_level

    assert train.last_ato_output is not None
    assert train.last_ato_output.ato_brake_level == 4
    assert first_brake_level == 1
    assert train.applied_brake_level == first_brake_level

    train.step_tick(0.1)

    assert train.commanded_brake_level >= first_brake_level
    assert train.commanded_brake_level <= first_brake_level + 1


def test_step_tick_passes_brake_bias_to_train_ato_controller():
    baseline_manager = TrainManager()
    baseline_train = baseline_manager.get_train("TRAIN-001")
    baseline_train.state.position = 1420.0
    baseline_train.state.speed_ms = 5.0
    baseline_train.driving_mode = "AM"
    baseline_train.next_stop_target_m = 1500.0
    baseline_train.ato_gradient_compensation_enabled = False
    baseline_train.ato_brake_bias_enabled = True
    baseline_train.ato_brake_bias = 1.0
    _apply_valid_ma(baseline_train, ma_limit=1600.0, allowed_speed=80.0, distance=180.0)

    biased_manager = TrainManager()
    biased_train = biased_manager.get_train("TRAIN-001")
    biased_train.state.position = 1420.0
    biased_train.state.speed_ms = 5.0
    biased_train.driving_mode = "AM"
    biased_train.next_stop_target_m = 1500.0
    biased_train.ato_gradient_compensation_enabled = False
    biased_train.ato_brake_bias_enabled = True
    biased_train.ato_brake_bias = 1.3
    _apply_valid_ma(biased_train, ma_limit=1600.0, allowed_speed=80.0, distance=180.0)

    baseline_train.step_tick(0.1)
    biased_train.step_tick(0.1)

    assert baseline_train.last_ato_output is not None
    assert biased_train.last_ato_output is not None
    assert (
        biased_train.last_ato_output.ato_target_speed_kmh
        < baseline_train.last_ato_output.ato_target_speed_kmh
    )
    assert biased_train.state.ato_brake_bias == pytest.approx(1.3)
    assert biased_train.state.ato_brake_bias_enabled is True


def test_train_state_protocol_contains_ato_fields():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1000.0
    train.driving_mode = "AM"
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train)

    train.step_tick(0.1)
    state = train.state.to_protocol()

    for field in [
        "driving_mode",
        "ato_state",
        "recommended_speed",
        "ato_target_speed",
        "ato_traction_level",
        "ato_brake_level",
        "commanded_traction_level",
        "commanded_brake_level",
        "applied_traction_level",
        "applied_brake_level",
        "control_source",
        "atp_intervened",
        "stop_target",
        "distance_to_stop",
        "stop_result",
    ]:
        assert field in state

    for old_field in [
        "vehicle_id",
        "position",
        "speed",
        "acceleration",
        "mode",
        "is_running",
        "emergency_brake",
    ]:
        assert old_field in state


def test_train_state_am_fields_match_internal_values():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1000.0
    train.driving_mode = "AM"
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train)

    train.step_tick(0.1)

    assert train.state.driving_mode == "AM"
    assert train.state.ato_state == train.ato_state
    assert train.state.control_source in {"ato", "degraded", "emergency"}
    assert train.state.commanded_traction_level == train.commanded_traction_level
    assert train.state.commanded_brake_level == train.commanded_brake_level
    assert train.state.applied_traction_level == train.applied_traction_level
    assert train.state.applied_brake_level == train.applied_brake_level


def test_train_state_sm_fields_match_cached_driver_command():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1000.0
    train.driving_mode = "SM"
    train.cached_traction_level = 2
    train.cached_brake_level = 0
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train)

    train.step_tick(0.1)

    assert train.state.driving_mode == "SM"
    assert train.state.control_source == "manual"
    assert train.state.recommended_speed >= 0.0
    assert train.state.commanded_traction_level == 2
    assert train.state.commanded_brake_level == 0


def test_train_state_atp_intervention_fields():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.speed_ms = 30.0
    train.driving_mode = "AM"
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=20.0, distance=600.0)

    train.step_tick(0.1)

    assert train.state.mode == "emergency"
    assert train.state.control_source == "emergency"
    assert train.state.atp_intervened is True
    assert train.state.applied_traction_level == 0
    assert train.state.applied_brake_level == 4


def test_stop_result_in_window_in_train_state():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1500.3
    train.state.speed_ms = 0.0
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=20.0, distance=100.0)

    train.step_tick(0.1)

    result = train.state.stop_result
    assert result is not None
    assert result["type"] == "stop_result"
    assert result["qualified"] is True
    assert result["status"] == "in_window"
    assert abs(result["error_cm"] - 30.0) < 1.0


def test_stop_result_is_not_generated_before_stop_window_overshoot():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1501.0
    train.state.speed_ms = 0.0
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=20.0, distance=100.0)

    train.step_tick(0.1)

    assert train.state.stop_result is None
    assert train.stop_result_published_for_target is False


def test_stop_result_is_not_generated_before_stop_window_undershoot():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1499.0
    train.state.speed_ms = 0.0
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=20.0, distance=100.0)

    train.step_tick(0.1)

    assert train.state.stop_result is None
    assert train.stop_result_published_for_target is False


def test_stop_result_is_not_regenerated_for_same_target():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1500.2
    train.state.speed_ms = 0.0
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train, ma_limit=1600.0, allowed_speed=20.0, distance=100.0)

    train.step_tick(0.1)
    first_result = train.last_stop_result
    train.state.position = 1500.4
    train.step_tick(0.1)

    assert train.stop_result_published_for_target is True
    assert train.last_stop_result is first_result


def test_stop_result_resets_when_stop_target_changes():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1500.1
    train.state.speed_ms = 0.0
    train.next_stop_target_m = 1500.0
    _apply_valid_ma(train, ma_limit=2600.0, allowed_speed=20.0, distance=1100.0)

    train.step_tick(0.1)
    first_result = train.last_stop_result
    train.next_stop_target_m = 1502.0
    train.state.position = 1502.1
    train.step_tick(0.1)

    assert first_result is not None
    assert train.last_stop_result_target_m == 1502.0
    assert train.stop_result_published_for_target is True
    assert train.last_stop_result is not first_result
