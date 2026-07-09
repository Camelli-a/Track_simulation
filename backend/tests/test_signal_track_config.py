import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_track_config import PLATFORMS, STATIONS, STOP_TARGETS  # noqa: E402


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
