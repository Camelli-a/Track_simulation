COMMAND_COAST = 0
COMMAND_TRACTION = 1
COMMAND_BRAKE = 2

SIGNAL_TRACTION = 0x55
SIGNAL_BRAKE = 0xAA


def clamp_percent(percent: float) -> float:
    return max(0.0, min(float(percent), 100.0))


def level_to_percent(level: int) -> float:
    level = max(0, min(int(level), 4))
    return level / 4 * 100.0


def percent_to_level(percent: float) -> int:
    percent = clamp_percent(percent)
    if percent == 0:
        return 0
    if percent <= 25:
        return 1
    if percent <= 50:
        return 2
    if percent <= 75:
        return 3
    return 4


def normalize_command(command: int) -> int:
    command = int(command)
    if command == SIGNAL_TRACTION:
        return COMMAND_TRACTION
    if command == SIGNAL_BRAKE:
        return COMMAND_BRAKE
    if command in (COMMAND_COAST, COMMAND_TRACTION, COMMAND_BRAKE):
        return command
    return COMMAND_COAST


def command_percent_to_levels(command: int, percent: float) -> tuple[int, int]:
    command = normalize_command(command)
    level = percent_to_level(percent)

    if command == COMMAND_TRACTION:
        return level, 0
    if command == COMMAND_BRAKE:
        return 0, level
    return 0, 0


def levels_to_command_percent(traction_level: int, brake_level: int) -> tuple[int, float]:
    if brake_level > 0:
        return COMMAND_BRAKE, level_to_percent(brake_level)
    if traction_level > 0:
        return COMMAND_TRACTION, level_to_percent(traction_level)
    return COMMAND_COAST, 0.0

