import pytest

from app.services.signal_control import calculate_signal_snapshot
from app.services.signal_speed_limit import (
    find_static_speed_limit,
    find_static_speed_limit_with_preview,
)
from app.services.signal_track_config import STATIC_SPEED_LIMITS


def test_static_speed_limit_preview_warns_before_short_low_speed_segment():
    test_limits = [
        {"limit_id": "A", "start": 0.0, "end": 100.0, "speed_limit": 80.0},
        {"limit_id": "B", "start": 100.0, "end": 140.0, "speed_limit": 35.0},
    ]
    preview = find_static_speed_limit_with_preview(
        60.0,
        route_speed_limit=80.0,
        decel_mps2=0.9,
        static_speed_limits=test_limits,
    )

    assert preview is not None
    assert preview["preview"] is True
    assert preview["preview_target_speed_limit"] == pytest.approx(35.0)
    assert preview["preview_distance_to_start_m"] == pytest.approx(40.0)
    assert 35.0 <= preview["speed_limit"] < 80.0


def test_known_2014m_short_high_island_is_flattened_to_35kmh():
    for position in [1988.9, 2015.9, 2035.0, 2048.0, 2055.6]:
        limit = find_static_speed_limit(position)

        assert limit is not None
        assert limit["speed_limit"] == pytest.approx(35.0)


def test_static_speed_table_has_no_short_high_islands_between_lower_limits():
    high_islands = []
    i = 0
    while i < len(STATIC_SPEED_LIMITS):
        if STATIC_SPEED_LIMITS[i]["speed_limit"] >= 90.0:
            j = i
            while (
                j < len(STATIC_SPEED_LIMITS)
                and STATIC_SPEED_LIMITS[j]["speed_limit"] >= 90.0
            ):
                j += 1
            prev_limit = STATIC_SPEED_LIMITS[i - 1] if i > 0 else None
            next_limit = STATIC_SPEED_LIMITS[j] if j < len(STATIC_SPEED_LIMITS) else None
            length_m = STATIC_SPEED_LIMITS[j - 1]["end"] - STATIC_SPEED_LIMITS[i]["start"]
            if (
                prev_limit is not None
                and next_limit is not None
                and length_m <= 120.0
                and prev_limit["speed_limit"] < 90.0
                and next_limit["speed_limit"] < 90.0
            ):
                high_islands.append(
                    (
                        STATIC_SPEED_LIMITS[i]["limit_id"],
                        STATIC_SPEED_LIMITS[j - 1]["limit_id"],
                    )
                )
            i = j
        else:
            i += 1

    assert high_islands == []


def test_signal_ma_uses_flattened_static_limit_at_2035m():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 2035.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            }
        ]
    )

    ma_limit = snapshot["ma_limits"][0]

    assert ma_limit["speed_limit_reason"] == "static_limit"
    assert ma_limit["speed_limit_warning"] is False
    assert ma_limit["static_speed_limit"] == pytest.approx(35.0)
    assert ma_limit["speed_limit"] == pytest.approx(35.0)
