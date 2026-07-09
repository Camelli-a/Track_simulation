import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_track_config import (  # noqa: E402
    GRADIENT_PROFILE,
    PLATFORMS,
    STATIC_SPEED_LIMITS,
    STATIONS,
    STOP_TARGETS,
)


def test_stop_targets_exported_from_track_config():
    assert STOP_TARGETS
    assert any(target["route_id"] == "R_MAIN" for target in STOP_TARGETS)
    assert any(target["route_id"] == "R_BRANCH" for target in STOP_TARGETS)


def test_stop_targets_have_required_protocol_fields():
    required_fields = {
        "target_id",
        "station_id",
        "route_id",
        "position",
        "window_before",
        "window_after",
        "approach_distance",
        "source",
    }

    for target in STOP_TARGETS:
        assert required_fields <= set(target)
        assert target["position"] >= 0.0
        assert target["window_before"] > 0.0
        assert target["window_after"] > 0.0
        assert target["approach_distance"] > 0.0


def test_stations_and_platforms_extracted_from_teacher_tables():
    assert STATIONS
    assert PLATFORMS
    assert STATIONS[0]["station_id"] == "ST-001"
    assert STATIONS[0]["station_name"] == "GGZ"
    assert PLATFORMS[0]["platform_id"] == "PF-001"
    assert PLATFORMS[0]["source"] == "teacher_platform_table"


def test_static_speed_limits_exported_from_teacher_table():
    assert STATIC_SPEED_LIMITS
    assert len(STATIC_SPEED_LIMITS) > 2
    assert STATIC_SPEED_LIMITS[0]["source"] == "teacher_static_speed_limit_table"
    assert STATIC_SPEED_LIMITS[0]["speed_limit_unit"] == "cm/s"
    assert STATIC_SPEED_LIMITS[0]["speed_limit"] == 48.0
    assert not (
        len(STATIC_SPEED_LIMITS) == 2
        and STATIC_SPEED_LIMITS[0]["start"] == 0.0
        and STATIC_SPEED_LIMITS[0]["end"] == 500.0
        and STATIC_SPEED_LIMITS[1]["start"] == 500.0
        and STATIC_SPEED_LIMITS[1]["end"] == 2500.0
    )


def test_static_speed_limits_have_required_fields_and_valid_ranges():
    required_fields = {
        "limit_id",
        "source_index",
        "source_name",
        "seg_id",
        "start_offset_m",
        "end_offset_m",
        "start",
        "end",
        "speed_limit",
        "speed_limit_raw",
        "speed_limit_unit",
        "related_switch_id",
        "direction",
        "reason",
        "source",
    }

    for limit in STATIC_SPEED_LIMITS:
        assert required_fields <= set(limit)
        assert limit["start"] < limit["end"]
        assert 0.0 < limit["speed_limit"] <= 160.0
        assert limit["source"] == "teacher_static_speed_limit_table"


def test_gradient_profile_exported_from_teacher_table():
    assert GRADIENT_PROFILE
    assert len(GRADIENT_PROFILE) > 2
    assert GRADIENT_PROFILE[0]["source"] == "teacher_gradient_table"
    assert GRADIENT_PROFILE[0]["gradient_unit"] == "permille"


def test_gradient_profile_has_required_fields_and_valid_ranges():
    required_fields = {
        "gradient_id",
        "source_index",
        "source_name",
        "seg_id",
        "start_offset_m",
        "end_offset_m",
        "start",
        "end",
        "gradient",
        "gradient_unit",
        "direction",
        "source",
    }

    for gradient in GRADIENT_PROFILE:
        assert required_fields <= set(gradient)
        assert gradient["start"] < gradient["end"]
        assert gradient["gradient_unit"] == "permille"
        assert gradient["source"] == "teacher_gradient_table"
