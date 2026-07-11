def kmh_to_ms(speed_kmh: float) -> float:
    return speed_kmh / 3.6


def ms_to_kmh(speed_ms: float) -> float:
    return speed_ms * 3.6


def ms_to_cms(speed_ms: float) -> int:
    return int(round(speed_ms * 100))


def ms_to_mms(speed_ms: float) -> int:
    return int(round(speed_ms * 1000))


def m_to_cm(position_m: float) -> int:
    return int(round(position_m * 100))


def m_to_mm(position_m: float) -> int:
    return int(round(position_m * 1000))

