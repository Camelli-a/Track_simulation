from .id_mapping import UDP_TRAIN_SLOTS

API_TRAIN_SLOTS = UDP_TRAIN_SLOTS
API_VALUES_PER_TRAIN = 6
API_VALUE_COUNT = API_TRAIN_SLOTS * API_VALUES_PER_TRAIN

OUTPUT_FIELDS = (
    "train_id",
    "active_cab",
    "direction",
    "acceleration",
    "speed",
    "mileage",
)

INPUT_FIELDS = (
    "train_id",
    "operation_command",
    "segment",
    "offset",
    "direction",
    "active_cab",
)


def build_api_output_values(train_manager_or_states) -> list[float]:
    """Build the formal RT-LAB API output vector.

    The vehicle interface document defines 20 trains and 6 float values per
    train: id, active end, direction, acceleration, speed, cumulative mileage.
    Internal trains beyond slot 20 remain available through REST/ZMQ/JSON and
    are intentionally not exported through this formal RT-LAB vector.
    """

    states = _states_by_slot(train_manager_or_states)
    values: list[float] = []
    for slot in range(1, API_TRAIN_SLOTS + 1):
        state = states.get(slot)
        if state is None:
            values.extend([0.0] * API_VALUES_PER_TRAIN)
            continue

        values.extend(
            [
                float(state.get("train_id", state.get("train_index", slot))),
                float(state.get("active_cab", state.get("active_end", 1.0))),
                float(state.get("direction", state.get("direction_code", 1.0))),
                float(state.get("acceleration", 0.0)),
                float(state.get("speed", 0.0)),
                float(state.get("mileage", state.get("position", 0.0))),
            ]
        )
    return values


def parse_api_output_values(values: list[float] | tuple[float, ...]) -> dict[int, dict]:
    if len(values) < API_VALUE_COUNT:
        raise ValueError(
            f"vehicle API output must contain at least {API_VALUE_COUNT} values, got {len(values)}"
        )

    result: dict[int, dict] = {}
    for slot in range(1, API_TRAIN_SLOTS + 1):
        offset = (slot - 1) * API_VALUES_PER_TRAIN
        result[slot] = {
            field: float(values[offset + index])
            for index, field in enumerate(OUTPUT_FIELDS)
        }
    return result


def build_api_input_parameters(commands_by_slot: dict[int, dict]) -> list[dict]:
    """Build OpalSetParametersByName-style path/value records.

    Field order follows the vehicle interface document's model input variables:
    train id, operation command, segment id, offset, direction, active end.
    """

    parameters: list[dict] = []
    for slot in range(1, API_TRAIN_SLOTS + 1):
        command = commands_by_slot.get(slot, {})
        values = {
            "train_id": command.get("train_id", command.get("id", slot)),
            "operation_command": command.get(
                "operation_command",
                command.get("command", 0),
            ),
            "segment": command.get("segment", command.get("seg", 0)),
            "offset": command.get("offset", 0.0),
            "direction": command.get("direction", 1),
            "active_cab": command.get("active_cab", command.get("active_end", 1)),
        }

        for field in INPUT_FIELDS:
            parameters.append(
                {
                    "path": api_input_path(slot, field),
                    "value": float(values[field]),
                }
            )
    return parameters


def api_input_path(slot: int, field: str) -> str:
    if not 1 <= slot <= API_TRAIN_SLOTS:
        raise ValueError(f"API train slot must be 1..{API_TRAIN_SLOTS}: {slot}")
    if field not in INPUT_FIELDS:
        raise ValueError(f"unknown vehicle API input field: {field}")

    group = _slot_group(slot)
    signal_name = _input_signal_name(slot, field)
    return (
        f"PowerSystemAndTrainsV1/SS_Trains{group}/Train{group}/"
        f"Train_Control/{signal_name}/Value"
    )


def _slot_group(slot: int) -> str:
    if slot >= 18:
        return "18_20"
    start = slot if slot % 2 == 1 else slot - 1
    return f"{start}_{start + 1}"


def _input_signal_name(slot: int, field: str) -> str:
    prefixes = {
        "train_id": "ID",
        "operation_command": "num_seg",
        "segment": "x0_seg",
        "offset": "sig_train",
        "direction": "handle",
        "active_cab": "active_Tc",
    }
    return f"{prefixes[field]}{slot}"


def _states_by_slot(train_manager_or_states) -> dict[int, dict]:
    if isinstance(train_manager_or_states, dict):
        return train_manager_or_states

    if hasattr(train_manager_or_states, "get_train_by_slot"):
        states = {}
        for slot in range(1, API_TRAIN_SLOTS + 1):
            train = train_manager_or_states.get_train_by_slot(slot)
            if train is not None:
                states[slot] = train.state.to_protocol()
        return states

    raise TypeError("vehicle API codec expects a TrainManager or dict[int, dict]")
