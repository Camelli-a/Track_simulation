from app.vehicle_sim.adapters.command_mapping import command_percent_to_levels
from app.vehicle_sim.adapters.id_mapping import index_to_vehicle_id, vehicle_id_to_index
from app.vehicle_sim.adapters.units import m_to_cm, m_to_mm, ms_to_cms, ms_to_mms
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
from app.vehicle_sim.train_manager import TrainManager


def test_id_and_unit_mapping():
    assert vehicle_id_to_index("TRAIN-001") == 1
    assert index_to_vehicle_id(2) == "TRAIN-002"
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


def test_vehicle_input_clamps_percent_and_builds_driver_messages():
    packet = pack_vehicle_input({1: {"command": 1, "percent": 150.0}})
    commands = unpack_vehicle_input(packet)

    assert commands[1]["percent"] == 100.0
    messages = vehicle_input_to_driver_messages(commands)
    assert messages[0]["type"] == "driver_input"
    assert messages[0]["train_index"] == 1
    assert messages[0]["source"] == "vehicle_udp"


def test_command_percent_mapping():
    assert command_percent_to_levels(1, 50.0) == (2, 0)
    assert command_percent_to_levels(2, 75.0) == (0, 3)
    assert command_percent_to_levels(0, 100.0) == (0, 0)


def test_router_accepts_command_percent_input():
    manager = TrainManager()
    router = MessageRouter(manager)
    router.handle(
        {
            "type": "driver_input",
            "train_index": 1,
            "command": 1,
            "percent": 50.0,
        }
    )
    train = manager.get_train("TRAIN-001")
    assert train.current_traction_level == 2
    assert train.current_brake_level == 0

