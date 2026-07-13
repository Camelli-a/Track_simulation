import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.data_flow.data_mapper import normalize_ato_command, normalize_switch  # noqa: E402


def test_normalize_switch_accepts_locked_positions():
    normal = normalize_switch({"switch_id": "SW-01", "position": "locked_normal"})
    reverse = normalize_switch({"switch_id": "SW-02", "state": "locked_reverse"})

    assert normal["position"] == "normal"
    assert normal["routing"] == "normal"
    assert normal["state"] == "normal"
    assert normal["locked"] is True

    assert reverse["position"] == "reverse"
    assert reverse["routing"] == "reverse"
    assert reverse["state"] == "reverse"
    assert reverse["locked"] is True


def test_normalize_ato_command_accepts_signal_adapter_output():
    command = normalize_ato_command(
        {
            "vehicle_id": "TRAIN-001",
            "control_mode": "ATO",
            "target_speed": 48.0,
            "traction_level": 5,
            "brake_level": 9,
        }
    )

    assert command["control_mode"] == "ato"
    assert command["traction_level"] == 4
    assert command["brake_level"] == 7
