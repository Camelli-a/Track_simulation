import pytest

from app.vehicle_sim.controllers.train_ato_controller import AtoControlInput
from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.models import DriverInput, MaLimit, CommState
from app.vehicle_sim.train_manager import TrainManager


def _single_train(vehicle_id="TRAIN-001", slot=1, position=100.0):
    manager = TrainManager(initial_count=0)
    result = manager.add_train(vehicle_id=vehicle_id, slot=slot, position=position)
    assert result["ok"] is True
    return manager, manager.get_train(vehicle_id)


def _apply_ma(
    train,
    *,
    ma_limit=500.0,
    allowed_speed=80.0,
    target_distance=None,
    permission="allow",
    signal_state="green",
    eb_trigger_speed=None,
):
    train.apply_ma_state(
        MaLimit(
            vehicle_id=train.state.vehicle_id,
            ma_limit=ma_limit,
            target_speed=allowed_speed,
            reason="test",
            allowed_speed_kmh=allowed_speed,
            eb_trigger_speed_kmh=(
                allowed_speed + 8.0 if eb_trigger_speed is None else eb_trigger_speed
            ),
            target_distance_m=target_distance,
            permission=permission,
            signal_state=signal_state,
        )
    )


def _driver_input(train, **overrides):
    data = {
        "vehicle_id": train.state.vehicle_id,
        "line_id": train.state.line_id,
        "source": "test",
        "control_mode": "manual",
        "traction_level": 0,
        "brake_level": 0,
        "direction": "forward",
        "emergency_button": False,
    }
    data.update(overrides)
    return DriverInput(**data)


def test_ma_shorten_makes_am_control_more_conservative_or_atp_intervenes():
    _, train = _single_train(position=100.0)
    train.driving_mode = "AM"
    train.state.speed_ms = 15.0
    train.next_stop_target_m = 450.0
    _apply_ma(train, ma_limit=500.0, allowed_speed=80.0, target_distance=400.0)

    train.step_tick(0.1)
    normal_distance_to_ma = train.last_curve_point["distance_to_ma_m"]

    _apply_ma(train, ma_limit=130.0, allowed_speed=20.0, target_distance=30.0)
    train.step_tick(0.1)

    assert train.last_curve_point["distance_to_ma_m"] < normal_distance_to_ma
    assert train.commanded_traction_level == 0 or train.applied_traction_level == 0
    assert train.commanded_brake_level > 0 or train.applied_brake_level > 0
    if train.atp_intervened:
        assert train.applied_brake_level == 4


def test_red_signal_degrades_ato_and_blocks_traction():
    _, train = _single_train(position=100.0)
    train.driving_mode = "AM"
    train.state.speed_ms = 8.0
    train.ato_brake_bias = 1.0
    _apply_ma(train, ma_limit=200.0, allowed_speed=60.0, signal_state="red")

    train.step_tick(0.1)

    assert train.last_ato_output is not None
    assert train.last_ato_output.degraded is True
    assert train.ato_state == "degraded"
    assert train.commanded_traction_level == 0
    assert train.commanded_brake_level >= 2
    assert train.applied_traction_level == 0
    assert train.last_brake_bias_adjustment is None


def test_comm_loss_triggers_atp_or_emergency_without_changing_driving_mode():
    _, train = _single_train(position=100.0)
    train.driving_mode = "AM"
    train.state.speed_ms = 10.0
    train.apply_comm_state(
        CommState(
            source="test",
            driver_console_connected=False,
            zmq_connected=False,
            last_message_at=0.0,
        )
    )

    train.step_tick(0.1)

    assert train.driving_mode == "AM"
    assert train.atp_intervened is True or train.state.emergency_brake is True
    assert train.state.atp_intervened is True
    assert train.applied_traction_level == 0
    assert train.applied_brake_level == 4
    assert train.last_curve_point["atp_intervened"] is True


def test_driver_overspeed_in_sm_is_overridden_by_atp():
    _, train = _single_train(position=100.0)
    train.driving_mode = "SM"
    train.state.speed_ms = 15.0
    _apply_ma(
        train,
        ma_limit=1000.0,
        allowed_speed=40.0,
        target_distance=900.0,
        eb_trigger_speed=45.0,
    )
    train.step_manual(
        _driver_input(train, traction_level=4, brake_level=0, control_mode="manual"),
        0.1,
    )

    train.step_tick(0.1)

    assert train.driving_mode == "SM"
    assert train.commanded_traction_level == 4
    assert train.applied_traction_level == 0
    assert train.applied_brake_level == 4
    assert train.atp_intervened is True
    assert train.control_source == "emergency"


def test_driver_emergency_clears_traction_and_applies_full_brake():
    _, train = _single_train(position=100.0)
    train.step_manual(
        _driver_input(
            train,
            traction_level=4,
            brake_level=0,
            emergency_button=True,
        ),
        0.1,
    )

    train.step_tick(0.1)

    assert train.state.emergency_brake is True
    assert train.applied_traction_level == 0
    assert train.applied_brake_level == 4
    assert train.last_curve_point["emergency_brake"] is True


def test_ato_past_stop_target_does_not_command_traction():
    _, train = _single_train(position=1001.0)
    train.driving_mode = "AM"
    train.state.speed_ms = 1.0
    train.next_stop_target_m = 1000.0
    train.ato_brake_bias = 0.7
    train.ato_jerk_limit_enabled = True
    _apply_ma(train, ma_limit=1200.0, allowed_speed=60.0, target_distance=199.0)

    train.step_tick(0.1)

    assert train.commanded_traction_level == 0
    assert train.commanded_brake_level > 0
    assert train.ato_state in {"braking_to_stop", "holding", "degraded"}
    assert train.last_curve_point["distance_to_stop_m"] < 0


def test_single_train_process_ignores_other_vehicle_dangerous_ma_state():
    manager, train = _single_train(position=100.0)
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")

    router.handle(
        {
            "type": "ma_state",
            "vehicle_id": "TRAIN-002",
            "ma_limit": 50.0,
            "allowed_speed_kmh": 0.0,
            "target_distance_m": -50.0,
            "signal_state": "red",
        }
    )
    states = manager.step_all(0.1)

    assert train.ma_limit is None
    assert manager.get_train("TRAIN-002") is None
    assert train.state.emergency_brake is False
    assert states[0]["vehicle_id"] == "TRAIN-001"


def test_single_train_process_ignores_other_vehicle_driver_emergency():
    manager, train = _single_train(position=100.0)
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")

    router.handle(
        {
            "type": "driver_input",
            "vehicle_id": "TRAIN-002",
            "traction_level": 4,
            "brake_level": 0,
            "emergency_button": True,
        }
    )
    manager.step_all(0.1)

    assert train.state.emergency_brake is False
    assert train.cached_traction_level == 0
    assert manager.get_train("TRAIN-002") is None


@pytest.mark.parametrize(
    "setup",
    [
        "atp",
        "degraded",
        "emergency",
        "sm",
    ],
)
def test_safety_scenarios_do_not_trigger_brake_bias_adaptation(setup):
    _, train = _single_train(position=900.0)
    train.driving_mode = "AM"
    train.ato_brake_bias = 1.0
    train.last_ato_output = train.train_ato_controller.compute_am_command(
        AtoControlInput(
            vehicle_id=train.state.vehicle_id,
            position_m=900.0,
            speed_ms=5.0,
            ma_limit_m=1200.0,
            allowed_speed_kmh=60.0,
            stop_target_m=1000.0,
            driving_mode="AM",
        )
    )
    train.last_stop_result = train.train_ato_controller.evaluate_stop_result(
        vehicle_id=train.state.vehicle_id,
        target_position_m=1000.0,
        actual_position_m=1001.0,
        speed_ms=0.0,
    )

    if setup == "atp":
        train.atp_intervened = True
    elif setup == "degraded":
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
    elif setup == "emergency":
        train.state.emergency_brake = True
    elif setup == "sm":
        train.driving_mode = "SM"

    train._maybe_adapt_brake_bias_from_stop_result()

    assert train.ato_brake_bias == pytest.approx(1.0)
    assert train.last_brake_bias_adjustment is None
