import pytest

from app.vehicle_sim.models import DriverInput
from app.vehicle_sim.train_manager import TrainManager


def _train():
    return TrainManager(initial_count=1).get_train("TRAIN-001")


def _manual(**overrides):
    values = {
        "vehicle_id": "TRAIN-001",
        "line_id": "LINE-1",
        "source": "test",
        "control_mode": "manual",
        "traction_level": 0,
        "brake_level": 0,
        "direction": "forward",
        "emergency_button": False,
    }
    values.update(overrides)
    return DriverInput(**values)


def test_train_state_exposes_explicit_si_and_dashboard_units():
    train = _train()
    train.state.position = 123.45
    train.state.speed_ms = 8.25
    train.state.acceleration = -0.42

    state = train.state.to_protocol()
    assert state["position_m"] == 123.45
    assert state["speed_mps"] == 8.25
    assert state["speed_kmh"] == pytest.approx(29.7)
    assert state["vehicle_speed_kmh"] == pytest.approx(29.7)
    assert state["acceleration_mps2"] == -0.42
    assert not any(key.endswith("_cm") or key.endswith("_cmps") for key in state)


def test_train_state_exposes_final_applied_control_and_force():
    train = _train()
    train.step_manual(
        _manual(traction_level=2, traction_percent=50.0), 0.1
    )
    train.step_tick(0.1)

    state = train.state.to_protocol()
    assert state["traction_level"] == 2
    assert state["traction_percent"] == 50.0
    assert state["brake_percent"] == 0.0
    assert state["actual_traction_force_n"] > 0.0
    assert state["actual_brake_force_n"] == 0.0
    assert state["control_mode"] == "manual"
    assert state["control_source"] == "manual"


def test_atp_override_is_reflected_as_final_applied_control():
    train = _train()
    train.comm_ok = False
    train.state.speed_ms = 5.0
    train.step_manual(
        _manual(traction_level=4, traction_percent=100.0), 0.1
    )
    train.step_tick(0.1)

    state = train.state.to_protocol()
    assert state["emergency_brake"] is True
    assert state["atp_intervention"] is True
    assert state["traction_percent"] == 0.0
    assert state["brake_percent"] == 100.0
    assert state["actual_brake_force_n"] > 0.0


def test_operational_and_door_fields_are_published():
    train = _train()
    train.ato_capable = True
    train.auto_reverse_capable = True
    train.recommended_speed_kmh = 25.0
    train.parking_brake_applied = True
    train._sync_public_state()

    state = train.state.to_protocol()
    assert state["ato_capable"] is True
    assert state["auto_reverse_cap"] is True
    assert state["recommended_speed_kmh"] == 25.0
    assert state["parking_brake"] is True
    assert state["high_voltage_on"] is True
    assert state["door_open_light"] is False


def test_network_fault_output_belongs_to_communication_module():
    train = _train()
    train.comm_ok = False
    train.hardware_network_fault_light = True

    state = train.state.to_protocol()
    assert "network_fault" not in state
    assert "network_fault_light" not in state
