import sys
import time
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.data_flow.ato_guidance import PLC_FEEDBACK_FIELDS  # noqa: E402
from app.data_flow.state_store import DashboardStateStore  # noqa: E402


def _snapshot_train(
    *,
    driving_mode: str = "AM",
    control_source: str = "ato",
    ato_traction_level: int = 1,
    ato_brake_level: int = 0,
    applied_traction_level: int = 1,
    applied_brake_level: int = 0,
    door_closed: bool = True,
    emergency: bool = False,
    comm_ok: bool = True,
    driver_ato_active: bool = True,
):
    store = DashboardStateStore()
    now = time.time()
    store.update_comm(
        {
            "source": "driver_tcp",
            "driver_console_connected": comm_ok,
            "zmq_connected": comm_ok,
            "last_message_at": now,
        }
    )
    store.update_ma_limits(
        [
            {
                "vehicle_id": "TRAIN-001",
                "ma_limit": 500.0,
                "speed_limit": 60.0,
                "permission": "allow",
                "signal_state": "green",
            }
        ]
    )
    store.update_driver_input(
        "TRAIN-001",
        {
            "vehicle_id": "TRAIN-001",
            "direction": "forward",
            "direction_code": 1,
            "control_mode": "ato" if driving_mode == "AM" else "manual",
            "main_handle_raw": 1,
            "traction_level": 2,
            "brake_level": 0,
            "key_switch": True,
            "door_closed_light": door_closed,
            "emergency_button": emergency,
            "emergency_cmd": False,
            "parking_apply": False,
            "high_voltage_light": True,
            "brake_bad_light": False,
            "network_fault_light": False,
            "ato_capable": True,
            "ato_active": driver_ato_active,
            "auto_reverse_cap": False,
            "auto_reverse_active": False,
            "wash_mode_status": False,
        },
    )
    store.update_train(
        "TRAIN-001",
        {
            "vehicle_id": "TRAIN-001",
            "line_id": "LINE-1",
            "position": 100.0,
            "position_m": 100.0,
            "speed_kmh": 36.0,
            "speed_mps": 10.0,
            "acceleration": 0.1,
            "acceleration_mps2": 0.1,
            "direction": 1,
            "direction_code": 1,
            "mode": "ato" if driving_mode == "AM" else "manual",
            "driving_mode": driving_mode,
            "control_source": control_source,
            "ato_state": "approaching",
            "recommended_speed_kmh": 40.0,
            "ato_target_speed_kmh": 42.0,
            "ato_traction_level": ato_traction_level,
            "ato_brake_level": ato_brake_level,
            "commanded_traction_level": applied_traction_level,
            "commanded_brake_level": applied_brake_level,
            "applied_traction_level": applied_traction_level,
            "applied_brake_level": applied_brake_level,
            "atp_intervened": False,
            "emergency_brake": emergency,
            "doors_all_closed": door_closed,
            "door_closed_light": door_closed,
            "door_open_light": not door_closed,
            "high_voltage_on": True,
            "brake_bad_light": False,
            "ato_capable": True,
            "ato_active": driving_mode == "AM" and not emergency,
            "ma_limit": 500.0,
            "speed_limit": 60.0,
            "permission": "allow",
            "signal_state": "green",
        },
    )
    snapshot = store.get_snapshot().model_dump(mode="json")
    assert len(snapshot["trains"]) == 1
    return snapshot["trains"][0]


def test_am_guidance_is_control_and_plc_feedback_uses_supported_speed_field():
    train = _snapshot_train(driving_mode="AM", applied_traction_level=2)

    guidance = train["ato_guidance"]
    feedback = train["plc_feedback"]
    assert guidance["control_authority"] == "control"
    assert guidance["is_command_applied"] is True
    assert "ATO正在" in guidance["action_text"]
    assert feedback["ato_active"] is True
    assert feedback["vehicle_speed_kmh"] == 36.0
    assert set(feedback) == set(PLC_FEEDBACK_FIELDS)


def test_sm_guidance_is_advisory_and_never_outputs_traction_or_brake_to_plc():
    train = _snapshot_train(
        driving_mode="SM",
        control_source="manual",
        ato_traction_level=2,
        applied_traction_level=0,
    )

    guidance = train["ato_guidance"]
    feedback = train["plc_feedback"]
    assert guidance["control_authority"] == "advisory"
    assert guidance["is_command_applied"] is False
    assert "建议" in guidance["action_text"]
    assert guidance["suggested_traction_level"] == 2
    assert feedback["ato_active"] is False
    assert "traction_level" not in feedback
    assert "brake_level" not in feedback


def test_open_door_blocks_ato_precheck_and_sets_plc_door_lights():
    train = _snapshot_train(door_closed=False)

    guidance = train["ato_guidance"]
    feedback = train["plc_feedback"]
    assert guidance["precheck"]["can_start_ato"] is False
    assert guidance["precheck"]["checks"]["door_closed"] is False
    assert "请先关闭车门" in guidance["action_text"]
    assert feedback["door_closed_light"] is False
    assert feedback["door_open_light"] is True


def test_emergency_guidance_disables_plc_ato_active():
    train = _snapshot_train(emergency=True, applied_traction_level=0, applied_brake_level=4)

    guidance = train["ato_guidance"]
    feedback = train["plc_feedback"]
    assert guidance["recommended_action"] == "emergency"
    assert "紧急制动" in guidance["action_text"]
    assert feedback["ato_active"] is False


def test_comm_fault_blocks_precheck_and_sets_network_fault():
    train = _snapshot_train(comm_ok=False)

    guidance = train["ato_guidance"]
    feedback = train["plc_feedback"]
    assert guidance["precheck"]["checks"]["comm_ok"] is False
    assert "等待司机台/通信恢复" in guidance["action_text"]
    assert feedback["network_fault"] is True


def test_input_lights_and_output_lights_are_separated():
    train = _snapshot_train(driving_mode="AM", driver_ato_active=False)

    assert train["input_lights"]["ato_active"] is False
    assert train["output_lights"]["ato_active"] is True
    assert train["plc_feedback"] == train["output_lights"]
