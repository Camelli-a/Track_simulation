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
from main import app  # noqa: E402


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

    section = next(item for item in snapshot["sections"] if item["section_id"] == "SEG-02")
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
    assert ma_limit["safe_distance"] == 120.0
    assert ma_limit["ma_limit"] == 500.0


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
                "position": 530.0,
                "speed": 40.0,
                "route_id": "R_MAIN",
            },
        ]
    )

    ma_limit = _ma_for(snapshot, "TRAIN-001")
    assert ma_limit["ma_limit"] == 410.0
    assert ma_limit["permission"] == "restricted"
    assert ma_limit["signal_state"] == "yellow"
    assert ma_limit["speed_limit"] == 30.0


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
    assert ma_limit["ma_limit"] == 380.0
    assert ma_limit["permission"] == "stop"
    assert ma_limit["signal_state"] == "red"
    assert ma_limit["speed_limit"] == 0.0


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
    assert ma_limit["ma_limit"] == 500.0
    assert ma_limit["safe_distance"] == 120.0


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
