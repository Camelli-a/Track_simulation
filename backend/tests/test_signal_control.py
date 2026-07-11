import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_control import (  # noqa: E402
    build_ma_state_message,
    build_signal_state_message,
    calculate_signal_snapshot,
)
from app.services.signal_zmq_adapter import SignalZmqAdapter  # noqa: E402
from main import app  # noqa: E402


class FakeMessageBus:
    def __init__(self):
        self.published = []
        self.subscriptions = []
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def subscribe(self, topic, handler):
        self.subscriptions.append((topic, handler))

    def publish(self, topic, data):
        self.published.append((topic, data))


def _ma_for(snapshot, vehicle_id):
    return next(item for item in snapshot["ma_limits"] if item["vehicle_id"] == vehicle_id)


def test_position_maps_to_section():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 620.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            }
        ]
    )

    section = next(item for item in snapshot["sections"] if item["section_id"] == "JZ1")
    assert section["occupied"] is True
    assert section["vehicle_id"] == "TRAIN-001"


def test_rear_vehicle_ma_limit_uses_front_vehicle_safe_distance():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            },
            {
                "vehicle_id": "TRAIN-002",
                "position": 620.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            },
        ]
    )

    ma_limit = _ma_for(snapshot, "TRAIN-001")
    assert ma_limit["front_vehicle_id"] == "TRAIN-002"
    assert ma_limit["front_train_length"] == 120.0
    assert ma_limit["location_uncertainty"] == 5.0
    assert ma_limit["communication_margin"] == 10.0
    assert ma_limit["safety_margin"] == 30.0
    assert ma_limit["front_protection_point"] == 455.0
    assert ma_limit["safe_distance"] == 165.0
    assert ma_limit["ma_limit"] == 455.0
    assert ma_limit["required_stop_distance"] == 108.4
    assert ma_limit["emergency_stop_distance"] == 98.1
    assert ma_limit["warning_distance"] == 158.4
    assert ma_limit["braking_curve_speed_limit"] > 0
    assert ma_limit["braking_model"] == "simplified_atp_braking_curve"


def test_far_from_ma_is_allow_green():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            }
        ]
    )

    ma_limit = _ma_for(snapshot, "TRAIN-001")
    assert ma_limit["permission"] == "allow"
    assert ma_limit["signal_state"] == "green"
    assert ma_limit["speed_limit"] == 48.0
    assert ma_limit["route_speed_limit"] == 80.0
    assert ma_limit["static_speed_limit"] == 48.0
    assert ma_limit["static_speed_limit_id"] == "SL-001"
    assert ma_limit["speed_limit_reason"] == "static_limit"


def test_distance_to_ma_between_80_and_200_is_restricted():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            },
            {
                "vehicle_id": "TRAIN-002",
                "position": 575.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            },
        ]
    )

    ma_limit = _ma_for(snapshot, "TRAIN-001")
    assert ma_limit["ma_limit"] == 410.0
    assert ma_limit["distance_to_ma"] == 110.0
    assert ma_limit["permission"] == "restricted"
    assert ma_limit["signal_state"] == "yellow"
    assert 0.0 < ma_limit["speed_limit"] <= ma_limit["route_speed_limit"]
    assert ma_limit["braking_curve_speed_limit"] == ma_limit["speed_limit"]
    assert ma_limit["speed_limit_reason"] == "braking_curve"


def test_distance_to_ma_at_or_below_80_is_stop():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            },
            {
                "vehicle_id": "TRAIN-002",
                "position": 500.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            },
        ]
    )

    ma_limit = _ma_for(snapshot, "TRAIN-001")
    assert ma_limit["ma_limit"] == 335.0
    assert ma_limit["permission"] == "stop"
    assert ma_limit["signal_state"] == "red"
    assert ma_limit["speed_limit"] == 0.0
    assert ma_limit["speed_limit_reason"] == "stop"


def test_ma_limit_includes_static_speed_limit():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            }
        ]
    )

    ma_limit = _ma_for(snapshot, "TRAIN-001")
    assert ma_limit["static_speed_limit"] == 48.0
    assert ma_limit["static_speed_limit_id"] == "SL-001"
    assert ma_limit["static_speed_limit_source"] == "teacher_static_speed_limit_table"
    assert ma_limit["static_speed_limit_related_switch_id"] is None
    assert "speed_limit_reason" in ma_limit


def test_static_limit_caps_speed_limit():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 20.0,
                "route_id": "R_MAIN",
            }
        ]
    )

    ma_limit = _ma_for(snapshot, "TRAIN-001")
    assert ma_limit["permission"] == "allow"
    assert ma_limit["speed_limit"] == 48.0
    assert ma_limit["speed_limit_reason"] == "static_limit"


def test_emergency_brake_forces_stop_in_ma_limit():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 620.0,
                "speed": 20.0,
                "route_id": "R_MAIN",
                "emergency_brake": True,
            }
        ]
    )

    ma_limit = _ma_for(snapshot, "TRAIN-001")
    assert ma_limit["permission"] == "stop"
    assert ma_limit["signal_state"] == "red"
    assert ma_limit["speed_limit"] == 0.0
    assert ma_limit["target_speed"] == 0.0
    assert ma_limit["speed_limit_reason"] == "emergency_brake"


def test_fault_speed_limit_participates_in_ma_limit():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 620.0,
                "speed": 20.0,
                "route_id": "R_MAIN",
                "fault_speed_limit": 30.0,
            }
        ]
    )

    ma_limit = _ma_for(snapshot, "TRAIN-001")
    assert ma_limit["speed_limit"] == 30.0
    assert ma_limit["fault_speed_limit"] == 30.0
    assert ma_limit["speed_limit_reason"] == "fault_limit"


def test_branch_route_request_conflicts_with_locked_main_switch():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-003",
                "position": 2435.0,
                "speed": 25.0,
                "route_id": "R_MAIN",
            }
        ],
        [
            {
                "vehicle_id": "TRAIN-003",
                "route_id": "R_BRANCH",
            }
        ],
    )

    result = snapshot["route_results"][0]
    assert result["allowed"] is False
    assert result["reason"] == "switch_locked_conflict"
    assert result["required_switch_id"] == "SW-01"
    assert result["required_position"] == "reverse"
    assert result["current_position"] == "normal"
    assert result["locked_by_route_id"] == "R_MAIN"


def test_signal_status_endpoint_returns_snapshot_fields():
    response = TestClient(app).get("/api/v1/signal/status")

    assert response.status_code == 200
    data = response.json()
    assert {
        "lights",
        "signals",
        "sections",
        "switches",
        "ma_limits",
        "route_results",
    } <= set(data)


def test_signal_evaluate_endpoint_returns_snapshot_fields():
    response = TestClient(app).post(
        "/api/v1/signal/evaluate",
        json={
            "train_states": [
                {
                    "vehicle_id": "TRAIN-001",
                    "position": 300.0,
                    "speed": 40.0,
                    "route_id": "R_MAIN",
                }
            ]
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert {
        "timestamp",
        "system_mode",
        "lights",
        "signals",
        "sections",
        "switches",
        "ma_limits",
        "route_results",
    } <= set(data)


def test_signal_evaluate_endpoint_calculates_rear_vehicle_ma_limit():
    response = TestClient(app).post(
        "/api/v1/signal/evaluate",
        json={
            "train_states": [
                {
                    "vehicle_id": "TRAIN-001",
                    "position": 300.0,
                    "speed": 40.0,
                    "route_id": "R_MAIN",
                },
                {
                    "vehicle_id": "TRAIN-002",
                    "position": 620.0,
                    "speed": 40.0,
                    "route_id": "R_MAIN",
                },
            ]
        },
    )

    assert response.status_code == 200
    ma_limit = _ma_for(response.json(), "TRAIN-001")
    assert ma_limit["front_vehicle_id"] == "TRAIN-002"
    assert ma_limit["ma_limit"] == 455.0
    assert ma_limit["front_protection_point"] == 455.0
    assert ma_limit["distance_to_ma"] == 155.0
    assert ma_limit["safe_distance"] == 165.0


def test_signal_evaluate_endpoint_reports_switch_locked_conflict():
    response = TestClient(app).post(
        "/api/v1/signal/evaluate",
        json={
            "train_states": [
                {
                    "vehicle_id": "TRAIN-003",
                    "position": 2435.0,
                    "speed": 25.0,
                    "route_id": "R_MAIN",
                }
            ],
            "route_requests": [
                {
                    "vehicle_id": "TRAIN-003",
                    "route_id": "R_BRANCH",
                }
            ],
        },
    )

    assert response.status_code == 200
    result = response.json()["route_results"][0]
    assert result["allowed"] is False
    assert result["reason"] == "switch_locked_conflict"
    assert result["required_position"] == "reverse"
    assert result["current_position"] == "normal"
    assert result["locked_by_route_id"] == "R_MAIN"


def test_build_signal_state_message_uses_protocol_fields():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            }
        ]
    )
    snapshot["timestamp"] = 1720000000.0
    snapshot["system_mode"] = "normal"

    message = build_signal_state_message(snapshot)

    assert message == {
        "type": "signal_state",
        "timestamp": 1720000000.0,
        "system_mode": "normal",
        "signals": snapshot["signals"],
        "sections": snapshot["sections"],
        "switches": snapshot["switches"],
        "route_results": snapshot["route_results"],
    }


def test_build_ma_state_message_uses_protocol_fields():
    snapshot = calculate_signal_snapshot(
        [
            {
                "vehicle_id": "TRAIN-001",
                "position": 300.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            }
        ]
    )
    snapshot["timestamp"] = 1720000000.0

    message = build_ma_state_message(snapshot)

    assert message == {
        "type": "ma_state",
        "timestamp": 1720000000.0,
        "ma_limits": snapshot["ma_limits"],
    }


def test_signal_zmq_adapter_start_subscribes_train_state():
    adapter = SignalZmqAdapter()
    fake_bus = FakeMessageBus()
    adapter.bus = fake_bus

    adapter.start()

    assert fake_bus.started is True
    assert fake_bus.subscriptions[0][0] == "train_state"


def test_signal_zmq_adapter_caches_train_state_with_default_route_id():
    adapter = SignalZmqAdapter()
    adapter.bus = FakeMessageBus()

    adapter.on_train_state(
        "train_state",
        {
            "vehicle_id": "TRAIN-001",
            "position": 300.0,
            "speed": 40.0,
        },
    )

    assert adapter.train_states_by_id["TRAIN-001"] == {
        "vehicle_id": "TRAIN-001",
        "position": 300.0,
        "speed": 40.0,
        "route_id": "R_MAIN",
    }


def test_signal_zmq_adapter_publishes_signal_state_and_ma_state_without_wrapping_fields():
    adapter = SignalZmqAdapter()
    fake_bus = FakeMessageBus()
    adapter.bus = fake_bus

    adapter.on_train_state(
        "train_state",
        {
            "vehicle_id": "TRAIN-001",
            "position": 300.0,
            "speed": 40.0,
            "route_id": "R_MAIN",
        },
    )

    topics = [topic for topic, _ in fake_bus.published]
    assert topics == ["signal_state", "ma_state", "ato_command"]

    signal_data = fake_bus.published[0][1]
    ma_data = fake_bus.published[1][1]
    ato_data = fake_bus.published[2][1]
    assert "type" not in signal_data
    assert "timestamp" not in signal_data
    assert "type" not in ma_data
    assert "timestamp" not in ma_data
    assert "type" not in ato_data
    assert "timestamp" not in ato_data
    assert {"system_mode", "signals", "sections", "switches", "route_results"} <= set(signal_data)
    assert set(ma_data) == {"ma_limits"}
    assert set(ato_data) == {"commands"}
