from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.train_manager import TrainManager


def _manager_and_router(count=3):
    manager = TrainManager(initial_count=count)
    return manager, MessageRouter(manager)


def test_physical_driver_controls_only_explicit_train_one():
    manager, router = _manager_and_router()
    result = router.handle(
        {
            "type": "driver_input",
            "source": "driver_tcp",
            "vehicle_id": "TRAIN-001",
            "traction_percent": 100.0,
            "direction": "forward",
        }
    )

    assert result == {"ok": True, "vehicle_id": "TRAIN-001"}
    assert manager.get_train("TRAIN-001").requested_traction_percent == 100.0
    assert manager.get_train("TRAIN-002").requested_traction_percent == 0.0
    assert manager.get_train("TRAIN-003").requested_traction_percent == 0.0


def test_physical_driver_cannot_target_other_train():
    manager, router = _manager_and_router()
    result = router.handle(
        {
            "type": "driver_input",
            "source": "driver_tcp",
            "vehicle_id": "TRAIN-002",
            "traction_percent": 100.0,
        }
    )

    assert result["ok"] is False
    assert result["reason"] == "physical_driver_vehicle_mismatch"
    assert manager.get_train("TRAIN-002").requested_traction_percent == 0.0


def test_driver_input_rejects_missing_vehicle_id_instead_of_broadcasting():
    manager, router = _manager_and_router()
    result = router.handle(
        {
            "type": "driver_input",
            "source": "driver_tcp",
            "train_index": 1,
            "traction_percent": 100.0,
        }
    )

    assert result == {"ok": False, "reason": "driver_input_requires_vehicle_id"}
    assert all(train.requested_traction_percent == 0.0 for train in manager.trains.values())


def test_virtual_driver_can_control_its_own_non_physical_train():
    manager, router = _manager_and_router()
    result = router.handle(
        {
            "type": "driver_input",
            "source": "virtual_driver",
            "vehicle_id": "TRAIN-002",
            "traction_percent": 50.0,
            "direction": "forward",
        }
    )

    assert result["ok"] is True
    assert manager.get_train("TRAIN-002").requested_traction_percent == 50.0
    assert manager.get_train("TRAIN-001").requested_traction_percent == 0.0


def test_speed_constraint_is_targeted_and_enters_atp_limit():
    manager, router = _manager_and_router(2)
    train_one = manager.get_train("TRAIN-001")
    train_two = manager.get_train("TRAIN-002")
    train_one.state.speed_ms = 20.0 / 3.6

    result = router.handle(
        {
            "type": "speed_constraint",
            "vehicle_id": "TRAIN-001",
            "speed_limit_kmh": 10.0,
            "reason": "temporary_work_zone",
        }
    )
    train_one.step_tick(0.1)

    assert result["ok"] is True
    assert train_one.external_speed_limit_kmh == 10.0
    assert train_two.external_speed_limit_kmh is None
    assert train_one.state.emergency_brake is True
    assert train_one.last_atp_decision.allowed_speed_kmh == 10.0


def test_red_signal_or_denied_interlocking_is_targeted():
    manager, router = _manager_and_router(2)
    train_one = manager.get_train("TRAIN-001")
    train_two = manager.get_train("TRAIN-002")
    train_one.state.speed_ms = 2.0

    router.handle(
        {
            "type": "interlocking_state",
            "vehicle_id": "TRAIN-001",
            "permission": "stop",
            "signal_state": "red",
        }
    )
    train_one.step_tick(0.1)

    assert train_one.permission == "stop"
    assert train_one.state.emergency_brake is True
    assert train_two.permission is None


def test_fault_event_affects_only_target_unless_scope_all_is_explicit():
    manager, router = _manager_and_router(2)
    train_one = manager.get_train("TRAIN-001")
    train_two = manager.get_train("TRAIN-002")

    router.handle(
        {
            "type": "fault_event",
            "vehicle_id": "TRAIN-002",
            "fault_type": "brake_fault",
            "active": True,
            "severity": "critical",
        }
    )
    train_two.step_tick(0.1)

    assert train_one.brake_fault is False
    assert train_two.brake_fault is True
    assert train_two.state.emergency_brake is True

    router.handle(
        {
            "type": "fault_event",
            "scope": "all",
            "fault_type": "power_fault",
            "active": True,
        }
    )
    assert train_one.power_fault is True
    assert train_two.power_fault is True


def test_train_builds_separate_ato_atp_and_door_states():
    manager, _ = _manager_and_router(1)
    train = manager.get_train("TRAIN-001")
    train.step_tick(0.1)

    assert train.build_ato_state()["type"] == "ato_state"
    assert train.build_atp_state()["type"] == "atp_state"
    assert train.build_door_state()["type"] == "door_state"
    assert train.build_atp_state()["vehicle_id"] == "TRAIN-001"
