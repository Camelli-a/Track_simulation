import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_ato_controller import (  # noqa: E402
    AtoController,
    AtoStrategyOptimizer,
    PIDController,
    calculate_stop_curve_speed_limit,
    control_value_to_levels,
    find_next_stop_target,
)
from app.services.signal_gradient import calculate_effective_deceleration  # noqa: E402
from app.services.signal_track_config import STOP_TARGETS as CONFIG_STOP_TARGETS  # noqa: E402


DEMO_STOP_TARGETS = [
    {
        "target_id": "STOP-TEST",
        "station_id": "ST-TEST",
        "station_name": "Test Station",
        "platform_id": "PF-TEST",
        "platform_name": "Test Platform",
        "route_id": "R_MAIN",
        "position": 1200.0,
        "window_before": 0.5,
        "window_after": 0.5,
        "approach_distance": 600.0,
        "source": "test_fixture",
    }
]


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


def _controller_with_demo_stop():
    return AtoController(stop_targets=DEMO_STOP_TARGETS)


def _gradient_profile(gradient):
    return [
        {
            "gradient_id": "GR-TEST",
            "start": 0.0,
            "end": 2000.0,
            "gradient": gradient,
            "gradient_unit": "permille",
            "source": "test_fixture",
        }
    ]


def test_default_controller_uses_config_stop_targets():
    controller = AtoController()

    assert controller.stop_targets is CONFIG_STOP_TARGETS
    assert CONFIG_STOP_TARGETS


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


def test_stop_curve_speed_limit_uses_effective_deceleration():
    flat = calculate_stop_curve_speed_limit(100.0, 0.8)
    downhill = calculate_stop_curve_speed_limit(
        100.0,
        calculate_effective_deceleration(0.8, -20.0),
    )
    uphill = calculate_stop_curve_speed_limit(
        100.0,
        calculate_effective_deceleration(0.8, 20.0),
    )

    assert downhill < flat
    assert uphill > flat


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
    controller = _controller_with_demo_stop()

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=40.0),
    )

    assert command["target_speed"] <= command["safe_speed_limit"]
    assert command["target_speed"] <= command["stop_curve_speed_limit"]
    assert command["ato_state"] in {"approach_station", "braking_to_stop"}


def test_braking_to_stop_when_current_speed_above_curve():
    controller = _controller_with_demo_stop()

    command = controller.build_ato_command_for_train(
        _train_state(position=1190.0, speed=80.0),
        _ma_limit(speed_limit=80.0),
    )

    assert command["ato_state"] == "braking_to_stop"
    assert command["brake_level"] > 0


def test_creep_near_target():
    controller = _controller_with_demo_stop()

    command = controller.build_ato_command_for_train(
        _train_state(position=1197.0, speed=2.0),
        _ma_limit(speed_limit=40.0),
    )

    assert command["ato_state"] == "creep"
    assert command["target_speed"] <= controller.creep_speed_limit


def test_holding_inside_stop_window_low_speed():
    controller = _controller_with_demo_stop()

    command = controller.build_ato_command_for_train(
        _train_state(position=1200.2, speed=0.2),
        _ma_limit(speed_limit=40.0),
    )

    assert command["ato_state"] == "holding"
    assert command["holding_brake"] is True


def test_overshoot_outputs_degraded():
    controller = _controller_with_demo_stop()

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
    controller = _controller_with_demo_stop()

    for position in (100.0, 900.0, 1197.0):
        command = controller.build_ato_command_for_train(
            _train_state(position=position, speed=20.0),
            _ma_limit(speed_limit=30.0),
        )
        assert command["target_speed"] <= command["safe_speed_limit"]


def test_optimizer_generates_four_candidate_strategies():
    optimizer = AtoStrategyOptimizer()

    candidates = optimizer.generate_candidate_strategies(
        safe_speed_limit=60.0,
        stop_curve_speed_limit=50.0,
        current_speed=40.0,
        distance_to_target=200.0,
        approach_distance=600.0,
        ato_state="approach_station",
    )

    assert {item["strategy"] for item in candidates} == {
        "conservative_brake",
        "comfort_brake",
        "energy_saving",
        "precise_stop",
    }


def test_optimizer_candidates_do_not_exceed_safe_speed_limit():
    optimizer = AtoStrategyOptimizer()

    candidates = optimizer.generate_candidate_strategies(
        safe_speed_limit=30.0,
        stop_curve_speed_limit=50.0,
        current_speed=40.0,
        distance_to_target=200.0,
        approach_distance=600.0,
        ato_state="approach_station",
    )

    assert all(item["target_speed"] <= 30.0 for item in candidates)


def test_optimizer_selects_highest_score():
    optimizer = AtoStrategyOptimizer()
    context = {
        "safe_speed_limit": 60.0,
        "stop_curve_speed_limit": 50.0,
        "current_speed": 40.0,
        "distance_to_target": 200.0,
        "approach_distance": 600.0,
        "ato_state": "approach_station",
    }

    result = optimizer.optimize(**context)

    assert result["score"] == max(item["score"] for item in result["strategy_scores"])


def test_precise_stop_preferred_near_target():
    optimizer = AtoStrategyOptimizer()

    result = optimizer.optimize(
        safe_speed_limit=30.0,
        stop_curve_speed_limit=5.0,
        current_speed=4.0,
        distance_to_target=3.0,
        approach_distance=600.0,
        ato_state="creep",
    )

    assert result["selected_strategy"] == "precise_stop"


def test_energy_saving_preferred_far_from_target_or_cruise():
    optimizer = AtoStrategyOptimizer()

    result = optimizer.optimize(
        safe_speed_limit=60.0,
        stop_curve_speed_limit=60.0,
        current_speed=40.0,
        distance_to_target=500.0,
        approach_distance=600.0,
        ato_state="cruise",
    )

    assert result["selected_strategy"] == "energy_saving"


def test_comfort_brake_preferred_in_normal_approach():
    optimizer = AtoStrategyOptimizer()

    result = optimizer.optimize(
        safe_speed_limit=60.0,
        stop_curve_speed_limit=60.0,
        current_speed=40.0,
        distance_to_target=200.0,
        approach_distance=600.0,
        ato_state="approach_station",
    )

    assert result["selected_strategy"] == "comfort_brake"


def test_degraded_bypasses_optimizer():
    controller = _controller_with_demo_stop()

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=0.0, permission="stop", reason="signal_stop"),
    )

    assert command["selected_strategy"] == "safety_stop"
    assert command["strategy_scores"] == []


def test_holding_bypasses_optimizer():
    controller = _controller_with_demo_stop()

    command = controller.build_ato_command_for_train(
        _train_state(position=1200.2, speed=0.2),
        _ma_limit(speed_limit=40.0),
    )

    assert command["selected_strategy"] == "holding"
    assert command["strategy_scores"] == []


def test_optimized_target_speed_never_exceeds_safe_speed_limit():
    controller = _controller_with_demo_stop()

    for position in (900.0, 1190.0, 1197.0):
        command = controller.build_ato_command_for_train(
            _train_state(position=position, speed=20.0),
            _ma_limit(speed_limit=30.0),
        )
        assert command["target_speed"] <= command["safe_speed_limit"]
        assert command["target_speed"] <= command["stop_curve_speed_limit"]


def test_downhill_gradient_lowers_ato_stop_curve_limit():
    flat_controller = AtoController(stop_targets=DEMO_STOP_TARGETS, gradient_profile=[])
    downhill_controller = AtoController(
        stop_targets=DEMO_STOP_TARGETS,
        gradient_profile=_gradient_profile(-30.0),
    )

    flat_command = flat_controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=80.0),
    )
    downhill_command = downhill_controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=80.0),
    )

    assert downhill_command["effective_deceleration"] < flat_command["effective_deceleration"]
    assert downhill_command["stop_curve_speed_limit"] < flat_command["stop_curve_speed_limit"]


def test_uphill_gradient_raises_stop_curve_but_target_respects_safe_limit():
    controller = AtoController(
        stop_targets=DEMO_STOP_TARGETS,
        gradient_profile=_gradient_profile(30.0),
    )

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=30.0),
    )

    assert command["effective_deceleration"] > 0.8
    assert command["target_speed"] <= command["safe_speed_limit"]
    assert command["target_speed"] <= command["stop_curve_speed_limit"]


def test_ato_command_includes_gradient_fields():
    controller = AtoController(
        stop_targets=DEMO_STOP_TARGETS,
        gradient_profile=_gradient_profile(-12.0),
    )

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=40.0),
    )

    assert command["gradient"] == -12.0
    assert command["gradient_id"] == "GR-TEST"
    assert command["gradient_unit"] == "permille"
    assert command["effective_deceleration"] < 0.8


def test_ato_uses_base_deceleration_without_gradient_data():
    controller = AtoController(stop_targets=DEMO_STOP_TARGETS, gradient_profile=[])

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=40.0),
    )

    assert command["gradient"] is None
    assert command["gradient_id"] is None
    assert command["effective_deceleration"] == 0.8


def test_ato_command_includes_strategy_score_fields():
    controller = _controller_with_demo_stop()

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=40.0),
    )

    assert command["selected_strategy"] != "pid_basic"
    assert isinstance(command["score"], float)
    assert len(command["strategy_scores"]) == 4


def test_strategy_scores_has_no_type_or_timestamp():
    controller = _controller_with_demo_stop()

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=40.0),
    )

    for strategy_score in command["strategy_scores"]:
        assert "type" not in strategy_score
        assert "timestamp" not in strategy_score


def test_ato_command_includes_stop_target_metadata():
    controller = _controller_with_demo_stop()

    command = controller.build_ato_command_for_train(
        _train_state(position=900.0, speed=20.0),
        _ma_limit(speed_limit=40.0),
    )

    assert command["target_id"] == "STOP-TEST"
    assert command["station_name"] == "Test Station"
    assert command["platform_id"] == "PF-TEST"
    assert command["platform_name"] == "Test Platform"
    assert command["stop_target_source"] == "test_fixture"
