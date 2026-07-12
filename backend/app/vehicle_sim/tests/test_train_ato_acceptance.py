from app.vehicle_sim.models import DriverInput, MaLimit
from app.vehicle_sim.train_manager import TrainManager


def _apply_ma(
    train,
    *,
    ma_limit=1600.0,
    allowed_speed=60.0,
    target_distance=200.0,
    permission="allow",
    signal_state="green",
):
    train.apply_ma_state(
        MaLimit(
            vehicle_id=train.state.vehicle_id,
            ma_limit=ma_limit,
            target_speed=allowed_speed,
            reason="acceptance",
            allowed_speed_kmh=allowed_speed,
            eb_trigger_speed_kmh=allowed_speed + 8.0,
            target_distance_m=target_distance,
            permission=permission,
            signal_state=signal_state,
        )
    )


def _assert_levels_are_safe(train):
    for level in [
        train.ato_traction_level,
        train.ato_brake_level,
        train.commanded_traction_level,
        train.commanded_brake_level,
        train.applied_traction_level,
        train.applied_brake_level,
    ]:
        assert 0 <= level <= 4
    assert not (
        train.commanded_traction_level > 0 and train.commanded_brake_level > 0
    )
    assert not (train.applied_traction_level > 0 and train.applied_brake_level > 0)


def test_am_ato_can_generate_stop_result_or_reach_holding_state():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.driving_mode = "AM"
    train.state.position = 1400.0
    train.state.speed_ms = 8.0
    train.next_stop_target_m = 1500.0
    _apply_ma(train)

    accepted = False
    for _ in range(2000):
        train.step_tick(0.1)
        _assert_levels_are_safe(train)
        assert train.state.position <= train.ma_limit
        if (
            train.state.stop_result is not None
            or train.ato_state == "holding"
            or (abs(train.state.position - 1500.0) < 20.0 and train.state.speed_ms < 2.0)
        ):
            accepted = True
            break

    state = train.state.to_protocol()
    assert accepted is True
    assert train.last_ato_output is not None
    assert state["driving_mode"] == "AM"
    assert state["ato_state"] is not None
    assert state["commanded_traction_level"] == train.commanded_traction_level
    assert state["commanded_brake_level"] == train.commanded_brake_level


def test_sm_mode_uses_driver_cached_command_and_outputs_recommendation():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.state.position = 1000.0
    train.next_stop_target_m = 1500.0
    _apply_ma(train, target_distance=600.0)

    train.step_manual(
        DriverInput(
            vehicle_id=train.state.vehicle_id,
            line_id=train.state.line_id,
            source="test",
            control_mode="manual",
            traction_level=2,
            brake_level=0,
            direction="forward",
            emergency_button=False,
        ),
        dt=0.1,
    )
    train.step_tick(0.1)

    assert train.driving_mode == "SM"
    assert train.state.mode in {"manual", "emergency"}
    assert train.commanded_traction_level == 2
    assert train.commanded_brake_level == 0
    assert train.control_source == "manual"
    assert train.last_ato_output is not None
    assert train.recommended_speed >= 0.0


def test_am_degraded_blocks_traction():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.driving_mode = "AM"
    train.cached_traction_level = 3
    train.cached_brake_level = 0

    train.step_tick(0.1)

    assert train.last_ato_output.degraded is True
    assert train.commanded_traction_level == 0
    assert train.commanded_brake_level >= 2
    assert train.control_source in {"degraded", "emergency"}
    assert train.applied_traction_level == 0


def test_atp_intervention_overrides_commanded_levels():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.driving_mode = "AM"
    train.cached_traction_level = 2
    train.cached_brake_level = 0
    train.comm_ok = False
    _apply_ma(train, target_distance=600.0)

    train.step_tick(0.1)

    assert train.state.mode == "emergency"
    assert train.control_source == "emergency"
    assert train.atp_intervened is True
    assert train.applied_traction_level == 0
    assert train.applied_brake_level == 4
    assert train.driving_mode == "AM"


def test_real_driver_brake_level_7_maps_to_vehicle_brake_4_without_emergency():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    initial_position = train.state.position
    initial_speed = train.state.speed_ms

    train.step_manual(
        DriverInput(
            vehicle_id=train.state.vehicle_id,
            line_id=train.state.line_id,
            source="driver_desk",
            control_mode="manual",
            traction_level=4,
            brake_level=7,
            direction="forward",
            emergency_button=False,
            emergency_cmd=False,
            main_handle_raw=4,
            raw_brake_level=7,
        ),
        dt=0.1,
    )

    assert train.cached_traction_level == 0
    assert train.cached_brake_level == 4
    assert train.raw_brake_level == 7
    assert train.fast_brake is True
    assert train.state.emergency_brake is False
    assert train.state.position == initial_position
    assert train.state.speed_ms == initial_speed

    train.step_tick(0.1)

    assert train.applied_brake_level == 4
    assert train.applied_brake_level <= 4


def test_train_state_protocol_contains_minimum_ato_fields():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    train.driving_mode = "AM"
    train.state.position = 1000.0
    train.next_stop_target_m = 1500.0
    _apply_ma(train, target_distance=600.0)

    train.step_tick(0.1)
    state = train.state.to_protocol()

    for field in [
        "vehicle_id",
        "position",
        "speed",
        "acceleration",
        "mode",
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


def test_multi_train_ato_instances_are_isolated():
    manager = TrainManager()
    train_am = manager.get_train("TRAIN-001")
    train_sm = manager.get_train("TRAIN-002")

    train_am.state.position = 1488.0
    train_am.state.speed_ms = 8.0
    train_am.driving_mode = "AM"
    train_am.cached_traction_level = 4
    train_am.cached_brake_level = 0
    train_am.next_stop_target_m = 1500.0
    _apply_ma(
        train_am,
        ma_limit=1600.0,
        allowed_speed=80.0,
        target_distance=200.0,
    )

    train_sm.state.position = 1199.8
    train_sm.state.speed_ms = 0.0
    train_sm.next_stop_target_m = 1200.0
    _apply_ma(
        train_sm,
        ma_limit=1500.0,
        allowed_speed=45.0,
        target_distance=300.0,
    )
    train_sm.step_manual(
        DriverInput(
            vehicle_id=train_sm.state.vehicle_id,
            line_id=train_sm.state.line_id,
            source="test",
            control_mode="manual",
            traction_level=0,
            brake_level=1,
            direction="forward",
            emergency_button=False,
        ),
        dt=0.1,
    )

    states = []
    for _ in range(3):
        states = manager.step_all(0.1)

    state_by_vehicle_id = {state["vehicle_id"]: state for state in states}
    state_am = state_by_vehicle_id["TRAIN-001"]
    state_sm = state_by_vehicle_id["TRAIN-002"]

    assert train_am.last_ato_output is not None
    assert train_sm.last_ato_output is not None
    assert train_am.last_ato_output is not train_sm.last_ato_output

    assert train_am.driving_mode == "AM"
    assert train_am.control_source in {"ato", "degraded", "emergency"}
    assert train_am.commanded_traction_level == train_am.last_ato_output.commanded_traction_level
    assert train_am.commanded_brake_level == train_am.last_ato_output.commanded_brake_level
    assert train_am.commanded_traction_level != train_am.cached_traction_level

    assert train_sm.driving_mode == "SM"
    assert train_sm.control_source == "manual"
    assert train_sm.commanded_traction_level == train_sm.cached_traction_level
    assert train_sm.commanded_brake_level == train_sm.cached_brake_level
    assert train_sm.commanded_brake_level == 1

    assert state_am["vehicle_id"] == "TRAIN-001"
    assert state_sm["vehicle_id"] == "TRAIN-002"
    assert state_am["driving_mode"] == "AM"
    assert state_sm["driving_mode"] == "SM"
    assert state_am["control_source"] == train_am.control_source
    assert state_sm["control_source"] == "manual"
    assert state_am["stop_target"] == 1500.0
    assert state_sm["stop_target"] == 1200.0
    assert state_sm["stop_result"] is not None
    assert state_sm["stop_result"]["vehicle_id"] == "TRAIN-002"
    assert train_am.state.stop_result != train_sm.state.stop_result
