import pytest

from app.vehicle_sim.adapters.command_mapping import (
    command_percent_to_levels,
    normalize_driver_brake_level,
)
from app.vehicle_sim.adapters.id_mapping import index_to_vehicle_id, vehicle_id_to_index
from app.vehicle_sim.adapters.units import m_to_cm, m_to_mm, ms_to_cms, ms_to_mms
from app.vehicle_sim.adapters.vehicle_api_codec import (
    API_VALUE_COUNT,
    api_input_path,
    build_api_input_parameters,
    build_api_output_values,
    parse_api_output_values,
)
from app.vehicle_sim.adapters.vehicle_udp_codec import (
    API_CYCLE_SECONDS,
    INPUT_PACKET_SIZE,
    MODEL_IP,
    MODEL_PORT,
    OUTPUT_PACKET_SIZE,
    PLATFORM_IP,
    PLATFORM_PORT,
    UDP_CYCLE_SECONDS,
    pack_vehicle_input,
    pack_vehicle_output,
    pack_protocol_train_states,
    unpack_vehicle_input,
    unpack_vehicle_output,
    vehicle_input_to_driver_messages,
)
from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.models import AtoCommand, DriverInput
from app.vehicle_sim.train_manager import TrainManager


def test_id_and_unit_mapping():
    assert vehicle_id_to_index("TRAIN-001") == 1
    assert index_to_vehicle_id(2) == "TRAIN-002"
    assert vehicle_id_to_index("TRAIN-021") == 21
    assert index_to_vehicle_id(25) == "TRAIN-025"
    assert ms_to_cms(12.345) == 1234
    assert ms_to_mms(12.345) == 12345
    assert m_to_cm(123.456) == 12346
    assert m_to_mm(123.456) == 123456


def test_vehicle_udp_codec_fixed_length_and_mapping():
    output = pack_vehicle_output(
        {1: {"acceleration": 0.3, "speed": 12.5, "mileage": 123.4}}
    )
    assert len(output) == OUTPUT_PACKET_SIZE
    unpacked_output = unpack_vehicle_output(output)
    assert unpacked_output[1]["speed"] == 12.5
    assert unpacked_output[20]["mileage"] == 0.0

    packet = pack_vehicle_input(
        {
            1: {"command": 1, "percent": 50.0},
            2: {"command": 2, "percent": 75.0},
        }
    )
    assert len(packet) == INPUT_PACKET_SIZE
    commands = unpack_vehicle_input(packet)
    assert commands[1]["traction_level"] == 2
    assert commands[1]["brake_level"] == 0
    assert commands[2]["traction_level"] == 0
    assert commands[2]["brake_level"] == 3


def test_vehicle_udp_interface_constants_match_protocol():
    assert MODEL_IP == "192.168.200.110"
    assert MODEL_PORT == 23001
    assert PLATFORM_IP == "192.168.200.102"
    assert PLATFORM_PORT == 23002
    assert UDP_CYCLE_SECONDS == 0.02
    assert API_CYCLE_SECONDS == 0.5
    assert OUTPUT_PACKET_SIZE == 480
    assert INPUT_PACKET_SIZE == 320


def test_pack_protocol_train_states_uses_position_as_mileage():
    packet = pack_protocol_train_states(
        [
            {
                "vehicle_id": "TRAIN-001",
                "train_index": 1,
                "acceleration": 0.2,
                "speed": 36.0,
                "position": 88.5,
            }
        ]
    )

    output = unpack_vehicle_output(packet)
    assert output[1] == {"acceleration": 0.2, "speed": 36.0, "mileage": 88.5}


def test_udp_codec_ignores_internal_trains_beyond_protocol_slots():
    manager = TrainManager()
    manager.reset_trains(25)

    packet = pack_vehicle_output(manager)
    output = unpack_vehicle_output(packet)

    assert len(manager.trains) == 25
    assert len(packet) == OUTPUT_PACKET_SIZE
    assert set(output) == set(range(1, 21))
    assert manager.get_train_by_slot(21) is not None


def test_vehicle_input_clamps_percent_and_builds_driver_messages():
    packet = pack_vehicle_input({1: {"command": 1, "percent": 150.0}})
    commands = unpack_vehicle_input(packet)

    assert commands[1]["percent"] == 100.0
    messages = vehicle_input_to_driver_messages(commands)
    assert messages[0]["type"] == "driver_input"
    assert messages[0]["train_index"] == 1
    assert messages[0]["source"] == "udp"


def test_vehicle_formal_api_codec_matches_document_shape():
    manager = TrainManager()
    manager.reset_trains(25)

    values = build_api_output_values(manager)
    parsed = parse_api_output_values(values)
    parameters = build_api_input_parameters(
        {
            1: {
                "train_id": 1,
                "operation_command": 2,
                "segment": 3,
                "offset": 12.5,
                "direction": 1,
                "active_cab": 1,
            }
        }
    )

    assert len(values) == API_VALUE_COUNT
    assert len(parameters) == API_VALUE_COUNT
    assert parsed[1]["train_id"] == 1.0
    assert set(parsed) == set(range(1, 21))
    assert api_input_path(1, "train_id").endswith("/ID1/Value")
    assert api_input_path(20, "active_cab").endswith("/active_Tc20/Value")
    assert parameters[0] == {
        "path": "PowerSystemAndTrainsV1/SS_Trains1_2/Train1_2/Train_Control/ID1/Value",
        "value": 1.0,
    }


def test_command_percent_mapping():
    assert command_percent_to_levels(1, 50.0) == (2, 0)
    assert command_percent_to_levels(2, 75.0) == (0, 3)
    assert command_percent_to_levels(0, 100.0) == (0, 0)


@pytest.mark.parametrize(
    ("raw_level", "vehicle_level"),
    [
        (0, 0),
        (1, 1),
        (2, 1),
        (3, 2),
        (4, 2),
        (5, 3),
        (6, 3),
        (7, 4),
    ],
)
def test_driver_brake_level_maps_from_0_7_to_vehicle_0_4(
    raw_level, vehicle_level
):
    assert normalize_driver_brake_level(raw_level) == vehicle_level


def test_router_accepts_command_percent_input():
    manager = TrainManager()
    router = MessageRouter(manager)
    router.handle(
        {
            "type": "driver_input",
            "vehicle_id": "TRAIN-001",
            "command": 1,
            "percent": 50.0,
        }
    )
    train = manager.get_train("TRAIN-001")
    assert train.requested_traction_level == 2
    assert train.requested_brake_level == 0
    assert train.current_traction_level == 0


def test_router_accepts_real_driver_desk_fast_brake_without_emergency():
    manager = TrainManager()
    router = MessageRouter(manager)
    train = manager.get_train("TRAIN-001")
    initial_position = train.state.position
    initial_speed = train.state.speed_ms

    router.handle(
        {
            "type": "driver_input",
            "train_index": 1,
            "main_handle_raw": 4,
            "traction_level": 4,
            "brake_level": 7,
            "control_mode": "manual",
            "emergency_button": False,
        }
    )

    assert train.cached_traction_level == 0
    assert train.cached_brake_level == 4
    assert train.current_traction_level == 0
    assert train.current_brake_level == 4
    assert train.fast_brake is True
    assert train.state.emergency_brake is False
    assert train.state.position == initial_position
    assert train.state.speed_ms == initial_speed


def test_router_driver_input_resolves_traction_brake_conflict():
    manager = TrainManager()
    router = MessageRouter(manager)
    router.handle(
        {
            "type": "driver_input",
            "train_index": 1,
            "traction_level": 3,
            "brake_level": 2,
        }
    )

    train = manager.get_train("TRAIN-001")
    assert train.cached_traction_level == 0
    assert train.cached_brake_level > 0


def test_step_manual_caches_without_integrating_until_step_tick():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    initial_position = train.state.position
    initial_speed = train.state.speed_ms
    initial_acceleration = train.state.acceleration

    train.step_manual(
        DriverInput(
            vehicle_id="TRAIN-001",
            line_id="LINE-1",
            source="test",
            control_mode="manual",
            traction_level=3,
            brake_level=0,
            direction="forward",
            emergency_button=False,
        ),
        dt=1.0,
    )

    assert train.state.position == initial_position
    assert train.state.speed_ms == initial_speed
    assert train.state.acceleration == initial_acceleration
    assert train.cached_traction_level == 3
    assert train.cached_brake_level == 0

    train.step_tick(1.0)

    assert train.state.speed_ms > initial_speed
    assert train.state.position > initial_position


def test_step_ato_caches_without_integrating():
    manager = TrainManager()
    train = manager.get_train("TRAIN-001")
    initial_position = train.state.position
    initial_speed = train.state.speed_ms

    command = AtoCommand(
        vehicle_id="TRAIN-001",
        line_id="LINE-1",
        control_mode="ato",
        target_speed=30.0,
        target_position=None,
        traction_level=2,
        brake_level=0,
        reason="test",
    )
    train.step_ato(command, dt=1.0)

    assert train.cached_external_ato_command is command
    assert train.cached_traction_level == 2
    assert train.cached_brake_level == 0
    assert train.state.position == initial_position
    assert train.state.speed_ms == initial_speed


def test_driver_input_maps_driving_mode_and_direction():
    manager = TrainManager()
    router = MessageRouter(manager)
    train = manager.get_train("TRAIN-001")

    router.handle(
        {
            "type": "driver_input",
            "train_index": 1,
            "control_mode": "ato",
            "ato_active": True,
            "direction": "backward",
        }
    )
    assert train.driving_mode == "AM"
    assert train.state.direction_code == -1

    router.handle(
        {
            "type": "driver_input",
            "train_index": 1,
            "control_mode": "manual",
            "ato_active": False,
            "direction": "neutral",
        }
    )
    assert train.driving_mode == "SM"
    assert train.state.direction_code == 0

    router.handle(
        {
            "type": "driver_input",
            "train_index": 1,
            "control_mode": "manual",
            "direction": "forward",
        }
    )
    assert train.state.direction_code == 1


@pytest.mark.parametrize("field", ["emergency_button", "emergency_cmd"])
def test_driver_emergency_fields_set_emergency(field):
    manager = TrainManager()
    router = MessageRouter(manager)

    router.handle(
        {
            "type": "driver_input",
            "train_index": 1,
            field: True,
        }
    )

    train = manager.get_train("TRAIN-001")
    assert train.state.emergency_brake is True
    assert train.emergency_pending is True


def test_router_set_train_state_creates_missing_train():
    manager = TrainManager()
    router = MessageRouter(manager)

    result = router.handle(
        {
            "type": "set_train_state",
            "vehicle_id": "TRAIN-011",
            "position": 1200.0,
            "speed": 36.0,
        }
    )

    assert result["ok"] is True
    assert result["created"] is True
    assert result["vehicle_id"] == "TRAIN-011"
    assert result["train_index"] == 11
    train = manager.get_train("TRAIN-011")
    assert train is not None
    assert train.state.position == 1200.0
    assert train.state.speed_kmh == 36.0


def test_router_accepts_flat_ma_state_like_data_flow_listener():
    manager = TrainManager()
    router = MessageRouter(manager)

    router.handle(
        {
            "type": "ma_state",
            "vehicle_id": "TRAIN-001",
            "ma_limit": 500.0,
            "speed_limit": 45.0,
            "distance_to_ma": 120.0,
            "permission": "restricted",
            "signal_state": "yellow",
        }
    )

    train = manager.get_train("TRAIN-001")
    assert train.ma_limit == 500.0
    assert train.allowed_speed_kmh == 45.0
    assert train.target_distance_m == 120.0
    assert train.permission == "restricted"

