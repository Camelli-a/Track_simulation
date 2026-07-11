from copy import deepcopy
from typing import Any

from app.services.signal_track_config import (
    DEFAULT_ROUTE_ID,
    DEFAULT_TRAIN_LENGTH,
    SIGNALS,
    SWITCHES,
)


DIRECTION_UP_CODE = 0x55
DIRECTION_DOWN_CODE = 0xAA

SWITCH_DEFAULT_CODE = 0x00
SWITCH_NORMAL_CODE = 0x01
SWITCH_REVERSE_CODE = 0x02
SWITCH_FOUR_OPEN_CODE = 0x04

SIGNAL_DEFAULT_CODE = 0x00
SIGNAL_RED_CODE = 0x01
SIGNAL_YELLOW_CODE = 0x02
SIGNAL_RED_YELLOW_CODE = 0x03
SIGNAL_GREEN_CODE = 0x04
SIGNAL_YELLOW_OFF_CODE = 0x05
SIGNAL_RED_OFF_CODE = 0x06
SIGNAL_GREEN_OFF_CODE = 0x07
SIGNAL_WHITE_CODE = 0x08
SIGNAL_RED_BROKEN_CODE = 0x09
SIGNAL_BLUE_CODE = 0x0A
SIGNAL_GREEN_BROKEN_CODE = 0x10
SIGNAL_YELLOW_BROKEN_CODE = 0x20
SIGNAL_WHITE_BROKEN_CODE = 0x30

TRACTION_COMMAND_CODE = 0x55
BRAKE_COMMAND_CODE = 0xAA
INVALID_COMMAND_CODE = 0x00


_MISSING = object()


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def _to_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            return int(value.strip(), 0)
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_hardware_train_state(data: dict) -> dict:
    numeric_train_id = _to_int(
        _first_present(
            data,
            [
                "train_id",
                "numeric_train_id",
                "vehicle_numeric_id",
                "列车ID",
                "列车 ID",
            ],
        ),
        0,
    )
    vehicle_id = data.get("vehicle_id") or (
        f"TRAIN-{numeric_train_id:03d}" if numeric_train_id else "TRAIN-000"
    )

    speed_cm_s = _to_float(
        _first_present(data, ["speed_cm_s", "train_speed_cm_s", "列车速度"]),
        0.0,
    )
    distance_cm = _to_float(
        _first_present(
            data,
            [
                "distance_cm",
                "accumulated_distance_cm",
                "position_cm",
                "列车积累走行距离",
            ],
        ),
        0.0,
    )
    direction_code = _to_int(
        _first_present(data, ["direction_code", "train_direction", "列车运行方向"]),
        SWITCH_DEFAULT_CODE,
    )
    fault_speed_limit_value = _first_present(
        data,
        ["fault_speed_limit_cm_s", "故障限速"],
    )
    fault_speed_limit = (
        round(_to_float(fault_speed_limit_value, 0.0) * 0.036, 3)
        if fault_speed_limit_value is not _MISSING and _can_convert_float(fault_speed_limit_value)
        else None
    )

    return {
        "vehicle_id": str(vehicle_id),
        "numeric_train_id": numeric_train_id,
        "position": round(distance_cm / 100.0, 3),
        "speed": round(speed_cm_s * 0.036, 3),
        "direction": _direction_name(direction_code),
        "direction_code": direction_code,
        "route_id": str(data.get("route_id") or DEFAULT_ROUTE_ID),
        "train_length": _to_float(data.get("train_length"), DEFAULT_TRAIN_LENGTH),
        "load_kg": _to_float(
            _first_present(data, ["load_kg", "train_load_kg", "列车载重"]),
            0.0,
        ),
        "fault_speed_limit": fault_speed_limit,
        "emergency_brake": bool(
            _to_int(
                _first_present(
                    data,
                    ["emergency_brake", "emergency_brake_applied", "施加紧急制动"],
                ),
                0,
            )
        ),
        "traction_available_count": _to_int(
            _first_present(data, ["traction_available_count", "可用牵引数量"]),
            0,
        ),
        "brake_available_count": _to_int(
            _first_present(data, ["brake_available_count", "可用制动数量"]),
            0,
        ),
    }


def map_switch_position_to_hardware_code(position: str | None) -> int:
    normalized = _normalize_text(position)
    if normalized == "normal":
        return SWITCH_NORMAL_CODE
    if normalized == "reverse":
        return SWITCH_REVERSE_CODE
    if normalized in {"four_open", "fault"}:
        return SWITCH_FOUR_OPEN_CODE
    return SWITCH_DEFAULT_CODE


def map_switch_to_hardware_code(switch: dict) -> int:
    state = _normalize_text(switch.get("state"))
    position = _normalize_text(switch.get("position"))

    if state == "fault" or switch.get("fault") is True:
        return SWITCH_FOUR_OPEN_CODE
    if state == "four_open" or switch.get("four_open") is True:
        return SWITCH_FOUR_OPEN_CODE
    if state.startswith("moving_to_"):
        return SWITCH_DEFAULT_CODE
    if state in {"locked_normal", "normal"} or position == "normal":
        return SWITCH_NORMAL_CODE
    if state in {"locked_reverse", "reverse"} or position == "reverse":
        return SWITCH_REVERSE_CODE
    return SWITCH_DEFAULT_CODE


def map_signal_state_to_hardware_code(state: str | None) -> int:
    return {
        "red": SIGNAL_RED_CODE,
        "yellow": SIGNAL_YELLOW_CODE,
        "red_yellow": SIGNAL_RED_YELLOW_CODE,
        "green": SIGNAL_GREEN_CODE,
        "yellow_off": SIGNAL_YELLOW_OFF_CODE,
        "red_off": SIGNAL_RED_OFF_CODE,
        "green_off": SIGNAL_GREEN_OFF_CODE,
        "white": SIGNAL_WHITE_CODE,
        "red_broken": SIGNAL_RED_BROKEN_CODE,
        "blue": SIGNAL_BLUE_CODE,
        "green_broken": SIGNAL_GREEN_BROKEN_CODE,
        "yellow_broken": SIGNAL_YELLOW_BROKEN_CODE,
        "white_broken": SIGNAL_WHITE_BROKEN_CODE,
    }.get(_normalize_text(state), SIGNAL_DEFAULT_CODE)


def build_train_control_suggestion(ma_limit: dict) -> dict:
    permission = _normalize_text(ma_limit.get("permission"))
    current_speed = _to_float(ma_limit.get("current_speed"), 0.0)
    speed_limit = _to_float(ma_limit.get("speed_limit"), 0.0)
    target_speed = _to_float(ma_limit.get("target_speed"), 0.0)

    if permission == "stop":
        command = "brake"
        command_code = BRAKE_COMMAND_CODE
        percent = 100
        reason = "stop_permission"
    elif permission == "restricted" and current_speed > speed_limit:
        overspeed_ratio = (current_speed - speed_limit) / max(speed_limit, 1.0)
        command = "brake"
        command_code = BRAKE_COMMAND_CODE
        percent = int(clamp(round(overspeed_ratio * 100), 20, 80))
        reason = "overspeed_against_signal_limit"
    elif permission == "allow" and current_speed < target_speed:
        speed_gap_ratio = (target_speed - current_speed) / max(target_speed, 1.0)
        command = "traction"
        command_code = TRACTION_COMMAND_CODE
        percent = int(clamp(round(speed_gap_ratio * 100), 10, 60))
        reason = "below_target_speed"
    else:
        command = "coast"
        command_code = INVALID_COMMAND_CODE
        percent = 0
        reason = "no_traction_brake_required"

    return {
        "vehicle_id": ma_limit.get("vehicle_id"),
        "permission": ma_limit.get("permission"),
        "current_speed": current_speed,
        "speed_limit": speed_limit,
        "target_speed": target_speed,
        "command": command,
        "command_code": command_code,
        "percent": percent,
        "reason": reason,
    }


def build_hardware_signal_output(snapshot: dict) -> dict:
    readonly_snapshot = deepcopy(snapshot)
    switch_config_by_id = {item["switch_id"]: item for item in SWITCHES}
    signal_config_by_id = {item["signal_id"]: item for item in SIGNALS}

    switch_states = []
    for switch in readonly_snapshot.get("switches", []):
        switch_id = switch.get("switch_id")
        switch_config = switch_config_by_id.get(switch_id, {})
        source_index = switch_config.get("source_index", switch.get("source_index"))
        position = switch.get("position")
        switch_states.append(
            {
                "switch_id": switch_id,
                "source_index": source_index,
                "position": position,
                "hardware_code": map_switch_to_hardware_code(switch),
                "locked": switch.get("locked", False),
                "locked_by_route_id": switch.get("locked_by_route_id"),
            }
        )

    signal_states = []
    for signal in readonly_snapshot.get("signals", []):
        signal_id = signal.get("signal_id")
        signal_config = signal_config_by_id.get(signal_id, {})
        state = signal.get("signal_state") or signal.get("state") or "unknown"
        signal_states.append(
            {
                "signal_id": signal_id,
                "source_index": signal_config.get("source_index", signal.get("source_index")),
                "state": state,
                "hardware_code": map_signal_state_to_hardware_code(state),
                "route_id": signal.get("route_id"),
                "permission": signal.get("permission"),
            }
        )

    return {
        "switch_states": switch_states,
        "signal_states": signal_states,
        "train_control_suggestions": [
            build_train_control_suggestion(item)
            for item in readonly_snapshot.get("ma_limits", [])
        ],
    }


def _first_present(data: dict, keys: list[str]) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return _MISSING


def _can_convert_float(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _direction_name(direction_code: int) -> str:
    if direction_code == DIRECTION_UP_CODE:
        return "up"
    if direction_code == DIRECTION_DOWN_CODE:
        return "down"
    return "unknown"


def _normalize_text(value: str | None) -> str:
    if value is None:
        return "unknown"
    return str(value).strip().lower()
