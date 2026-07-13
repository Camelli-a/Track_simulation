from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.train_manager import TrainManager


def _single_train_manager(vehicle_id="TRAIN-001", slot=1, position=0.0):
    manager = TrainManager(initial_count=0)
    result = manager.add_train(vehicle_id=vehicle_id, slot=slot, position=position)
    assert result["ok"] is True
    return manager


def test_train_manager_initial_count_zero_can_hold_one_train():
    manager = TrainManager(initial_count=0)

    assert manager.trains == {}

    result = manager.add_train(vehicle_id="TRAIN-001", slot=1, position=0.0)
    states = manager.step_all(0.1)

    assert result["ok"] is True
    assert list(manager.trains) == ["TRAIN-001"]
    assert len(states) == 1
    assert states[0]["vehicle_id"] == "TRAIN-001"


def test_single_train_router_only_handles_owned_driver_input():
    manager = _single_train_manager()
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")
    train = manager.get_train("TRAIN-001")

    router.handle(
        {
            "type": "driver_input",
            "vehicle_id": "TRAIN-002",
            "traction_level": 3,
            "brake_level": 0,
        }
    )

    assert train.cached_traction_level == 0
    assert train.cached_brake_level == 0
    assert manager.get_train("TRAIN-002") is None

    router.handle(
        {
            "type": "driver_input",
            "vehicle_id": "TRAIN-001",
            "traction_level": 2,
            "brake_level": 0,
            "control_mode": "manual",
        }
    )

    assert train.cached_traction_level == 2
    assert train.cached_brake_level == 0


def test_enable_fallback_ato_is_disabled_by_default():
    manager = _single_train_manager(position=1500.0)
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")
    train = manager.get_train("TRAIN-001")

    result = router.handle(
        {
            "type": "enable_fallback_ato",
            "vehicle_id": "TRAIN-001",
            "target_position": 1800.0,
        }
    )

    assert result == {
        "ok": True,
        "ignored": True,
        "reason": "legacy_fallback_ato_disabled",
    }
    assert train.fallback_ato is None
    assert train.next_stop_target_m == 1660.5


def test_enable_fallback_ato_updates_owned_stop_target():
    manager = _single_train_manager(position=1500.0)
    router = MessageRouter(
        manager,
        owned_vehicle_id="TRAIN-001",
        allow_legacy_fallback_ato=True,
    )
    train = manager.get_train("TRAIN-001")
    train.next_stop_target_m = 1000.0
    train.stop_target_m = 1000.0
    train.state.emergency_brake = True

    router.handle(
        {
            "type": "enable_fallback_ato",
            "vehicle_id": "TRAIN-001",
            "target_position": 1800.0,
        }
    )

    assert train.next_stop_target_m == 1800.0
    assert train.stop_target_m == 1800.0
    assert train.state.emergency_brake is False
    assert train.state.mode == "ato"


def test_station_demo_fallback_ignores_non_demo_ma_updates():
    manager = _single_train_manager(position=1500.0)
    router = MessageRouter(
        manager,
        owned_vehicle_id="TRAIN-001",
        allow_legacy_fallback_ato=True,
    )
    train = manager.get_train("TRAIN-001")

    router.handle(
        {
            "type": "enable_fallback_ato",
            "vehicle_id": "TRAIN-001",
            "target_position": 1800.0,
            "reason": "station_demo_approach",
        }
    )
    router.handle(
        {
            "type": "ma_state",
            "vehicle_id": "TRAIN-001",
            "ma_limit": 2500.0,
            "speed_limit": 30.0,
            "reason": "default_signal_control",
        }
    )
    assert train.ma_limit is None

    router.handle(
        {
            "type": "ma_state",
            "vehicle_id": "TRAIN-001",
            "ma_limit": 2200.0,
            "speed_limit": 48.0,
            "reason": "station_demo_approach",
        }
    )
    assert train.ma_limit == 2200.0


def test_single_train_router_only_handles_owned_flat_ma_state():
    manager = _single_train_manager()
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")
    train = manager.get_train("TRAIN-001")

    router.handle(
        {
            "type": "ma_state",
            "vehicle_id": "TRAIN-002",
            "ma_limit": 1800.0,
            "speed_limit": 45.0,
        }
    )

    assert train.ma_limit is None
    assert manager.get_train("TRAIN-002") is None

    router.handle(
        {
            "type": "ma_state",
            "vehicle_id": "TRAIN-001",
            "ma_limit": 1500.0,
            "speed_limit": 40.0,
            "distance_to_ma": 500.0,
            "stop_target_m": 313.0,
        }
    )

    assert train.ma_limit == 1500.0
    assert train.allowed_speed_kmh == 40.0
    assert train.target_distance_m == 500.0
    assert train.next_stop_target_m == 313.0


def test_single_train_router_filters_batch_ma_limits_to_owned_train():
    manager = _single_train_manager()
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")
    train = manager.get_train("TRAIN-001")

    router.handle(
        {
            "type": "ma_state",
            "ma_limits": [
                {
                    "vehicle_id": "TRAIN-002",
                    "ma_limit": 1800.0,
                    "speed_limit": 45.0,
                },
                {
                    "vehicle_id": "TRAIN-001",
                    "ma_limit": 1500.0,
                    "speed_limit": 40.0,
                },
            ],
        }
    )

    assert train.ma_limit == 1500.0
    assert train.allowed_speed_kmh == 40.0
    assert manager.get_train("TRAIN-002") is None


def test_single_train_comm_state_without_vehicle_id_is_broadcast():
    manager = _single_train_manager()
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")
    train = manager.get_train("TRAIN-001")

    router.handle(
        {
            "type": "comm_state",
            "driver_console_connected": False,
            "zmq_connected": True,
            "last_message_at": 100.0,
        }
    )

    assert train.comm_ok is False
    assert train.last_comm_message_at == 100.0


def test_single_train_comm_state_for_other_vehicle_is_ignored():
    manager = _single_train_manager()
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")
    train = manager.get_train("TRAIN-001")

    router.handle(
        {
            "type": "comm_state",
            "driver_console_connected": False,
            "zmq_connected": True,
            "last_message_at": 100.0,
        }
    )
    router.handle(
        {
            "type": "comm_state",
            "vehicle_id": "TRAIN-002",
            "driver_console_connected": True,
            "zmq_connected": True,
            "last_message_at": 200.0,
        }
    )

    assert train.comm_ok is False
    assert train.last_comm_message_at == 100.0
    assert manager.get_train("TRAIN-002") is None


def test_single_train_add_train_cannot_create_other_vehicle():
    manager = _single_train_manager()
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")

    result = router.handle(
        {
            "type": "add_train",
            "vehicle_id": "TRAIN-002",
            "train_index": 2,
            "position": 300.0,
        }
    )

    assert result["ignored"] is True
    assert set(manager.trains) == {"TRAIN-001"}


def test_single_train_reset_trains_does_not_restore_default_ten_trains():
    manager = _single_train_manager(position=123.0)
    router = MessageRouter(manager, owned_vehicle_id="TRAIN-001")

    result = router.handle({"type": "reset_trains", "count": 10})

    assert result["ok"] is True
    assert set(manager.trains) == {"TRAIN-001"}
    assert manager.get_train("TRAIN-002") is None


def test_single_train_step_all_outputs_only_owned_train_state_with_ato_fields():
    manager = _single_train_manager()

    states = manager.step_all(0.1)

    assert len(states) == 1
    assert states[0]["vehicle_id"] == "TRAIN-001"
    for field in [
        "driving_mode",
        "control_source",
        "applied_traction_level",
        "applied_brake_level",
    ]:
        assert field in states[0]
