import time

from app.vehicle_sim.models import CommState, DriverInput, PowerState
from app.vehicle_sim.train_manager import TrainManager


def _train():
    return TrainManager(initial_count=1).get_train("TRAIN-001")


def _feedback(**overrides):
    values = {
        "vehicle_id": "TRAIN-001",
        "line_id": "LINE-1",
        "source": "plc",
        "control_mode": "manual",
        "traction_level": 0,
        "brake_level": 0,
        "direction": "forward",
        "emergency_button": False,
    }
    values.update(overrides)
    return DriverInput(**values)


def test_high_voltage_feedback_cannot_override_power_module():
    train = _train()
    train.apply_power_state(
        PowerState(
            substation_id="SS-01",
            voltage=0.0,
            current=0.0,
            power=0.0,
            is_fault=True,
        )
    )
    train.step_manual(_feedback(high_voltage_light=True), 0.1)

    assert train.hardware_high_voltage_light is True
    assert train.power_fault is True
    assert train.power_factor == 0.0
    assert train.state.high_voltage_light is False


def test_network_lamp_feedback_cannot_override_comm_state():
    train = _train()
    train.apply_comm_state(
        CommState(
            source="driver_console",
            driver_console_connected=False,
            zmq_connected=True,
            last_message_at=0.0,
        )
    )
    train.step_manual(_feedback(network_fault_light=False), 0.1)

    assert train.hardware_network_fault_light is False
    assert train.comm_ok is False
    assert "network_fault_light" not in train.state.to_protocol()


def test_brake_bad_feedback_is_diagnostic_only():
    train = _train()
    train.step_manual(_feedback(brake_bad_light=True), 0.1)

    assert train.hardware_brake_bad_light is True
    assert train.brake_fault is False
    assert train.state.brake_bad_light is False
    assert train.requested_brake_level == 0
    assert train.requested_brake_percent == 0.0


def test_indicator_feedback_mismatches_are_reported_without_control_effect():
    train = _train()
    train.step_manual(
        _feedback(
            high_voltage_light=False,
            brake_bad_light=True,
            door_closed_light=False,
            network_fault_light=True,
        ),
        0.1,
    )

    mismatches = train.get_indicator_feedback_mismatches()
    assert mismatches == {
        "high_voltage_light": {"commanded": True, "feedback": False},
        "brake_bad_light": {"commanded": False, "feedback": True},
        "door_closed_light": {"commanded": True, "feedback": False},
    }


def test_protocol_lamps_are_derived_from_business_state():
    train = _train()
    train.apply_power_state(
        PowerState("SS-01", voltage=1500.0, current=0.0, power=0.0, is_fault=False)
    )
    train.apply_comm_state(
        CommState("driver_console", True, True, last_message_at=time.time())
    )

    state = train.state.to_protocol()
    assert state["high_voltage_light"] is True
    assert state["brake_bad_light"] is False
    assert state["door_closed_light"] is True
    assert "network_fault_light" not in state
