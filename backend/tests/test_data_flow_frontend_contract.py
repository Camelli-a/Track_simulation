import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.data_flow.mock_service import MockDashboardService  # noqa: E402
from app.data_flow.state_store import DashboardStateStore  # noqa: E402
from main import app  # noqa: E402


def test_dashboard_snapshot_exposes_frontend_page_contract():
    response = TestClient(app).get("/api/v1/dashboard/snapshot")

    assert response.status_code == 200
    data = response.json()
    assert data["integration"]["integration_mode"] in {"simulation", "realtime", "hybrid", "degraded"}
    assert data["integration"]["realtime_channel"] == "websocket"
    assert data["scenarios"]

    ma_shrink = next(item for item in data["scenarios"] if item["scenario_id"] == "ma_shrink")
    assert ma_shrink["page_config"]["primary_chart"] == "speed_distance"
    assert "ma_status" in ma_shrink["page_config"]["panels"]
    assert "atp_triggered" in ma_shrink["page_config"]["key_metrics"]

    assert data["trains"]
    train = data["trains"][0]
    assert train["section_id"]
    assert "track_id" in train
    assert "station_id" in train

    assert data["sections"]
    section = data["sections"][0]
    assert "track_id" in section
    assert "station_id" in section


def test_scenarios_endpoint_returns_named_page_config():
    client = TestClient(app)

    response = client.get("/api/v1/dashboard/scenarios/manual_overspeed_atp")

    assert response.status_code == 200
    data = response.json()
    assert data["scenario_id"] == "manual_overspeed_atp"
    assert data["page_config"]["secondary_chart"] == "driver_input_timeline"
    assert data["page_config"]["panels"] == [
        "driver_input",
        "recommended_speed",
        "atp_status",
        "stop_result",
    ]


def test_scene_state_endpoint_returns_active_scene_and_vehicle_scene_map():
    response = TestClient(app).get("/api/v1/dashboard/scene-state")

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "dashboard_scene_state"
    assert data["active_scene"]["scenario_id"]
    assert "scope" in data["active_scene"]
    assert isinstance(data["vehicle_scene_map"], list)
    assert data["vehicle_scene_map"]
    first_vehicle_scene = data["vehicle_scene_map"][0]
    assert first_vehicle_scene["vehicle_id"]
    assert first_vehicle_scene["scenario_id"]
    assert isinstance(first_vehicle_scene["key_metrics"], list)
    assert isinstance(first_vehicle_scene["highlight_events"], list)


def test_station_yards_endpoint_returns_static_layout_for_rendering():
    response = TestClient(app).get("/api/v1/dashboard/stations/yards")

    assert response.status_code == 200
    data = response.json()
    assert data["line_id"] == "LINE-1"
    assert len(data["stations"]) >= 2

    station = data["stations"][0]
    assert station["station_id"]
    assert station["track_ids"]
    assert station["switch_ids"]
    assert station["signal_ids"]
    assert station["section_ids"]

    track = data["yard_tracks"][0]
    assert {"track_id", "track_name", "station_id", "track_type", "direction", "section_ids"} <= set(track)
    assert track["geometry"]["type"] == "polyline"
    assert track["geometry"]["points"]

    switch = data["yard_switches"][0]
    assert switch["connects"]
    assert switch["approach_track_id"]
    assert switch["normal_to"]
    assert switch["reverse_to"]
    assert switch["active_to"]
    assert switch["branch_geometries"]
    first_branch = switch["branch_geometries"][0]
    assert first_branch["from_track_id"]
    assert first_branch["to_track_id"]
    assert first_branch["geometry"]["type"] == "polyline"
    assert first_branch["geometry"]["points"]

    signal = data["yard_signals"][0]
    assert signal["track_id"]
    assert signal["protects_switch_id"] or signal["protects_section_id"]


def test_dashboard_snapshot_switches_expose_active_branch():
    response = TestClient(app).get("/api/v1/dashboard/snapshot")

    assert response.status_code == 200
    data = response.json()
    assert data["switches"]
    switch = data["switches"][0]
    assert "active_to" in switch


def test_state_store_can_backfill_train_topology_from_sections():
    store = DashboardStateStore()
    now = 1000.0

    store.update_track_info(
        {
            "line_id": "LINE-1",
            "sections": [
                {
                    "section_id": "SEG-01",
                    "track_seg_id": "T01",
                    "track_id": "STA-01-T1",
                    "station_id": "STA-01",
                    "start": 0.0,
                    "end": 500.0,
                }
            ],
        }
    )
    store.update_signal_state(
        {
            "sections": [
                {
                    "section_id": "SEG-01",
                    "track_id": "STA-01-T1",
                    "station_id": "STA-01",
                    "start": 0.0,
                    "end": 500.0,
                    "occupied": True,
                    "occupied_by": "TRAIN-001",
                }
            ]
        }
    )
    store.update_train(
        "TRAIN-001",
        {
            "vehicle_id": "TRAIN-001",
            "position": 120.0,
            "speed": 32.0,
            "mode": "manual",
            "updated_at": now,
        },
    )

    snapshot = store.get_snapshot()
    train = next(item for item in snapshot.trains if item.vehicle_id == "TRAIN-001")
    assert train.section_id == "SEG-01"
    assert train.track_id == "STA-01-T1"
    assert train.station_id == "STA-01"


def test_mock_dashboard_service_throttles_duplicate_ticks(monkeypatch: pytest.MonkeyPatch):
    store = DashboardStateStore()
    service = MockDashboardService(store)
    base_time = 1000.0
    service.start_time = base_time - 10.0

    monkeypatch.setattr("app.data_flow.mock_service.time.time", lambda: base_time)
    assert service.tick() is True
    first_snapshot = store.get_snapshot()
    first_position = first_snapshot.trains[0].position

    monkeypatch.setattr("app.data_flow.mock_service.time.time", lambda: base_time + 0.05)
    assert service.tick() is False
    second_snapshot = store.get_snapshot()
    second_position = second_snapshot.trains[0].position

    monkeypatch.setattr("app.data_flow.mock_service.time.time", lambda: base_time + 0.25)
    assert service.tick() is True
    third_snapshot = store.get_snapshot()
    third_position = third_snapshot.trains[0].position

    assert second_position == first_position
    assert third_position > second_position


def test_state_store_scene_state_marks_vehicle_emergency_as_atp_scene():
    store = DashboardStateStore()
    now = 1000.0
    store.update_train(
        "TRAIN-001",
        {
            "vehicle_id": "TRAIN-001",
            "position": 1200.0,
            "speed": 0.0,
            "mode": "manual",
            "emergency_brake": True,
            "updated_at": now,
        },
    )
    scene_state = store.get_scene_state()

    assert scene_state.active_scene.scenario_id == "manual_overspeed_atp"
    assert scene_state.active_scene.target_vehicle_id == "TRAIN-001"
    vehicle_scene = next(item for item in scene_state.vehicle_scene_map if item.vehicle_id == "TRAIN-001")
    assert vehicle_scene.scenario_id == "manual_overspeed_atp"
