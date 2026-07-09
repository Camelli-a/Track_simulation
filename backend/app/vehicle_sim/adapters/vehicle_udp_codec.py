import struct

from .command_mapping import clamp_percent, command_percent_to_levels
from .id_mapping import UDP_TRAIN_SLOTS

MODEL_IP = "192.168.200.110"
MODEL_PORT = 23001
PLATFORM_IP = "192.168.200.102"
PLATFORM_PORT = 23002
UDP_CYCLE_SECONDS = 0.02
API_CYCLE_SECONDS = 0.5
ENDIANNESS = "<"

OUTPUT_VALUES_PER_TRAIN = 3
INPUT_VALUES_PER_TRAIN = 2
OUTPUT_FIELDS_PER_TRAIN = OUTPUT_VALUES_PER_TRAIN
INPUT_FIELDS_PER_TRAIN = INPUT_VALUES_PER_TRAIN

OUTPUT_PACKET_SIZE = UDP_TRAIN_SLOTS * OUTPUT_FIELDS_PER_TRAIN * 8
INPUT_PACKET_SIZE = UDP_TRAIN_SLOTS * INPUT_FIELDS_PER_TRAIN * 8


def pack_vehicle_output(train_manager_or_states) -> bytes:
    """Pack UDP slots 1..20 into the formal little-endian UDP payload.

    The internal vehicle manager can maintain more trains than the UDP protocol
    frame carries. This adapter intentionally exports only the fixed formal
    UDP slots and leaves higher internal slots to JSON/ZMQ/REST paths.
    """
    values = []
    train_states = _states_by_slot(train_manager_or_states)

    for train_index in range(1, UDP_TRAIN_SLOTS + 1):
        state = train_states.get(train_index)
        if state is None:
            values.extend([0.0, 0.0, 0.0])
            continue

        output_state = normalize_vehicle_output_state(state)
        values.append(output_state["acceleration"])
        values.append(output_state["speed"])
        values.append(output_state["mileage"])

    return struct.pack(ENDIANNESS + "d" * len(values), *values)


def unpack_vehicle_output(data: bytes) -> dict[int, dict]:
    if len(data) != OUTPUT_PACKET_SIZE:
        raise ValueError(
            f"vehicle output packet must be {OUTPUT_PACKET_SIZE} bytes, got {len(data)}"
        )

    values = struct.unpack(
        ENDIANNESS + "d" * (UDP_TRAIN_SLOTS * OUTPUT_FIELDS_PER_TRAIN),
        data,
    )
    result = {}
    for i in range(UDP_TRAIN_SLOTS):
        offset = i * OUTPUT_FIELDS_PER_TRAIN
        result[i + 1] = {
            "acceleration": values[offset],
            "speed": values[offset + 1],
            "mileage": values[offset + 2],
        }
    return result


def unpack_vehicle_input(data: bytes) -> dict[int, dict]:
    if len(data) < INPUT_PACKET_SIZE:
        raise ValueError(
            f"vehicle input packet must be at least {INPUT_PACKET_SIZE} bytes, got {len(data)}"
        )
    data = data[:INPUT_PACKET_SIZE]

    values = struct.unpack(
        ENDIANNESS + "d" * (UDP_TRAIN_SLOTS * INPUT_FIELDS_PER_TRAIN),
        data,
    )
    result = {}

    for i in range(UDP_TRAIN_SLOTS):
        train_index = i + 1
        command = int(values[i * INPUT_FIELDS_PER_TRAIN])
        percent = clamp_percent(values[i * INPUT_FIELDS_PER_TRAIN + 1])
        traction_level, brake_level = command_percent_to_levels(command, percent)

        result[train_index] = {
            "command": command,
            "percent": percent,
            "traction_level": traction_level,
            "brake_level": brake_level,
        }

    return result


def pack_vehicle_input(commands: dict[int, dict]) -> bytes:
    values = []
    for train_index in range(1, UDP_TRAIN_SLOTS + 1):
        command = commands.get(train_index, {})
        values.append(float(command.get("command", 0)))
        values.append(clamp_percent(command.get("percent", 0.0)))
    return struct.pack(ENDIANNESS + "d" * len(values), *values)


def normalize_vehicle_output_state(state: dict) -> dict:
    """Normalize internal train_state/protocol fields to UDP output fields.

    The vehicle UDP table names the output fields as acceleration, speed, and
    cumulative mileage. The current internal train_state uses position in
    meters, so position is accepted as the default mileage source until the
    formal document confirms a different unit convention.
    """
    mileage = state.get("mileage", state.get("position", 0.0))
    return {
        "acceleration": float(state.get("acceleration", 0.0)),
        "speed": float(state.get("speed", 0.0)),
        "mileage": float(mileage),
    }


def pack_protocol_train_states(train_states: list[dict]) -> bytes:
    states_by_index = {}
    for state in train_states:
        train_index = int(state.get("train_index", 0))
        if 1 <= train_index <= UDP_TRAIN_SLOTS:
            states_by_index[train_index] = state
    return pack_vehicle_output(states_by_index)


def vehicle_input_to_driver_messages(commands: dict[int, dict]) -> list[dict]:
    messages = []
    for train_index, command in sorted(commands.items()):
        messages.append(
            {
                "type": "driver_input",
                "train_index": train_index,
                "command": command["command"],
                "percent": command["percent"],
                "source": "vehicle_udp",
                "control_mode": "manual",
            }
        )
    return messages


def _states_by_slot(train_manager_or_states) -> dict[int, dict]:
    if isinstance(train_manager_or_states, dict):
        return train_manager_or_states

    if hasattr(train_manager_or_states, "get_train_by_slot"):
        states = {}
        for slot in range(1, UDP_TRAIN_SLOTS + 1):
            train = train_manager_or_states.get_train_by_slot(slot)
            if train is not None:
                states[slot] = train.state.to_protocol()
        return states

    raise TypeError("pack_vehicle_output expects a TrainManager or dict[int, dict]")

