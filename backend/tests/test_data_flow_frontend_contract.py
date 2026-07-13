import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from main import app  # noqa: E402
from app.core.config import settings  # noqa: E402


def test_dashboard_snapshot_exposes_frontend_page_contract():
    response = TestClient(app).get("/api/v1/dashboard/snapshot")

    assert response.status_code == 200
    data = response.json()
    assert data["integration"]["integration_mode"] in {"simulation", "realtime", "hybrid", "degraded"}
    assert data["integration"]["realtime_channel"] == "websocket"
    assert data["system"]["data_source"] == "zmq"
    assert settings.ENABLE_DASHBOARD_MOCK is False
    assert data["scenarios"]

    ma_shrink = next(item for item in data["scenarios"] if item["scenario_id"] == "ma_shrink")
    assert ma_shrink["page_config"]["primary_chart"] == "speed_distance"
    assert "ma_status" in ma_shrink["page_config"]["panels"]
    assert "atp_triggered" in ma_shrink["page_config"]["key_metrics"]


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


def test_scene_state_endpoint_returns_runtime_scene_contract():
    response = TestClient(app).get("/api/v1/dashboard/scene-state")

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "dashboard_scene_state"
    assert data["active_scene"]["scenario_id"]
    assert "key_metrics" in data["active_scene"]
    assert "highlight_events" in data["active_scene"]
    assert isinstance(data["vehicle_scene_map"], list)


def test_station_yards_endpoint_returns_static_layout_for_rendering():
    response = TestClient(app).get("/api/v1/dashboard/stations/yards")

    assert response.status_code == 200
    data = response.json()
    assert data["line_id"] == "LINE-1"
    assert len(data["stations"]) >= 13
    assert [station["station_name"] for station in data["stations"][:13]] == [
        "GGZ",
        "FSP",
        "KYL",
        "FTN",
        "FTD",
        "QLZ",
        "LLQ",
        "LLE",
        "BWR",
        "JBG",
        "BDZ",
        "BQS",
        "GTG",
    ]

    station = data["stations"][0]
    assert station["station_id"]
    assert station["track_ids"]
    assert station["signal_ids"]
    assert station["section_ids"]
    assert data["yard_switches"]
    assert data["yard_signals"]

    track = data["yard_tracks"][0]
    assert {"track_id", "track_name", "station_id", "track_type", "direction", "section_ids"} <= set(track)
    assert track["geometry"]["type"] == "polyline"
    assert track["geometry"]["points"]

    switch = data["yard_switches"][0]
    assert switch["connects"]
    assert switch["normal_to"]
    assert switch["reverse_to"]

    signal = data["yard_signals"][0]
    assert signal["track_id"]
    assert signal["protects_switch_id"] or signal["protects_section_id"]
