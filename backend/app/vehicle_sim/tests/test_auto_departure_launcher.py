import time

import pytest

from app.data_flow.ato_guidance import build_ato_precheck
from app.vehicle_sim.models import MaLimit
from app.vehicle_sim.train_manager import TrainManager
from scripts.auto_departure_launcher import (
    MAX_DEMO_TRAINS,
    build_vehicle_command,
    has_cleared_origin,
    monitor_vehicle_for_launch,
    next_launch_index,
    next_launch_index_if_ready,
    planned_vehicle_ids,
    train_position_m,
    validate_launch_range,
    vehicle_id_for,
)


def test_launcher_vehicle_ids_are_zero_padded():
    assert [vehicle_id_for("TRAIN", index) for index in (1, 2, 3)] == [
        "TRAIN-001",
        "TRAIN-002",
        "TRAIN-003",
    ]


def test_launcher_launch_range_plans_only_virtual_trains():
    assert planned_vehicle_ids("TRAIN", 2, 3) == [
        "TRAIN-002",
        "TRAIN-003",
    ]


def test_launcher_does_not_plan_or_start_train001():
    planned = planned_vehicle_ids("TRAIN", 2, 2)

    assert planned == ["TRAIN-002"]
    assert "TRAIN-001" not in planned


def test_anchor_vehicle_defaults_to_train001_for_monitoring():
    assert (
        monitor_vehicle_for_launch(
            anchor_vehicle_id="TRAIN-001",
            vehicle_prefix="TRAIN",
            launch_from_index=2,
            launched_count=0,
        )
        == "TRAIN-001"
    )
    assert (
        monitor_vehicle_for_launch(
            anchor_vehicle_id="TRAIN-001",
            vehicle_prefix="TRAIN",
            launch_from_index=2,
            launched_count=1,
        )
        == "TRAIN-002"
    )


def test_launcher_rejects_launch_from_index_one_or_lower():
    with pytest.raises(ValueError, match="TRAIN-001"):
        validate_launch_range(1, 3)


def test_launcher_rejects_max_index_above_demo_limit():
    assert MAX_DEMO_TRAINS == 5
    with pytest.raises(ValueError, match="<= 5"):
        validate_launch_range(2, 6)


def test_launcher_has_no_next_vehicle_after_all_requested_started():
    assert next_launch_index(0, 2, 3) == 2
    assert next_launch_index(1, 2, 3) == 3
    assert next_launch_index(2, 2, 3) is None
    assert next_launch_index(3, 2, 3) is None


def test_launcher_waits_for_anchor_before_starting_train002():
    waiting_snapshot = {"trains": [{"vehicle_id": "TRAIN-001", "position_m": 199.9}]}
    cleared_snapshot = {"trains": [{"vehicle_id": "TRAIN-001", "position_m": 200.0}]}

    common = {
        "anchor_vehicle_id": "TRAIN-001",
        "vehicle_prefix": "TRAIN",
        "launch_from_index": 2,
        "max_index": 3,
        "launched_count": 0,
        "clear_distance_m": 200.0,
    }
    assert next_launch_index_if_ready(waiting_snapshot, **common) is None
    assert next_launch_index_if_ready(cleared_snapshot, **common) == 2


def test_launcher_waits_for_train002_before_starting_train003():
    waiting_snapshot = {"trains": [{"vehicle_id": "TRAIN-002", "position_m": 199.9}]}
    cleared_snapshot = {"trains": [{"vehicle_id": "TRAIN-002", "position_m": 200.0}]}

    common = {
        "anchor_vehicle_id": "TRAIN-001",
        "vehicle_prefix": "TRAIN",
        "launch_from_index": 2,
        "max_index": 3,
        "launched_count": 1,
        "clear_distance_m": 200.0,
    }
    assert next_launch_index_if_ready(waiting_snapshot, **common) is None
    assert next_launch_index_if_ready(cleared_snapshot, **common) == 3


def test_launcher_vehicle_command_uses_single_train_process_entrypoint():
    command = build_vehicle_command(
        python_executable="python",
        vehicle_id="TRAIN-002",
        train_index=2,
        initial_position=0.0,
        dt=0.1,
    )

    assert command == [
        "python",
        "-m",
        "app.vehicle_sim.main_integrated",
        "--vehicle-id",
        "TRAIN-002",
        "--train-index",
        "2",
        "--initial-position",
        "0.0",
        "--dt",
        "0.1",
        "--virtual-ato",
    ]


def test_launcher_waits_until_previous_train_clears_origin():
    waiting_snapshot = {"trains": [{"vehicle_id": "TRAIN-001", "position_m": 199.9}]}
    cleared_snapshot = {"trains": [{"vehicle_id": "TRAIN-001", "position_m": 200.0}]}

    assert has_cleared_origin(waiting_snapshot, "TRAIN-001", 200.0) is False
    assert has_cleared_origin(cleared_snapshot, "TRAIN-001", 200.0) is True
    assert train_position_m({"trains": []}, "TRAIN-001") is None


def test_train001_remains_hardware_controlled_sm_on_creation():
    manager = TrainManager(initial_count=0)
    manager.add_train(vehicle_id="TRAIN-001", slot=1, position=0.0)
    train = manager.get_train("TRAIN-001")

    assert train.driving_mode == "SM"
    assert train.control_source == "manual"
    assert train.state.mode == "manual"
    assert train.ato_capable is False


def test_virtual_train002_starts_at_origin_with_next_stop_431_and_am_ready():
    manager = TrainManager(initial_count=0)
    manager.add_train(vehicle_id="TRAIN-002", slot=2, position=0.0, virtual_ato=True)
    train = manager.get_train("TRAIN-002")

    assert train.state.position == pytest.approx(0.0)
    assert train.state.line_id == "LINE-1"
    assert train.state.direction_code == 1
    assert train.next_stop_target_m == pytest.approx(431.0)
    assert train._resolve_stop_target_m() == pytest.approx(431.0)
    assert train.driving_mode == "AM"
    assert train.control_source == "ato"
    assert train.state.mode == "ato"
    assert train.ato_capable is True
    assert train.key_switch_active is True
    assert train.parking_brake_applied is False
    assert train.door_state.all_closed is True


def test_virtual_train002_precheck_can_start_with_valid_ma_and_comm():
    manager = TrainManager(initial_count=0)
    manager.add_train(vehicle_id="TRAIN-002", slot=2, position=0.0, virtual_ato=True)
    train = manager.get_train("TRAIN-002")
    train.apply_ma_state(
        MaLimit(
            vehicle_id="TRAIN-002",
            ma_limit=500.0,
            target_speed=45.0,
            reason="test",
            allowed_speed_kmh=45.0,
            eb_trigger_speed_kmh=55.0,
            target_distance_m=500.0,
            permission="allow",
            signal_state="green",
            updated_at=time.time(),
        )
    )

    train_state = train.state.to_protocol()
    ma_state = {
        "ma_limit": 500.0,
        "allowed_speed_kmh": 45.0,
        "permission": "allow",
        "signal_state": "green",
    }
    comm_state = {"driver_console_connected": True, "zmq_connected": True}
    precheck = build_ato_precheck(None, train_state, ma_state, comm_state)

    assert precheck["can_start_ato"] is True


def test_virtual_train002_moves_under_valid_ma():
    manager = TrainManager(initial_count=0)
    manager.add_train(vehicle_id="TRAIN-002", slot=2, position=0.0, virtual_ato=True)
    train = manager.get_train("TRAIN-002")
    train.apply_ma_state(
        MaLimit(
            vehicle_id="TRAIN-002",
            ma_limit=500.0,
            target_speed=45.0,
            reason="test",
            allowed_speed_kmh=45.0,
            eb_trigger_speed_kmh=55.0,
            target_distance_m=500.0,
            permission="allow",
            signal_state="green",
            updated_at=time.time(),
        )
    )

    train.step_tick(0.1)

    assert train.driving_mode == "AM"
    assert train.control_source == "ato"
    assert train.ato_state == "approaching"
    assert train.commanded_traction_level > 0
    assert train.commanded_brake_level == 0
    assert train.stop_target_m == pytest.approx(431.0)


def test_virtual_train_protocol_keeps_visual_edge_range():
    manager = TrainManager(initial_count=0)
    manager.add_train(vehicle_id="TRAIN-002", slot=2, position=2448.61)
    protocol = manager.get_train("TRAIN-002").state.to_protocol()

    assert protocol["edge_id"] is not None
    assert 1 <= protocol["edge_id"] <= 48


def test_manual_add_train002_does_not_auto_enter_ato():
    manager = TrainManager(initial_count=0)
    result = manager.add_train(vehicle_id="TRAIN-002", slot=2, position=0.0)
    train = manager.get_train("TRAIN-002")

    assert result["ok"] is True
    assert result["virtual_ato"] is False
    assert train.driving_mode == "SM"
    assert train.control_source == "manual"
    assert train.state.mode == "manual"
    assert train.ato_capable is False
