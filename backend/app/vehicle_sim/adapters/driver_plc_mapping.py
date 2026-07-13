"""Normalize driver-desk handle data into the vehicle control contract."""

from dataclasses import dataclass
from math import ceil

from .command_mapping import clamp_percent, percent_to_level

HANDLE_COAST = 0
HANDLE_TRACTION = 1
HANDLE_BRAKE = 2
HANDLE_FAST_BRAKE = 4

DIRECTION_NEUTRAL = 0
DIRECTION_FORWARD = 1
DIRECTION_REVERSE = 2

MAX_TRACTION_LEVEL = 4
MAX_SERVICE_BRAKE_LEVEL = 7


@dataclass(frozen=True)
class DriverControl:
    traction_level: int
    brake_level: int
    traction_percent: float
    brake_percent: float
    handle_mode: str


def direction_code_to_text(direction_code: int | None) -> str:
    if direction_code == DIRECTION_REVERSE:
        return "reverse"
    if direction_code == DIRECTION_FORWARD:
        return "forward"
    return "neutral"


def service_brake_percent_to_level(percent: float) -> int:
    normalized = clamp_percent(percent)
    if normalized == 0.0:
        return 0
    return min(MAX_SERVICE_BRAKE_LEVEL, ceil(normalized / 100.0 * 7.0))


def service_brake_level_to_percent(level: int) -> float:
    normalized = max(0, min(int(level), MAX_SERVICE_BRAKE_LEVEL))
    return normalized / MAX_SERVICE_BRAKE_LEVEL * 100.0


def traction_level_to_percent(level: int) -> float:
    normalized = max(0, min(int(level), MAX_TRACTION_LEVEL))
    return normalized / MAX_TRACTION_LEVEL * 100.0


def decode_driver_control(message: dict) -> DriverControl:
    """Use percentages as canonical control and levels as display metadata.

    ``main_handle_raw=4`` is treated as fast/maximum service braking, not ATP
    emergency braking.  The legacy ``main_handle_state`` alias is accepted at
    the adapter boundary.
    """
    raw_handle = message.get("main_handle_raw", message.get("main_handle_state"))
    if raw_handle is not None:
        handle = int(raw_handle)
        if handle == HANDLE_TRACTION:
            traction_percent = clamp_percent(message.get("traction_percent", 0.0))
            return DriverControl(
                traction_level=percent_to_level(traction_percent),
                brake_level=0,
                traction_percent=traction_percent,
                brake_percent=0.0,
                handle_mode="traction",
            )
        if handle == HANDLE_BRAKE:
            brake_percent = clamp_percent(message.get("brake_percent", 0.0))
            return DriverControl(
                traction_level=0,
                brake_level=service_brake_percent_to_level(brake_percent),
                traction_percent=0.0,
                brake_percent=brake_percent,
                handle_mode="brake",
            )
        if handle == HANDLE_FAST_BRAKE:
            return DriverControl(0, 7, 0.0, 100.0, "fast_brake")
        return DriverControl(0, 0, 0.0, 0.0, "coast")

    explicit_traction_percent = message.get("traction_percent")
    explicit_brake_percent = message.get("brake_percent")
    if explicit_traction_percent is not None or explicit_brake_percent is not None:
        traction_percent = clamp_percent(explicit_traction_percent or 0.0)
        brake_percent = clamp_percent(explicit_brake_percent or 0.0)
        if brake_percent > 0.0:
            traction_percent = 0.0
        return DriverControl(
            traction_level=percent_to_level(traction_percent),
            brake_level=service_brake_percent_to_level(brake_percent),
            traction_percent=traction_percent,
            brake_percent=brake_percent,
            handle_mode="brake" if brake_percent > 0.0 else "traction" if traction_percent > 0.0 else "coast",
        )

    traction_level = max(0, min(int(message.get("traction_level", 0)), 4))
    brake_level = max(0, min(int(message.get("brake_level", 0)), 7))
    if brake_level > 0:
        traction_level = 0
    return DriverControl(
        traction_level=traction_level,
        brake_level=brake_level,
        traction_percent=traction_level_to_percent(traction_level),
        brake_percent=service_brake_level_to_percent(brake_level),
        handle_mode="brake" if brake_level > 0 else "traction" if traction_level > 0 else "coast",
    )


def decode_driver_handle(message: dict) -> tuple[int, int]:
    """Compatibility wrapper returning display levels only."""
    control = decode_driver_control(message)
    return control.traction_level, control.brake_level
