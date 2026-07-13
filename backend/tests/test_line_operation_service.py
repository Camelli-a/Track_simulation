import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import line_operation_service as module  # noqa: E402
from app.services.line_operation_service import LineOperationConfig, LineOperationService  # noqa: E402


def _service() -> LineOperationService:
    service = LineOperationService()
    service.config = LineOperationConfig(headway_sec=3.0, max_active_trains=4)
    service._line = {"line_id": "LINE-1", "total_length_m": 1000.0}
    service._stations = [
        {"station_id": "ST-01", "station_name": "LEFT", "position": 0.0},
        {"station_id": "ST-02", "station_name": "MID", "position": 500.0},
        {"station_id": "ST-03", "station_name": "RIGHT", "position": 1000.0},
    ]
    return service


def test_line_operation_alternates_endpoint_departures(monkeypatch):
    service = _service()
    managed_commands = []
    published = []

    def manage(command):
        managed_commands.append(command)
        return SimpleNamespace(ok=True)

    monkeypatch.setattr(module, "publish_module_message", lambda topic, data: published.append((topic, data)) or True)
    monkeypatch.setattr(module.state_store, "get_snapshot", lambda: SimpleNamespace(trains=[]))
    service._manage_vehicle = manage

    service._spawn_if_needed(100.0)
    service._spawn_if_needed(104.0)

    assert [item.vehicle_id for item in managed_commands] == ["TRAIN-2000", "TRAIN-3000"]
    assert managed_commands[0].position == 0.0
    assert managed_commands[1].position == 1000.0
    assert published[0][1]["direction_code"] == 1
    assert published[0][1]["stop_target_m"] == 500.0
    assert published[1][1]["direction_code"] == -1
    assert published[1][1]["stop_target_m"] == 500.0
    assert published[0][1]["route_id"] == "LINE-UP"
    assert published[1][1]["route_id"] == "LINE-DOWN"


def test_line_operation_next_station_sequence_is_direction_aware():
    service = _service()

    assert service._resolve_next_station_index(100.0, "up") == 1
    assert service._resolve_next_station_index(900.0, "down") == 1
    assert service._resolve_next_station_index(999.0, "up") is None
    assert service._resolve_next_station_index(1.0, "down") is None


def test_endpoint_clear_uses_runtime_queue_before_state_store_updates(monkeypatch):
    service = _service()
    service._trains["TRAIN-2000"] = module.LineTrainRuntime(
        vehicle_id="TRAIN-2000",
        train_index=2000,
        direction="up",
        route_id="LINE-UP",
        start_position_m=0.0,
        target_station_index=1,
        created_at=100.0,
    )
    monkeypatch.setattr(module.state_store, "get_snapshot", lambda: SimpleNamespace(trains=[]))

    assert service._endpoint_clear("up") is False
    assert service._endpoint_clear("down") is True
