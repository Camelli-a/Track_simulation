from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.mock_driver_console import (
    MockDriverConsoleConfig,
    build_comm_state_message,
    build_cycle_messages,
    build_demo_ma_message,
    build_driver_input_message,
)
from app.vehicle_sim.train_manager import TrainManager


def test_mock_driver_console_builds_required_contract_messages():
    config = MockDriverConsoleConfig()

    assert build_driver_input_message(config) == {
        "type": "driver_input",
        "source": "mock_driver_console",
        "vehicle_id": "TRAIN-001",
        "control_mode": "ato",
        "direction": "forward",
        "key_switch": True,
        "door_closed_light": True,
        "ato_start_btn": True,
        "ato_capable": True,
        "ato_active": True,
        "emergency_button": False,
        "emergency_cmd": False,
        "parking_apply": False,
        "parking_release": True,
        "main_handle_raw": 0,
        "traction_level": 0,
        "brake_level": 0,
    }
    assert build_comm_state_message(config) == {
        "type": "comm_state",
        "source": "mock_driver_console",
        "driver_console_connected": True,
        "zmq_connected": True,
    }
    assert build_demo_ma_message(config) == {
        "type": "ma_state",
        "vehicle_id": "TRAIN-001",
        "permission": "allow",
        "signal_state": "green",
        "speed_limit": 40.0,
        "target_speed": 40.0,
        "ma_limit": 500.0,
        "distance_to_ma": 500.0,
        "source": "single_vehicle_demo_ma",
    }


def test_mock_driver_console_messages_make_ato_train_start_moving():
    manager = TrainManager(initial_count=0)
    result = manager.add_train(vehicle_id="TRAIN-001", slot=1, position=0.0)
    assert result["ok"] is True

    router = MessageRouter(manager, default_dt=0.1, owned_vehicle_id="TRAIN-001")
    train = manager.get_train("TRAIN-001")

    config = MockDriverConsoleConfig()
    for message in build_cycle_messages(config):
        router.handle(message)

    assert train.driving_mode == "AM"
    assert train.comm_ok is True
    assert train.permission == "allow"
    assert train.signal_state == "green"
    assert train.ma_limit == 500.0
    assert train.allowed_speed_kmh == 40.0
    assert train.target_distance_m == 500.0

    for _ in range(10):
        for message in build_cycle_messages(config):
            router.handle(message)
        train.step_tick(0.1)

    assert train.last_ato_output is not None
    assert train.last_ato_output.degraded is False
    assert train.last_ato_output.control_source == "ato"
    assert train.last_ato_output.commanded_traction_level > 0
    assert train.state.speed_ms > 0.0


def test_mock_driver_console_can_skip_demo_ma():
    config = MockDriverConsoleConfig(include_demo_ma=False)

    messages = build_cycle_messages(config)

    assert [message["type"] for message in messages] == [
        "driver_input",
        "comm_state",
    ]
