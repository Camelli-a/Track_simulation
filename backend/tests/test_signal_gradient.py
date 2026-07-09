import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_gradient import (  # noqa: E402
    calculate_effective_deceleration,
    find_gradient_at_position,
)


def test_find_gradient_at_position_returns_matching_teacher_gradient():
    gradient = find_gradient_at_position(900.0)

    assert gradient["gradient_id"] == "GR-003"
    assert gradient["gradient"] == 3.4
    assert gradient["source"] == "teacher_gradient_table"


def test_find_gradient_at_position_returns_none_outside_profile():
    assert find_gradient_at_position(-10.0) is None
    assert find_gradient_at_position(
        100.0,
        gradient_profile=[
            {
                "gradient_id": "GR-X",
                "start": 200.0,
                "end": 300.0,
                "gradient": 5.0,
            }
        ],
    ) is None


def test_find_gradient_at_position_uses_shortest_matching_interval():
    gradient = find_gradient_at_position(
        120.0,
        gradient_profile=[
            {
                "gradient_id": "LONG",
                "source_index": 1,
                "start": 0.0,
                "end": 1000.0,
                "gradient": 1.0,
            },
            {
                "gradient_id": "SHORT",
                "source_index": 2,
                "start": 100.0,
                "end": 150.0,
                "gradient": -5.0,
            },
        ],
    )

    assert gradient["gradient_id"] == "SHORT"


def test_effective_deceleration_increases_on_uphill():
    assert calculate_effective_deceleration(0.8, 10.0) > 0.8


def test_effective_deceleration_decreases_on_downhill():
    assert calculate_effective_deceleration(0.8, -10.0) < 0.8


def test_effective_deceleration_clamps_to_range():
    assert calculate_effective_deceleration(0.8, -1000.0) == 0.35
    assert calculate_effective_deceleration(0.8, 1000.0) == 1.2
