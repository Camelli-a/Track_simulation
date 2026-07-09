import copy
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.signal_hardware_adapter import (  # noqa: E402
    BRAKE_COMMAND_CODE,
    TRACTION_COMMAND_CODE,
    build_hardware_signal_output,
    build_train_control_suggestion,
    map_signal_state_to_hardware_code,
    map_switch_position_to_hardware_code,
    map_switch_to_hardware_code,
    normalize_hardware_train_state,
)
from app.services.signal_control import calculate_signal_snapshot  # noqa: E402


def test_normalize_hardware_train_state_converts_704_fields():
    train_state = normalize_hardware_train_state(
        {
            "列车 ID": 1,
            "列车速度": 1000,
            "列车积累走行距离": 30000,
            "列车运行方向": 0x55,
            "列车载重": 5000,
            "故障限速": 500,
            "施加紧急制动": 1,
            "可用牵引数量": 4,
            "可用制动数量": 4,
        }
    )

    assert train_state["vehicle_id"] == "TRAIN-001"
    assert train_state["numeric_train_id"] == 1
    assert train_state["speed"] == 36.0
    assert train_state["position"] == 300.0
    assert train_state["direction"] == "up"
    assert train_state["direction_code"] == 0x55
    assert train_state["fault_speed_limit"] == 18.0
    assert train_state["emergency_brake"] is True
    assert train_state["load_kg"] == 5000.0
    assert train_state["traction_available_count"] == 4
    assert train_state["brake_available_count"] == 4


def test_normalize_hardware_train_state_maps_down_direction():
    train_state = normalize_hardware_train_state(
        {
            "train_id": "2",
            "speed_cm_s": "100",
            "distance_cm": "500",
            "direction_code": "0xaa",
        }
    )

    assert train_state["vehicle_id"] == "TRAIN-002"
    assert train_state["direction"] == "down"
    assert train_state["direction_code"] == 0xAA


def test_hardware_normalized_fault_speed_limit_participates():
    train_state = normalize_hardware_train_state(
        {
            "train_id": "1",
            "speed_cm_s": 1000,
            "distance_cm": 62000,
            "direction_code": 0x55,
            "fault_speed_limit_cm_s": 500,
        }
    )

    snapshot = calculate_signal_snapshot([train_state])
    ma_limit = snapshot["ma_limits"][0]

    assert train_state["fault_speed_limit"] == 18.0
    assert ma_limit["fault_speed_limit"] == 18.0
    assert ma_limit["speed_limit"] == 18.0
    assert ma_limit["speed_limit_reason"] == "fault_limit"


def test_map_switch_position_to_hardware_code():
    assert map_switch_position_to_hardware_code("normal") == 0x01
    assert map_switch_position_to_hardware_code("Reverse") == 0x02
    assert map_switch_position_to_hardware_code("fault") == 0x04
    assert map_switch_position_to_hardware_code(None) == 0x00


def test_hardware_adapter_maps_locked_normal_and_locked_reverse():
    assert (
        map_switch_to_hardware_code({"state": "locked_normal", "position": "normal"})
        == 0x01
    )
    assert (
        map_switch_to_hardware_code({"state": "locked_reverse", "position": "reverse"})
        == 0x02
    )


def test_hardware_adapter_maps_fault_and_four_open():
    assert map_switch_to_hardware_code({"state": "fault", "position": "normal"}) == 0x04
    assert (
        map_switch_to_hardware_code({"state": "four_open", "position": "reverse"})
        == 0x04
    )


def test_map_signal_state_to_hardware_code():
    assert map_signal_state_to_hardware_code("red") == 0x01
    assert map_signal_state_to_hardware_code("yellow") == 0x02
    assert map_signal_state_to_hardware_code("green") == 0x04
    assert map_signal_state_to_hardware_code("red_yellow") == 0x03


def test_build_train_control_suggestion_stop_brakes_100_percent():
    suggestion = build_train_control_suggestion(
        {
            "vehicle_id": "TRAIN-001",
            "permission": "stop",
            "current_speed": 20,
            "speed_limit": 0,
            "target_speed": 0,
        }
    )

    assert suggestion["command"] == "brake"
    assert suggestion["command_code"] == BRAKE_COMMAND_CODE
    assert suggestion["percent"] == 100
    assert suggestion["reason"] == "stop_permission"


def test_build_train_control_suggestion_restricted_overspeed_brakes():
    suggestion = build_train_control_suggestion(
        {
            "vehicle_id": "TRAIN-001",
            "permission": "restricted",
            "current_speed": 60,
            "speed_limit": 40,
            "target_speed": 40,
        }
    )

    assert suggestion["command"] == "brake"
    assert suggestion["command_code"] == BRAKE_COMMAND_CODE
    assert 20 <= suggestion["percent"] <= 80
    assert suggestion["reason"] == "overspeed_against_signal_limit"


def test_build_train_control_suggestion_allow_below_target_tractions():
    suggestion = build_train_control_suggestion(
        {
            "vehicle_id": "TRAIN-001",
            "permission": "allow",
            "current_speed": 40,
            "speed_limit": 80,
            "target_speed": 80,
        }
    )

    assert suggestion["command"] == "traction"
    assert suggestion["command_code"] == TRACTION_COMMAND_CODE
    assert 10 <= suggestion["percent"] <= 60
    assert suggestion["reason"] == "below_target_speed"


def test_build_train_control_suggestion_allow_at_target_coasts():
    suggestion = build_train_control_suggestion(
        {
            "vehicle_id": "TRAIN-001",
            "permission": "allow",
            "current_speed": 80,
            "speed_limit": 80,
            "target_speed": 80,
        }
    )

    assert suggestion["command"] == "coast"
    assert suggestion["command_code"] == 0x00
    assert suggestion["percent"] == 0


def test_build_hardware_signal_output_maps_snapshot_without_mutating_input():
    snapshot = {
        "switches": [
            {
                "switch_id": "SW-01",
                "position": "normal",
                "locked": True,
                "locked_by_route_id": "R_MAIN",
            }
        ],
        "signals": [
            {
                "signal_id": "SIG-01",
                "state": "yellow",
                "signal_state": "yellow",
                "route_id": "R_MAIN",
                "permission": "restricted",
            }
        ],
        "ma_limits": [
            {
                "vehicle_id": "TRAIN-001",
                "permission": "stop",
                "current_speed": 20,
                "speed_limit": 0,
                "target_speed": 0,
            }
        ],
    }
    original_snapshot = copy.deepcopy(snapshot)

    output = build_hardware_signal_output(snapshot)

    assert output["switch_states"][0]["hardware_code"] == 0x01
    assert output["switch_states"][0]["source_index"] == 1
    assert output["signal_states"][0]["hardware_code"] == 0x02
    assert output["signal_states"][0]["source_index"] is None
    assert output["train_control_suggestions"][0]["command_code"] == BRAKE_COMMAND_CODE
    assert snapshot == original_snapshot
