import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_speed_limit import (  # noqa: E402
    find_static_speed_limit,
    resolve_speed_limit,
)


def test_find_static_speed_limit_returns_matching_limit():
    limit = find_static_speed_limit(300.0)

    assert limit["limit_id"] == "SL-001"
    assert limit["speed_limit"] == 60.0


def test_find_static_speed_limit_returns_none_outside_sections():
    assert find_static_speed_limit(300.0, static_speed_limits=[]) is None
    assert (
        find_static_speed_limit(
            300.0,
            static_speed_limits=[
                {
                    "limit_id": "SL-X",
                    "start": 500.0,
                    "end": 600.0,
                    "speed_limit": 45.0,
                }
            ],
        )
        is None
    )


def test_find_static_speed_limit_uses_min_when_overlapping():
    limit = find_static_speed_limit(
        300.0,
        static_speed_limits=[
            {
                "limit_id": "SL-80",
                "start": 0.0,
                "end": 500.0,
                "speed_limit": 80.0,
            },
            {
                "limit_id": "SL-45",
                "start": 100.0,
                "end": 400.0,
                "speed_limit": 45.0,
            },
        ],
    )

    assert limit["limit_id"] == "SL-45"
    assert limit["speed_limit"] == 45.0


def test_resolve_speed_limit_static_lower_than_route():
    result = resolve_speed_limit(
        permission="allow",
        route_speed_limit=80.0,
        static_speed_limit=60.0,
        static_speed_limit_id="SL-001",
    )

    assert result["speed_limit"] == 60.0
    assert result["speed_limit_reason"] == "static_limit"


def test_resolve_speed_limit_braking_lower_than_static_when_restricted():
    result = resolve_speed_limit(
        permission="restricted",
        route_speed_limit=80.0,
        static_speed_limit=60.0,
        static_speed_limit_id="SL-001",
        braking_curve_speed_limit=40.0,
    )

    assert result["speed_limit"] == 40.0
    assert result["speed_limit_reason"] == "braking_curve"


def test_resolve_speed_limit_fault_lower_than_static():
    result = resolve_speed_limit(
        permission="allow",
        route_speed_limit=80.0,
        static_speed_limit=60.0,
        fault_speed_limit=30.0,
    )

    assert result["speed_limit"] == 30.0
    assert result["speed_limit_reason"] == "fault_limit"


def test_resolve_speed_limit_fault_zero_forces_stop():
    result = resolve_speed_limit(
        permission="allow",
        route_speed_limit=80.0,
        static_speed_limit=60.0,
        fault_speed_limit=0.0,
    )

    assert result["speed_limit"] == 0.0
    assert result["speed_limit_reason"] == "fault_limit"
    assert result["permission_override"] == "stop"
    assert result["signal_state_override"] == "red"


def test_resolve_speed_limit_emergency_brake_forces_stop():
    result = resolve_speed_limit(
        permission="allow",
        route_speed_limit=80.0,
        static_speed_limit=60.0,
        emergency_brake=True,
    )

    assert result["speed_limit"] == 0.0
    assert result["speed_limit_reason"] == "emergency_brake"
    assert result["permission_override"] == "stop"
    assert result["signal_state_override"] == "red"
