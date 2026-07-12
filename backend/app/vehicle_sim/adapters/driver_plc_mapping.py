from .command_mapping import (
    command_percent_to_levels,
    normalize_driver_brake_level,
    normalize_driver_traction_level,
)

HANDLE_COAST = 0
HANDLE_TRACTION = 1
HANDLE_BRAKE = 2
HANDLE_FAST_BRAKE = 4

DIRECTION_NEUTRAL = 0
DIRECTION_FORWARD = 1
DIRECTION_REVERSE = 2


def direction_code_to_text(direction_code: int | None) -> str:
    if direction_code == DIRECTION_REVERSE:
        return "reverse"
    if direction_code == DIRECTION_FORWARD:
        return "forward"
    return "neutral"


def decode_driver_handle(message: dict) -> tuple[int, int]:
    main_handle_state = int(
        message.get("main_handle_raw", message.get("main_handle_state", HANDLE_COAST))
    )

    if main_handle_state == HANDLE_TRACTION:
        if message.get("traction_level") is not None:
            return normalize_driver_traction_level(message.get("traction_level")), 0
        return command_percent_to_levels(1, float(message.get("traction_percent", 0.0)))

    if main_handle_state == HANDLE_BRAKE:
        if message.get("brake_level") is not None:
            return 0, normalize_driver_brake_level(message.get("brake_level"))
        return command_percent_to_levels(2, float(message.get("brake_percent", 0.0)))

    if main_handle_state == HANDLE_FAST_BRAKE:
        return 0, 4

    return 0, 0

