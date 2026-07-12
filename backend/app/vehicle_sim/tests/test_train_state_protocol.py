import pytest

from app.vehicle_sim.models import TrainState
from app.vehicle_sim.train_manager import TrainManager


def _state(**overrides):
    data = {
        "vehicle_id": "TRAIN-001",
        "line_id": "LINE-1",
        "position": 1234.5,
        "speed_ms": 16.67,
        "acceleration": 0.8,
        "mode": "manual",
        "is_running": True,
        "emergency_brake": False,
    }
    data.update(overrides)
    return TrainState(**data)


def test_train_state_protocol_contains_visualization_base_fields():
    protocol = _state(direction_code=1).to_protocol()

    assert protocol["vehicle_id"] == "TRAIN-001"
    assert protocol["line_id"] == "LINE-1"
    assert protocol["position"] == 1234.5
    assert protocol["position_m"] == 1234.5
    assert protocol["speed_mps"] == 16.67
    assert protocol["direction"] == 1


@pytest.mark.parametrize(
    ("direction_code", "expected_direction"),
    [
        (1, 1),
        (-1, -1),
        (2, -1),
        (0x55, 1),
        (0xAA, -1),
        (0, 1),
    ],
)
def test_train_state_protocol_direction_is_normalized(direction_code, expected_direction):
    protocol = _state(direction_code=direction_code).to_protocol()

    assert protocol["direction"] == expected_direction
    assert protocol["direction"] in {1, -1}
    assert protocol["direction"] not in {0x55, 0xAA}


def test_train_state_protocol_speed_aliases_are_consistent():
    protocol = _state(speed_ms=10.0).to_protocol()

    assert protocol["speed_ms"] == 10.0
    assert protocol["speed_mps"] == 10.0
    assert protocol["speed_kmh"] == 36.0
    assert protocol["speed"] == 36.0


def test_train_state_protocol_acceleration_alias_is_consistent():
    protocol = _state(acceleration=0.8).to_protocol()

    assert protocol["acceleration"] == 0.8
    assert protocol["acceleration_mps2"] == 0.8


def test_train_state_protocol_keeps_ato_control_fields():
    protocol = _state(
        ato_traction_level=1,
        ato_brake_level=0,
        commanded_traction_level=1,
        commanded_brake_level=0,
        applied_traction_level=0,
        applied_brake_level=4,
        control_source="emergency",
        atp_intervened=True,
        ato_brake_bias=1.3,
        ato_brake_bias_enabled=True,
        ato_brake_bias_adaptation_enabled=True,
        last_brake_bias_adjustment={"error_m": 0.4},
        brake_bias_history_size=1,
    ).to_protocol()

    for field in [
        "ato_traction_level",
        "ato_brake_level",
        "commanded_traction_level",
        "commanded_brake_level",
        "applied_traction_level",
        "applied_brake_level",
        "control_source",
        "atp_intervened",
        "ato_brake_bias",
        "ato_brake_bias_enabled",
        "ato_brake_bias_adaptation_enabled",
        "last_brake_bias_adjustment",
        "brake_bias_history_size",
    ]:
        assert field in protocol

    assert protocol["applied_brake_level"] == 4
    assert protocol["control_source"] == "emergency"
    assert protocol["atp_intervened"] is True
    assert protocol["ato_brake_bias"] == 1.3
    assert protocol["ato_brake_bias_enabled"] is True
    assert protocol["ato_brake_bias_adaptation_enabled"] is True
    assert protocol["last_brake_bias_adjustment"]["error_m"] == 0.4
    assert protocol["brake_bias_history_size"] == 1


def test_train_stop_result_protocol_contains_vehicle_and_unit_aliases():
    manager = TrainManager(initial_count=0)
    manager.add_train(vehicle_id="TRAIN-001", slot=1, position=1500.2)
    train = manager.get_train("TRAIN-001")
    train.state.speed_ms = 0.0
    train.next_stop_target_m = 1500.0

    train.step_tick(0.1)
    result = train.state.to_protocol()["stop_result"]

    assert result is not None
    assert result["vehicle_id"] == "TRAIN-001"
    assert "error_m" in result
    assert "error_cm" in result
    assert "qualified" in result
    assert "status" in result
    assert result["target_position_m"] == result["target_position"]
    assert result["actual_position_m"] == result["actual_position"]
    assert result["speed_mps"] == result["speed_ms"]


def test_single_train_step_all_protocol_has_visualization_and_ato_fields():
    manager = TrainManager(initial_count=0)
    manager.add_train(vehicle_id="TRAIN-002", slot=2, position=300.0)

    states = manager.step_all(0.1)

    assert len(states) == 1
    state = states[0]
    assert state["vehicle_id"] == "TRAIN-002"
    for field in [
        "position_m",
        "speed_mps",
        "direction",
        "line_id",
        "applied_traction_level",
        "applied_brake_level",
        "ato_brake_bias",
        "ato_brake_bias_enabled",
        "ato_brake_bias_adaptation_enabled",
        "last_brake_bias_adjustment",
        "brake_bias_history_size",
    ]:
        assert field in state
