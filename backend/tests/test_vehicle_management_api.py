import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from main import app  # noqa: E402
from app.api.v1.endpoints import vehicle as vehicle_endpoint  # noqa: E402


def test_vehicle_manage_add_remove_clear_reset(monkeypatch):
    published = []

    def fake_publish(topic, data):
        published.append((topic, data))
        return True

    monkeypatch.setattr(vehicle_endpoint, "publish_module_message", fake_publish)
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
    assert len(data["trains"]) == 11
    assert published[-1] == (
        "add_train",
        {
            "vehicle_id": "TRAIN-011",
            "train_index": 11,
            "line_id": "LINE-1",
            "position": 1200.0,
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


def test_vehicle_trains_endpoint_reports_default_count():
    vehicle_endpoint.vehicle_manager.reset_trains(10)
    response = TestClient(app).get("/api/v1/vehicle/trains")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 10
    assert data["trains"][0]["vehicle_id"] == "TRAIN-001"
