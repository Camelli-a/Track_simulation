"""Runnable control-chain scenarios prepared for the onboard ATO MVP."""

from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.models import AtoCommand, CommState, DriverInput
from app.vehicle_sim.testing.fake_ato import FakeAtoController, FakeAtoDecision
from app.vehicle_sim.train_manager import TrainManager


def _manager_and_train():
    manager = TrainManager(initial_count=1)
    return manager, manager.get_train("TRAIN-001")


def _compute(controller, train, driving_mode="AM", stop_target_m=1500.0):
    return controller.compute(
        dt=0.1,
        speed_ms=train.state.speed_ms,
        position_m=train.state.position,
        gradient_permille=train.track.get_gradient(train.state.position),
        driving_mode=driving_mode,
        ma_state={
            "ma_limit_m": train.ma_limit,
            "allowed_speed_kmh": train.allowed_speed_kmh,
            "target_distance_m": train.target_distance_m,
            "permission": train.permission,
            "signal_state": train.signal_state,
        },
        stop_target_m=stop_target_m,
    )


def _apply_fake_ato_decision(train, decision):
    train.step_ato(
        AtoCommand(
            vehicle_id=train.state.vehicle_id,
            line_id=train.state.line_id,
            control_mode="ato",
            target_speed=decision.ato_target_speed_kmh,
            target_position=1500.0,
            traction_level=decision.traction_level,
            brake_level=decision.brake_level,
            reason=decision.ato_state,
        ),
        dt=0.1,
    )
    train.step_tick(0.1)


def test_am_fake_ato_command_flows_through_atp_and_new_dynamics():
    manager, train = _manager_and_train()
    MessageRouter(manager).handle(
        {
            "type": "ma_state",
            "vehicle_id": "TRAIN-001",
            "ma_limit": 1000.0,
            "distance_to_ma": 1000.0,
            "speed_limit": 80.0,
            "permission": "allow",
            "signal_state": "green",
        }
    )
    controller = FakeAtoController(
        default=FakeAtoDecision(
            ato_target_speed_kmh=40.0,
            recommended_speed_kmh=40.0,
            traction_level=4,
        )
    )

    decision = _compute(controller, train)
    _apply_fake_ato_decision(train, decision)

    assert train.state.mode == "ato"
    assert train.state.speed_ms > 0.0
    assert train.current_traction_level == 4
    assert train.current_brake_level == 0
    assert train.state.emergency_brake is False


def test_atp_overrides_unsafe_fake_ato_traction_after_ma_shrink():
    manager, train = _manager_and_train()
    train.state.position = 100.0
    train.state.speed_ms = 12.0
    MessageRouter(manager).handle(
        {
            "type": "ma_state",
            "vehicle_id": "TRAIN-001",
            "ma_limit": 120.0,
            "distance_to_ma": 20.0,
            "speed_limit": 80.0,
            "permission": "restricted",
            "signal_state": "yellow",
        }
    )
    controller = FakeAtoController(
        default=FakeAtoDecision(ato_target_speed_kmh=80.0, traction_level=4)
    )

    _apply_fake_ato_decision(train, _compute(controller, train))

    assert train.state.mode == "emergency"
    assert train.state.emergency_brake is True
    assert train.current_traction_level == 0
    assert train.current_brake_level == 4
    assert train.last_atp_decision.reason == "emergency_braking_curve_exceeded"


def test_sm_computes_recommendation_without_overriding_driver_brake():
    _, train = _manager_and_train()
    train.state.speed_ms = 5.0
    controller = FakeAtoController(
        default=FakeAtoDecision(
            ato_target_speed_kmh=30.0,
            recommended_speed_kmh=30.0,
            traction_level=4,
        )
    )
    recommendation = _compute(controller, train, driving_mode="SM")

    train.step_manual(
        DriverInput(
            vehicle_id="TRAIN-001",
            line_id="LINE-1",
            source="scenario",
            control_mode="manual",
            traction_level=0,
            brake_level=2,
            direction="forward",
            emergency_button=False,
        ),
        dt=0.1,
    )
    train.step_tick(0.1)

    assert recommendation.recommended_speed_kmh == 30.0
    assert recommendation.traction_level == 4
    assert train.state.mode == "manual"
    assert train.current_traction_level == 0
    assert train.current_brake_level == 2
    assert train.state.speed_ms < 5.0


def test_communication_loss_overrides_fake_ato_with_emergency_brake():
    _, train = _manager_and_train()
    train.state.speed_ms = 8.0
    train.apply_comm_state(
        CommState(
            source="scenario",
            driver_console_connected=False,
            zmq_connected=False,
            last_message_at=0.0,
        )
    )
    controller = FakeAtoController(
        default=FakeAtoDecision(ato_target_speed_kmh=40.0, traction_level=4)
    )

    _apply_fake_ato_decision(train, _compute(controller, train))

    assert train.state.emergency_brake is True
    assert train.current_traction_level == 0
    assert train.current_brake_level == 4
    assert train.last_atp_decision.reason == "communication_lost"


def test_fake_ato_instances_keep_independent_script_state():
    _, train = _manager_and_train()
    first = FakeAtoController(decisions=[FakeAtoDecision(traction_level=1)])
    second = FakeAtoController(decisions=[FakeAtoDecision(brake_level=2)])

    first_decision = _compute(first, train)
    second_decision = _compute(second, train)

    assert first_decision.traction_level == 1
    assert second_decision.brake_level == 2
    assert len(first.calls) == 1
    assert len(second.calls) == 1


def test_fake_ato_enforces_brake_priority_and_level_limits():
    _, train = _manager_and_train()
    controller = FakeAtoController(
        default=FakeAtoDecision(traction_level=9, brake_level=7)
    )

    decision = _compute(controller, train)

    assert decision.traction_level == 0
    assert decision.brake_level == 4
