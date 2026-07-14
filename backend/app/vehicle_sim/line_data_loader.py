"""Vehicle-side loader for converted official line data.

The vehicle simulation consumes metre/SI data.  This module adapts the
converted `line-layout.json` into `TrackMap`/`TrackSection` without importing
frontend code or signal services.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import TrackSection
from .track_map import TrackMap


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LINE_LAYOUT_PATH = PROJECT_ROOT / "frontend" / "public" / "data" / "line-layout.json"

# TRAIN-001 demo runs down-track, and TrainState.position_m is the front cab.
# The old stop targets came from platform StopLeftKm (the near edge), which
# stopped the cab at the platform entrance.  These values are Track=0
# StopRightKm from "视景系统公里标最新数据+站台位置20260703.xlsx" sheet "站台位置".
DOWN_PLATFORM_FRONT_CAB_STOPS_M = {
    "ST-01": 431.0,
    "ST-02": 1778.52,
    "ST-03": 2566.61,
    "ST-04": 3547.32,
    "ST-05": 5133.834,
    "ST-06": 6459.274,
    "ST-07": 8238.204,
    "ST-08": 9547.344,
    "ST-09": 10718.11378,
    "ST-10": 12117.07,
    "ST-11": 14029.28014,
    "ST-12": 15072.91,
    "ST-13": 16169.01966,
}


def default_line_layout_path() -> Path:
    return DEFAULT_LINE_LAYOUT_PATH


def load_line_layout(path: str | Path | None = None) -> dict[str, Any]:
    layout_path = Path(path) if path is not None else default_line_layout_path()
    if not layout_path.is_absolute():
        layout_path = PROJECT_ROOT / layout_path
    with layout_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_track_map_from_line_layout(path: str | Path | None = None) -> TrackMap:
    return TrackMap(build_track_sections(load_line_layout(path)))


def build_track_sections(layout: dict[str, Any]) -> list[TrackSection]:
    sections = _layout_sections(layout)
    speed_limits = layout.get("speed_limits", {}).get("static", [])
    result = []

    for index, section in enumerate(sections, start=1):
        start = float(section.get("start", 0.0))
        end = float(section.get("end", start))
        if end < start:
            start, end = end, start
        speed_limit = _effective_speed_limit_kmh(section, speed_limits, start, end)
        edge_id = _int_or_none(section.get("edge_id") or section.get("track_seg_id")) or index
        station_id = section.get("station_id")
        stop_position = _section_stop_position(section, station_id, start, end)

        result.append(
            TrackSection(
                section_id=str(section.get("section_id") or section.get("segment_id") or f"SEC-{index:03d}"),
                start=start,
                end=end,
                gradient=_normalize_gradient_permille(section.get("gradient", 0.0)),
                speed_limit=speed_limit,
                station_id=station_id,
                stop_position=stop_position,
                edge_id=edge_id,
                begin_km=_float_or_none(section.get("begin_km")) or start / 1000.0,
                end_km=_float_or_none(section.get("end_km")) or end / 1000.0,
                begin_switch=section.get("begin_switch"),
                end_switch=section.get("end_switch"),
                direction_code=int(section.get("direction_code", 1) or 1),
            )
        )

    if not result:
        raise ValueError("line layout does not contain any track sections")
    return sorted(result, key=lambda item: (item.start, item.end, item.section_id))


def build_initial_train_configs(
    count: int,
    *,
    spacing_m: float = 300.0,
    line_id: str = "LINE-1",
    start_position_m: float = 0.0,
) -> list[dict[str, Any]]:
    """Build explicit demo train configs.

    The official line workbook does not define runtime train instances, so
    this helper is deliberately parameter-driven.
    """

    count = max(0, int(count))
    spacing_m = float(spacing_m)
    start_position_m = float(start_position_m)
    return [
        {
            "vehicle_id": f"TRAIN-{index:03d}",
            "train_index": index,
            "line_id": line_id,
            "position_m": start_position_m + (index - 1) * spacing_m,
        }
        for index in range(1, count + 1)
    ]


def _layout_sections(layout: dict[str, Any]) -> list[dict[str, Any]]:
    track_info_sections = layout.get("track_info", {}).get("sections")
    if isinstance(track_info_sections, list) and track_info_sections:
        return track_info_sections
    blocks = layout.get("blocks")
    if isinstance(blocks, list) and blocks:
        return blocks
    raise ValueError("line layout must contain track_info.sections or blocks")


def _section_stop_position(
    section: dict[str, Any],
    station_id: str | None,
    section_start_m: float,
    section_end_m: float,
) -> float | None:
    if not station_id:
        return None
    if station_id in DOWN_PLATFORM_FRONT_CAB_STOPS_M:
        return _valid_stop_position(
            DOWN_PLATFORM_FRONT_CAB_STOPS_M[station_id],
            section_start_m,
            section_end_m,
        )
    return _valid_stop_position(section.get("stop_position"), section_start_m, section_end_m)


def _effective_speed_limit_kmh(
    section: dict[str, Any],
    speed_limits: Iterable[dict[str, Any]],
    section_start_m: float,
    section_end_m: float,
) -> float:
    candidates = []
    for item in speed_limits or []:
        start_m = _float_or_none(item.get("start_m"))
        end_m = _float_or_none(item.get("end_m"))
        if start_m is None or end_m is None:
            continue
        if end_m < start_m:
            start_m, end_m = end_m, start_m
        overlaps = section_start_m < end_m and section_end_m > start_m
        if overlaps:
            converted = _normalize_speed_limit_kmh(item.get("speed_limit"))
            if converted is not None and converted > 0:
                candidates.append(converted)

    if candidates:
        return min(candidates)
    fallback = _normalize_speed_limit_kmh(section.get("speed_limit"))
    return 60.0 if fallback is None or fallback <= 0 else fallback


def _normalize_speed_limit_kmh(value: Any) -> float | None:
    number = _float_or_none(value)
    if number is None:
        return None
    # Some official tables store speed as cm/s; values like 416.666 mean 15km/h.
    if number > 120.0:
        return round(number * 0.036, 3)
    return float(number)


def _normalize_gradient_permille(value: Any) -> float:
    """Return a physically plausible gradient in permille for dynamics.

    Several teacher workbook slope tables store values as tenths of permille:
    ``300`` means ``30.0‰``.  The converted station-yard section data can still
    contain those raw values.  Vehicle dynamics must not treat them as 300‰.
    """

    number = _float_or_none(value)
    if number is None:
        return 0.0
    if abs(number) > 60.0:
        number = number / 10.0
    return max(-60.0, min(60.0, float(number)))


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _valid_stop_position(value: Any, section_start_m: float, section_end_m: float) -> float | None:
    stop_position = _float_or_none(value)
    if stop_position is None or stop_position <= 0.0:
        return None
    if section_start_m <= stop_position <= section_end_m:
        return stop_position
    return None


def _int_or_none(value: Any) -> int | None:
    number = _float_or_none(value)
    if number is None:
        return None
    return int(number)
