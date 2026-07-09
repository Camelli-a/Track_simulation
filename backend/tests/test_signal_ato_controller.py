import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_ato_controller import (  # noqa: E402
    AtoController,
    PIDController,
    calculate_stop_curve_speed_limit,
    control_value_to_levels,
    find_next_stop_target,
)


def _train_state(position=300.0, speed=40.0, route_id="R_MAIN"):
    return {
        "vehicle_id": "TRAIN-001",
        "position": position,
        "speed": speed,
        "route_id": route_id,
    }


def _ma_limit(speed_limit=60.0, permission="allow", reason="route_end"):
    return {
        "vehicle_id": "TRAIN-001",
        "speed_limit": speed_limit,
        "permission": permission,
        "signal_state": "green" if permission == "allow" else "red",
        "reason": reason,
        "speed_limit_reason": "static_limit",
    }


def test_find_next_stop_target_returns_nearest_forward_target():
    target = find_next_stop_target(
        _train_state(position=100.0),
        stop_targets=[
            {"target_id": "A", "route_id": "R_MAIN", "position": 500.0},
            {"target_id": "B", "route_id": "R_MAIN", "position": 300.0},
            {"target_id": "C", "route_id": "R_BRANCH", "position": 200.0},
        ],
    )

    assert target["target_id"] == "B"


def test_find_next_stop_target_returns_none_without_forward_target():
    assert (
        find_next_stop_target(
            _train_state(position=700.0),
            stop_targets=[
                {"target_id": "A", "route_id": "R_MAIN", "position": 500.0}
            ],
        )
        is None
    )


def test_stop_curve_speed_limit_decreases_as_distance_decreases():
    assert calculate_stop_curve_speed_limit(400.0) > calculate_stop_curve_speed_limit(100.0)


def test_no_stop_target_outputs_cruise():
    controller = AtoController(stop_targets=[])

    command = controller.build_ato_command_for_train(_train_state(), _ma_limit())

    assert command["ato_state"] == "cruise"
    assert command["target_speed"] == command["safe_speed_limit"]
    assert command["reason"] == "no_stop_target"


def test_far_from_stop_target_cruise():
    controller = AtoController(
        stop_targets=[
            {
                "target_id": "STOP",
                "station_id": "ST",
                "route_id": "R_MAIN",
                "position": 1200.0,
                "window_before": 0.5,
                "window_after": 0.5,
                "approach_distance": 600.0,
            }
        ]
    )

    command = controller.build_ato_command_for_train(
        _train_state(position=100.0),
        _ma_limit(speed_limit=60.0),
    )

    assert command["ato_state"] == "cruise"
    assert command["target_speed"] == 60.0
    assert command["reason"] == "far_from_stop_target"


def test_approaching_station_target_speed_not_exceed_safe_limit():
    controller = AtoController()

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=40.0),
    )

    assert command["target_speed"] <= command["safe_speed_limit"]
    assert command["ato_state"] in {"approach_station", "braking_to_stop"}


def test_braking_to_stop_when_current_speed_above_curve():
    controller = AtoController()

    command = controller.build_ato_command_for_train(
        _train_state(position=1190.0, speed=80.0),
        _ma_limit(speed_limit=80.0),
    )

    assert command["ato_state"] == "braking_to_stop"
    assert command["brake_level"] > 0


def test_creep_near_target():
    controller = AtoController()

    command = controller.build_ato_command_for_train(
        _train_state(position=1197.0, speed=2.0),
        _ma_limit(speed_limit=40.0),
    )

    assert command["ato_state"] == "creep"
    assert command["target_speed"] <= controller.creep_speed_limit


def test_holding_inside_stop_window_low_speed():
    controller = AtoController()

    command = controller.build_ato_command_for_train(
        _train_state(position=1200.2, speed=0.2),
        _ma_limit(speed_limit=40.0),
    )

    assert command["ato_state"] == "holding"
    assert command["holding_brake"] is True


def test_overshoot_outputs_degraded():
    controller = AtoController()

    command = controller.build_ato_command_for_train(
        _train_state(position=1201.0, speed=5.0),
        _ma_limit(speed_limit=40.0),
    )

    assert command["ato_state"] == "degraded"
    assert command["reason"] == "overshoot"
    assert command["brake_level"] == 5


def test_signal_stop_outputs_degraded():
    controller = AtoController()

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=0.0, permission="stop", reason="signal_stop"),
    )

    assert command["ato_state"] == "degraded"
    assert command["target_speed"] == 0.0
    assert command["brake_level"] == 5


def test_pid_positive_error_outputs_traction():
    pid = PIDController()

    control_value = pid.update(target_speed=50.0, current_speed=40.0)
    traction_level, brake_level = control_value_to_levels(control_value)

    assert traction_level > 0
    assert brake_level == 0


def test_pid_negative_error_outputs_brake():
    pid = PIDController()

    control_value = pid.update(target_speed=30.0, current_speed=40.0)
    traction_level, brake_level = control_value_to_levels(control_value)

    assert traction_level == 0
    assert brake_level > 0


def test_pid_output_limited():
    pid = PIDController()

    assert pid.update(target_speed=1000.0, current_speed=0.0) <= 100.0
    assert pid.update(target_speed=0.0, current_speed=1000.0) >= -100.0


def test_target_speed_never_exceeds_safe_speed_limit():
    controller = AtoController()

    for position in (100.0, 900.0, 1197.0):
        command = controller.build_ato_command_for_train(
            _train_state(position=position, speed=20.0),
            _ma_limit(speed_limit=30.0),
        )
        assert command["target_speed"] <= command["safe_speed_limit"]
