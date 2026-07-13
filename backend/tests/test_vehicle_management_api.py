import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from main import app  # noqa: E402
from app.api.v1.endpoints import vehicle as vehicle_endpoint  # noqa: E402
from app.data_flow.state_store import state_store  # noqa: E402
from app.services.station_demo_service import StationDemoConfig, StationDemoService  # noqa: E402


def test_vehicle_manage_add_remove_clear_reset(monkeypatch):
    published = []

    def fake_publish(topic, data):
        published.append((topic, data))
        return True

    monkeypatch.setattr(vehicle_endpoint, "publish_module_message", fake_publish)
    monkeypatch.setattr(
        vehicle_endpoint.vehicle_process_manager,
        "start_train",
        lambda **kwargs: {"enabled": True, "started": True, **kwargs},
    )
    monkeypatch.setattr(
        vehicle_endpoint.vehicle_process_manager,
        "stop_train",
        lambda vehicle_id: {"stopped": True, "vehicle_id": vehicle_id},
    )
    monkeypatch.setattr(
        vehicle_endpoint.vehicle_process_manager,
        "stop_all",
        lambda: {"stopped": 0, "results": []},
    )
    vehicle_endpoint.vehicle_manager.reset_trains(10)

    client = TestClient(app)

    response = client.post(
        "/api/v1/vehicle/manage",
        json={
            "type": "add_train",
            "vehicle_id": "TRAIN-011",
            "train_index": 11,
            "position": 1200.0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["result"]["vehicle_id"] == "TRAIN-011"
    assert data["result"]["train_index"] == 11
    assert data["result"]["control_policy"] == "non_001_added_to_onboard_ato_queue"
    assert len(data["trains"]) == 11
    assert published[-1] == (
        "add_train",
        {
            "vehicle_id": "TRAIN-011",
            "train_index": 11,
            "line_id": "LINE-1",
            "position": 313.0,
        },
    )

    response = client.post(
        "/api/v1/vehicle/manage",
        json={"type": "remove_train", "vehicle_id": "TRAIN-011"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert all(item["vehicle_id"] != "TRAIN-011" for item in data["trains"])

    response = client.post("/api/v1/vehicle/manage", json={"type": "clear_trains"})
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["trains"] == []

    response = client.post(
        "/api/v1/vehicle/manage",
        json={"type": "reset_trains", "count": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["result"]["count"] == 5
    assert len(data["trains"]) == 5


def test_vehicle_manage_train_001_remains_manual_management(monkeypatch):
    published = []

    monkeypatch.setattr(
        vehicle_endpoint,
        "publish_module_message",
        lambda topic, data: published.append((topic, data)) or True,
    )
    monkeypatch.setattr(
        vehicle_endpoint.vehicle_process_manager,
        "start_train",
        lambda **kwargs: {"enabled": True, "started": True, **kwargs},
    )
    vehicle_endpoint.vehicle_manager.clear_trains()

    client = TestClient(app)
    response = client.post(
        "/api/v1/vehicle/manage",
        json={
            "type": "add_train",
            "vehicle_id": "TRAIN-001",
            "train_index": 1,
            "position": 1200.0,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["result"]["vehicle_id"] == "TRAIN-001"
    assert "control_policy" not in data["result"]
    assert published[-1] == (
        "add_train",
        {
            "vehicle_id": "TRAIN-001",
            "train_index": 1,
            "line_id": "LINE-1",
            "position": 1200.0,
        },
    )


def test_vehicle_trains_endpoint_reports_default_count():
    vehicle_endpoint.vehicle_manager.reset_trains(10)
    response = TestClient(app).get("/api/v1/vehicle/trains")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 10
    assert data["trains"][0]["vehicle_id"] == "TRAIN-001"


def test_vehicle_manage_allows_more_than_udp_slot_count(monkeypatch):
    monkeypatch.setattr(vehicle_endpoint, "publish_module_message", lambda topic, data: True)
    monkeypatch.setattr(
        vehicle_endpoint.vehicle_process_manager,
        "start_train",
        lambda **kwargs: {"enabled": True, "started": True, **kwargs},
    )
    vehicle_endpoint.vehicle_manager.reset_trains(10)

    response = TestClient(app).post(
        "/api/v1/vehicle/manage",
        json={
            "type": "add_train",
            "vehicle_id": "TRAIN-021",
            "train_index": 21,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["result"]["vehicle_id"] == "TRAIN-021"
    assert data["result"]["train_index"] == 21
    assert any(item["vehicle_id"] == "TRAIN-021" for item in data["trains"])


def test_vehicle_manage_remove_prunes_dashboard_snapshot(monkeypatch):
    monkeypatch.setattr(vehicle_endpoint, "publish_module_message", lambda topic, data: True)
    monkeypatch.setattr(
        vehicle_endpoint.vehicle_process_manager,
        "start_train",
        lambda **kwargs: {"enabled": True, "started": True, **kwargs},
    )
    monkeypatch.setattr(
        vehicle_endpoint.vehicle_process_manager,
        "stop_train",
        lambda vehicle_id: {"stopped": True, "vehicle_id": vehicle_id},
    )
    vehicle_endpoint.vehicle_manager.clear_trains()

    client = TestClient(app)
    response = client.post(
        "/api/v1/vehicle/manage",
        json={"type": "add_train", "vehicle_id": "TRAIN-077", "train_index": 77},
    )
    assert response.status_code == 200

    state_store.update_train(
        "TRAIN-077",
        {
            "vehicle_id": "TRAIN-077",
            "train_index": 77,
            "position": 7700.0,
            "speed": 0.0,
        },
    )
    assert any(item.vehicle_id == "TRAIN-077" for item in state_store.get_snapshot().trains)

    response = client.post(
        "/api/v1/vehicle/manage",
        json={"type": "remove_train", "vehicle_id": "TRAIN-077"},
    )
    assert response.status_code == 200
    assert all(item.vehicle_id != "TRAIN-077" for item in state_store.get_snapshot().trains)


def test_station_demo_start_status_stop(monkeypatch):
    monkeypatch.setattr(vehicle_endpoint, "publish_module_message", lambda topic, data: True)
    monkeypatch.setattr(
        vehicle_endpoint.vehicle_process_manager,
        "start_train",
        lambda **kwargs: {"enabled": True, "started": True, **kwargs},
    )
    monkeypatch.setattr(
        vehicle_endpoint.vehicle_process_manager,
        "stop_train",
        lambda vehicle_id: {"stopped": True, "vehicle_id": vehicle_id},
    )
    vehicle_endpoint.vehicle_manager.clear_trains()

    client = TestClient(app)
    response = client.post(
        "/api/v1/vehicle/station-demo/start",
        json={
            "station_name": "FSP",
            "headway_sec": 5,
            "dwell_sec": 2,
            "max_active_trains": 1,
            "start_index": 80,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["active"] is True
    assert data["station"]["station_name"] == "FSP"

    response = client.get("/api/v1/vehicle/station-demo/status")
    assert response.status_code == 200
    assert response.json()["active"] is True

    response = client.post("/api/v1/vehicle/station-demo/stop")
    assert response.status_code == 200
    assert response.json()["active"] is False


def test_station_demo_uses_station_yard_coordinates_for_visual_projection():
    service = StationDemoService()
    station = service._resolve_station(StationDemoConfig(station_name="GTG"))

    assert station["station_id"] == "ST-13"
    assert station["demo_coordinate_source"] == "station-yard-v2"
    assert station["demo_stop_section_id"] == "9G"
    assert "6G-A" not in station["demo_route_section_ids"]
    assert "5G-A" in station["demo_route_section_ids"]
    assert "11G" in station["demo_route_section_ids"]
    assert station["demo_approach_position_m"] < station["demo_stop_position_m"] < station["demo_exit_position_m"]
    assert station["yard_start_m"] <= station["demo_approach_position_m"] <= station["yard_end_m"]
    assert station["yard_start_m"] <= station["demo_stop_position_m"] <= station["yard_end_m"]
    assert station["yard_start_m"] <= station["demo_exit_position_m"] <= station["yard_end_m"]
    assert station["demo_exit_position_m"] > station["demo_route_end_m"]
    assert station["demo_exit_position_m"] <= station["demo_visual_exit_end_m"]
    assert station["demo_stop_position_m"] > 30000.0


def test_station_demo_targets_onboard_ato_without_fallback(monkeypatch):
    published = []
    monkeypatch.setattr(
        "app.services.station_demo_service.publish_module_message",
        lambda topic, data: published.append((topic, data)) or True,
    )

    service = StationDemoService()
    service.station = service._resolve_station(StationDemoConfig(station_name="GTG"))
    service.config = StationDemoConfig(station_name="GTG")
    runtime = type(
        "Runtime",
        (),
        {
            "vehicle_id": "TRAIN-ATO",
            "phase": "approach",
            "station_position_m": service.station["demo_stop_position_m"],
            "last_command_at": 0.0,
        },
    )()

    service._ensure_onboard_ato_target(
        runtime,
        service.station["demo_stop_position_m"],
        100.0,
        force=True,
    )

    assert [topic for topic, _ in published] == ["set_train_state"]
    payload = published[0][1]
    assert payload["vehicle_id"] == "TRAIN-ATO"
    assert payload["driving_mode"] == "AM"
    assert payload["mode"] == "ato"
    assert payload["stop_target_m"] == service.station["demo_stop_position_m"]
    assert payload["reason"] == "station_demo_approach"


def test_station_demo_blocks_spawn_when_previous_train_is_too_close():
    service = StationDemoService()
    service.station = service._resolve_station(
        StationDemoConfig(station_name="GTG", headway_sec=5.0, min_train_spacing_m=350.0)
    )
    service.config = StationDemoConfig(station_name="GTG", headway_sec=5.0, min_train_spacing_m=350.0)
    service.active = True
    service._next_index = 500
    service._last_spawn_at = 0.0

    responses = []

    class Response:
        ok = True

    def manage(command):
        responses.append(command)
        return Response()

    service._manage_vehicle = manage
    service._spawn_if_needed(100.0)
    assert len(responses) == 1
    first_vehicle_id = responses[0].vehicle_id

    state_store.update_train(
        first_vehicle_id,
        {
            "vehicle_id": first_vehicle_id,
            "position": service.station["demo_approach_position_m"] + 40.0,
            "speed": 20.0,
        },
    )
    service._spawn_if_needed(106.0)

    assert len(responses) == 1


def test_station_demo_does_not_timeout_slow_arrival_before_station():
    service = StationDemoService()
    service.station = service._resolve_station(StationDemoConfig(station_name="GTG"))
    service.config = StationDemoConfig(station_name="GTG", cruise_speed_kmh=16.0)
    service.active = True

    removed = []
    service._manage_vehicle = lambda command: removed.append(command)
    runtime = service._trains["TRAIN-SLOW"] = type(
        "Runtime",
        (),
        {
            "vehicle_id": "TRAIN-SLOW",
            "train_index": 1,
            "phase": "approach",
            "station_position_m": service.station["demo_stop_position_m"],
            "approach_position_m": service.station["demo_approach_position_m"],
            "exit_position_m": service.station["demo_exit_position_m"],
            "created_at": time.time() - 300.0,
            "dwell_started_at": None,
            "last_command_at": 0.0,
        },
    )()

    assert runtime.phase == "approach"
    state_store.update_train(
        "TRAIN-SLOW",
        {
            "vehicle_id": "TRAIN-SLOW",
            "position": service.station["demo_approach_position_m"] + 300.0,
            "speed": 12.0,
        },
    )
    service._tick()

    assert "TRAIN-SLOW" in service._trains
    assert removed == []


def test_ma_station_identity_is_merged_into_train_snapshot():
    state_store.update_train(
        "TRAIN-STATION-MA",
        {
            "vehicle_id": "TRAIN-STATION-MA",
            "position": 100.0,
            "speed": 0.0,
        },
    )
    state_store.update_ma_limits(
        [
            {
                "vehicle_id": "TRAIN-STATION-MA",
                "station_id": "ST-13",
                "station_name": "GTG",
                "ma_limit": 500.0,
                "position": 100.0,
                "updated_at": 1.0,
            }
        ]
    )

    train = next(item for item in state_store.get_snapshot().trains if item.vehicle_id == "TRAIN-STATION-MA")
    assert train.station_id == "ST-13"
    assert train.station_name == "GTG"
