from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.models import DriverInput
from app.vehicle_sim.models import TrackSection
from app.vehicle_sim.track_map import TrackMap
from app.vehicle_sim.train import Train
from app.vehicle_sim.train_manager import TrainManager


def _train_and_router():
    manager = TrainManager(initial_count=1)
    return manager.get_train("TRAIN-001"), MessageRouter(manager)


def _manual(**overrides):
    values = {
        "vehicle_id": "TRAIN-001",
        "line_id": "LINE-1",
        "source": "test",
        "control_mode": "manual",
        "traction_level": 0,
        "brake_level": 0,
        "direction": "forward",
        "emergency_button": False,
    }
    values.update(overrides)
    return DriverInput(**values)


def _two_stop_train():
    track = TrackMap(
        [
            TrackSection("A", 0.0, 150.0, 0.0, 80.0, "S1", 100.0),
            TrackSection("B", 150.0, 250.0, 0.0, 80.0, "S2", 200.0),
        ]
    )
    return Train("TRAIN-001", "LINE-1", track, train_index=1)


def _first_stop_position(train):
    return next(
        section.stop_position
        for section in train.track.sections
        if section.stop_position is not None
    )


def test_train_resolves_next_stop_from_track_before_entering_section():
    train = _two_stop_train()
    train.state.position = 0.0

    assert train._resolve_stop_target_m() == 100.0


def test_station_dwell_completion_advances_to_next_stop_target():
    train = _two_stop_train()
    train.state.position = 100.0
    train.state.speed_ms = 0.0
    train.door_dwell_sec = 0.1

    train.step_tick(0.1)
    assert train.state.door_state == "closed"
    assert train._is_completed_stop_target(100.0) is False

    train.step_tick(0.1)

    assert train.state.door_state == "closed"
    assert train._is_completed_stop_target(100.0) is True
    assert train.stop_target_m != 100.0
    assert train.door_state.last_auto_target_m is None
    assert train.next_stop_target_m == 200.0

    train.set_next_stop_target_m(100.0)
    assert train.next_stop_target_m == 200.0


def test_station_dwell_accepts_small_overshoot_and_advances():
    train = _two_stop_train()
    train.state.position = 101.96
    train.state.speed_ms = 0.0
    train.door_dwell_sec = 0.1
    train.set_next_stop_target_m(100.0)

    train.step_tick(0.1)
    assert train.state.door_state == "closed"

    train.step_tick(0.1)

    assert train.state.door_state == "closed"
    assert train._is_completed_stop_target(100.0) is True
    assert train.stop_target_m != 100.0
    assert train.door_state.last_auto_target_m is None
    assert train.next_stop_target_m == 200.0


def test_station_dwell_does_not_open_for_undershoot_outside_hold_window():
    train = _two_stop_train()
    train.state.position = 99.7
    train.state.speed_ms = 0.0
    train.door_dwell_sec = 0.1
    train.set_next_stop_target_m(100.0)

    train.step_tick(0.1)

    assert train.state.door_state == "closed"
    assert train._is_completed_stop_target(100.0) is False
    assert train.next_stop_target_m == 100.0


def test_station_dwell_does_not_depend_on_automatic_door_opening():
    train, _ = _train_and_router()
    train.state.position = _first_stop_position(train)
    train.state.speed_ms = 0.0
    train.door_dwell_sec = 1.0

    train.step_tick(0.5)
    assert train.state.door_state == "closed"
    assert train.state.left_door_open is False
    assert train.state.right_door_open is False
    assert train.state.doors_all_closed is True
    assert train.state.door_closed_light is True
    assert train.completed_stop_target_keys == set()

    train.step_tick(0.5)
    assert train.state.door_state == "closed"
    assert train.state.doors_all_closed is True
    assert train.state.door_closed_light is True
    assert train.completed_stop_target_keys == set()

    train.step_tick(0.5)
    assert train.state.door_state == "closed"
    assert train.state.doors_all_closed is True
    assert train.state.door_closed_light is True
    assert train.completed_stop_target_keys

    train.step_tick(0.5)
    assert train.state.door_state == "closed"


def test_station_dwell_accepts_overshoot_beyond_door_rearm_distance():
    train = _two_stop_train()
    train.state.position = 102.3
    train.state.speed_ms = 0.0
    train.door_dwell_sec = 0.1
    train.door_rearm_distance_m = 2.0
    train.set_next_stop_target_m(100.0)

    train.step_tick(0.1)
    train.step_tick(0.1)

    assert train.state.door_state == "closed"
    assert train._is_completed_stop_target(100.0) is True
    assert train.next_stop_target_m == 200.0


def test_automatic_door_does_not_open_while_train_is_moving():
    train, _ = _train_and_router()
    train.state.position = _first_stop_position(train)
    train.state.speed_ms = 1.0

    train.step_tick(0.1)

    assert train.state.doors_all_closed is True


def test_door_interlock_blocks_traction():
    train, _ = _train_and_router()
    train.state.position = 100.0
    train.step_manual(_manual(open_left_door=True), 0.1)
    train.step_tick(0.1)
    assert train.state.left_door_open is True

    train.step_manual(
        _manual(traction_level=4, traction_percent=100.0), 0.1
    )
    train.step_tick(0.1)
    assert train.current_traction_level == 0
    assert train.current_traction_percent == 0.0
    assert train.control_source == "door_interlock"


def test_manual_side_requests_and_close_requests_are_consumed():
    train, router = _train_and_router()
    train.state.position = 100.0
    router.handle(
        {
            "type": "driver_input",
            "vehicle_id": "TRAIN-001",
            "open_right_door": True,
            "door_mode": "right",
        }
    )
    train.step_tick(0.1)
    assert train.state.left_door_open is False
    assert train.state.right_door_open is True
    assert train.state.door_mode == "right"

    router.handle(
        {
            "type": "driver_input",
            "vehicle_id": "TRAIN-001",
            "close_right_door": True,
        }
    )
    train.step_tick(0.1)
    assert train.state.doors_all_closed is True
    assert train.close_right_door_requested is False


def test_door_closed_light_input_is_readback_not_physical_state():
    train, _ = _train_and_router()
    train.state.position = 100.0
    train.step_manual(
        _manual(open_left_door=True, door_closed_light=True), 0.1
    )
    train.step_tick(0.1)

    assert train.hardware_door_closed_light is True
    assert train.state.left_door_open is True
    assert train.state.doors_all_closed is False
    assert train.state.door_closed_light is False


def test_auto_door_mode_does_not_auto_open_at_station():
    train, _ = _train_and_router()
    train.state.position = _first_stop_position(train)
    train.step_manual(_manual(door_mode="both"), 0.1)
    train.step_tick(0.1)

    assert train.state.left_door_open is False
    assert train.state.right_door_open is False
    assert train.state.doors_all_closed is True


def test_train_state_protocol_exposes_physical_door_state():
    train, _ = _train_and_router()
    train.state.position = _first_stop_position(train)
    train.step_tick(0.1)

    protocol = train.state.to_protocol()
    assert protocol["door_state"] == "closed"
    assert protocol["left_door_open"] is False
    assert protocol["doors_all_closed"] is True
    assert protocol["door_closed_light"] is True
