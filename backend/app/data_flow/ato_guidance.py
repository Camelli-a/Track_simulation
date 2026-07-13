from __future__ import annotations

import math
from typing import Any, Mapping


PLC_FEEDBACK_FIELDS = (
    "vehicle_speed_kmh",
    "high_voltage_on",
    "brake_bad_light",
    "door_open_light",
    "door_closed_light",
    "network_fault",
    "auto_reverse_cap",
    "ato_capable",
    "wash_mode_status",
    "ato_active",
    "auto_reverse_active",
)


def _value(data: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if not data:
        return default
    value = data.get(key)
    return default if value is None else value


def _first_value(*items: tuple[Mapping[str, Any] | None, str], default: Any = None) -> Any:
    for data, key in items:
        value = _value(data, key)
        if value is not None:
            return value
    return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "allow", "active"}
    return bool(value)


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _speed_kmh(train_state: Mapping[str, Any] | None) -> float:
    explicit = _first_value(
        (train_state, "vehicle_speed_kmh"),
        (train_state, "speed_kmh"),
    )
    explicit_float = _as_float(explicit)
    if explicit_float is not None:
        return explicit_float
    speed_mps = _as_float(_first_value((train_state, "speed_mps"), (train_state, "speed_ms")))
    if speed_mps is not None:
        return speed_mps * 3.6
    return float(_as_float(_value(train_state, "speed"), 0.0) or 0.0)


def _speed_mps(train_state: Mapping[str, Any] | None) -> float:
    explicit = _as_float(_first_value((train_state, "speed_mps"), (train_state, "speed_ms")))
    if explicit is not None:
        return explicit
    return _speed_kmh(train_state) / 3.6


def _door_closed(driver_input: Mapping[str, Any] | None, train_state: Mapping[str, Any] | None) -> bool:
    value = _first_value(
        (driver_input, "door_closed_light"),
        (train_state, "doors_all_closed"),
        (train_state, "door_closed_light"),
        default=True,
    )
    return _as_bool(value, True)


def _comm_ok(comm_state: Mapping[str, Any] | None) -> bool:
    if not comm_state:
        return True
    return _as_bool(comm_state.get("driver_console_connected"), False) and _as_bool(
        comm_state.get("zmq_connected"), False
    )


def _ma_valid(
    train_state: Mapping[str, Any] | None,
    ma_state: Mapping[str, Any] | None,
) -> bool:
    explicit = _first_value((train_state, "ma_valid"), (ma_state, "ma_valid"))
    if explicit is not None:
        return _as_bool(explicit)

    ma_limit = _as_float(_first_value((ma_state, "ma_limit"), (train_state, "ma_limit")))
    speed_limit = _as_float(
        _first_value(
            (ma_state, "allowed_speed_kmh"),
            (ma_state, "speed_limit"),
            (train_state, "allowed_speed_kmh"),
            (train_state, "speed_limit"),
        )
    )
    permission = str(_first_value((ma_state, "permission"), (train_state, "permission"), default="unknown")).lower()
    signal_state = str(_first_value((ma_state, "signal_state"), (train_state, "signal_state"), default="unknown")).lower()

    permission_ok = permission in {"allow", "allowed", "restricted", "true", "1"}
    signal_ok = signal_state not in {"red", "stop", "forbidden", "deny", "denied"}
    return ma_limit is not None and speed_limit is not None and speed_limit > 0.0 and permission_ok and signal_ok


def build_input_lights(driver_input: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "high_voltage_light": _value(driver_input, "high_voltage_light"),
        "brake_bad_light": _value(driver_input, "brake_bad_light"),
        "door_closed_light": _value(driver_input, "door_closed_light"),
        "network_fault_light": _value(driver_input, "network_fault_light"),
        "ato_capable": _value(driver_input, "ato_capable"),
        "ato_active": _value(driver_input, "ato_active"),
        "auto_reverse_cap": _value(driver_input, "auto_reverse_cap"),
        "auto_reverse_active": _value(driver_input, "auto_reverse_active"),
        "wash_mode_status": _first_value((driver_input, "wash_mode_status"), (driver_input, "wash_mode_switch")),
    }


def build_ato_precheck(
    driver_input: Mapping[str, Any] | None,
    train_state: Mapping[str, Any] | None,
    ma_state: Mapping[str, Any] | None,
    comm_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    door_closed = _door_closed(driver_input, train_state)
    key_on = _as_bool(_value(driver_input, "key_switch"), True)

    direction = str(_first_value((driver_input, "direction"), (train_state, "direction_text"), default="forward")).lower()
    direction_code = _first_value((driver_input, "direction_code"), (train_state, "direction_code"))
    direction_selected = direction not in {"neutral", "none", "0"} and str(direction_code) not in {"0", "0.0"}

    parking_released = not _as_bool(_value(driver_input, "parking_apply"), False)
    parking_released = parking_released and str(_value(train_state, "control_source", "")).lower() != "parking_brake"
    parking_released = parking_released and not _as_bool(_value(train_state, "parking_brake"), False)

    not_emergency = not (
        _as_bool(_value(driver_input, "emergency_button"), False)
        or _as_bool(_value(driver_input, "emergency_cmd"), False)
        or _as_bool(_value(train_state, "emergency_brake"), False)
    )
    ma_valid = _ma_valid(train_state, ma_state)
    comm_ok = _comm_ok(comm_state)
    ato_capable_condition = all(
        (door_closed, key_on, direction_selected, parking_released, not_emergency, ma_valid, comm_ok)
    )
    checks = {
        "door_closed": door_closed,
        "key_on": key_on,
        "direction_selected": direction_selected,
        "parking_released": parking_released,
        "not_emergency": not_emergency,
        "ma_valid": ma_valid,
        "comm_ok": comm_ok,
        "ato_capable_condition": ato_capable_condition,
    }
    blocking_reasons: list[str] = []
    required_actions: list[str] = []
    if not door_closed:
        blocking_reasons.append("车门未关闭")
        required_actions.append("请先关闭车门，再启动ATO")
    if not key_on:
        blocking_reasons.append("钥匙开关未打开")
        required_actions.append("请打开钥匙开关")
    if not direction_selected:
        blocking_reasons.append("未选择方向")
        required_actions.append("请选择前进或后退方向")
    if not parking_released:
        blocking_reasons.append("停放制动未缓解")
        required_actions.append("请先缓解停放制动")
    if not not_emergency:
        blocking_reasons.append("紧急制动状态")
        required_actions.append("请解除紧急制动状态")
    if not ma_valid:
        blocking_reasons.append("MA或信号无效")
        required_actions.append("等待有效移动授权/信号开放")
    if not comm_ok:
        blocking_reasons.append("司机台或通信异常")
        required_actions.append("等待司机台/通信恢复")
    return {
        "can_start_ato": ato_capable_condition,
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "required_actions": required_actions,
    }


def _normal_action(
    *,
    is_am: bool,
    train_state: Mapping[str, Any] | None,
) -> tuple[str, str, str]:
    prefix = "ATO正在" if is_am else "建议"
    traction = int(_as_float(_first_value((train_state, "applied_traction_level"), (train_state, "ato_traction_level")), 0) or 0)
    brake = int(_as_float(_first_value((train_state, "applied_brake_level"), (train_state, "ato_brake_level")), 0) or 0)
    speed_mps = _speed_mps(train_state)
    distance_to_stop = _as_float(_first_value((train_state, "distance_to_stop"), (train_state, "distance_to_stop_m")))
    if speed_mps <= 0.2 and distance_to_stop is not None and abs(distance_to_stop) <= 1.0:
        return "hold", "hold", f"{prefix}停车保持"
    if brake > 0:
        return "brake", "brake", f"{prefix}制动{brake}级"
    if traction > 0:
        return "traction", "traction", f"{prefix}牵引{traction}级"
    return "coast", "coast", f"{prefix}巡航/惰行"


def _action_for_state(
    *,
    is_am: bool,
    driver_input: Mapping[str, Any] | None,
    train_state: Mapping[str, Any] | None,
    precheck: Mapping[str, Any],
) -> tuple[str, str, str]:
    checks = precheck.get("checks", {})
    prefix = "ATO正在" if is_am else "建议"
    if (
        _as_bool(_value(driver_input, "emergency_button"), False)
        or _as_bool(_value(driver_input, "emergency_cmd"), False)
        or _as_bool(_value(train_state, "emergency_brake"), False)
    ):
        return "emergency", "emergency", "紧急制动中，请解除紧急状态"
    if _as_bool(_value(train_state, "atp_intervened"), False):
        return "atp_brake", "emergency", "ATP介入制动，请等待速度降至安全范围"
    if not checks.get("door_closed", True):
        return "close_door", "degraded", "请先关闭车门，再启动ATO"
    if not checks.get("parking_released", True):
        return "release_parking", "degraded", "请先缓解停放制动"
    if not checks.get("ma_valid", True):
        return "wait_ma", "degraded", "等待有效移动授权/信号开放"
    if not checks.get("comm_ok", True):
        return "wait_comm", "degraded", "等待司机台/通信恢复"
    if str(_value(train_state, "control_source", "")).lower() == "degraded":
        return "degraded", "degraded", f"{prefix}降级制动/保持"
    return _normal_action(is_am=is_am, train_state=train_state)


def build_ato_guidance(
    driver_input: Mapping[str, Any] | None,
    train_state: Mapping[str, Any] | None,
    ma_state: Mapping[str, Any] | None,
    comm_state: Mapping[str, Any] | None,
    *,
    precheck: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    precheck_payload = dict(precheck or build_ato_precheck(driver_input, train_state, ma_state, comm_state))
    mode = str(_value(train_state, "driving_mode", _value(driver_input, "control_mode", "SM"))).upper()
    if mode == "ATO":
        mode = "AM"
    if mode == "MANUAL":
        mode = "SM"
    is_am = mode == "AM"
    recommended_action, current_phase, action_text = _action_for_state(
        is_am=is_am,
        driver_input=driver_input,
        train_state=train_state,
        precheck=precheck_payload,
    )
    return {
        "mode": "AM" if is_am else "SM",
        "control_authority": "control" if is_am else "advisory",
        "status_text": "ATO自动驾驶中" if is_am else "人工驾驶，ATO仅提供推荐",
        "current_phase": current_phase,
        "recommended_action": recommended_action,
        "action_text": action_text,
        "is_command_applied": is_am,
        "position_m": _as_float(_first_value((train_state, "position_m"), (train_state, "position"))),
        "speed_mps": _speed_mps(train_state),
        "speed_kmh": _speed_kmh(train_state),
        "acceleration_mps2": _as_float(_first_value((train_state, "acceleration_mps2"), (train_state, "acceleration"))),
        "recommended_speed_kmh": _as_float(_value(train_state, "recommended_speed_kmh")),
        "ato_target_speed_kmh": _as_float(_value(train_state, "ato_target_speed_kmh")),
        "stop_target_m": _as_float(_first_value((train_state, "stop_target"), (train_state, "stop_target_m"))),
        "distance_to_stop_m": _as_float(_first_value((train_state, "distance_to_stop"), (train_state, "distance_to_stop_m"))),
        "ato_traction_level": _value(train_state, "ato_traction_level", 0),
        "ato_brake_level": _value(train_state, "ato_brake_level", 0),
        "commanded_traction_level": _value(train_state, "commanded_traction_level", 0),
        "commanded_brake_level": _value(train_state, "commanded_brake_level", 0),
        "applied_traction_level": _value(train_state, "applied_traction_level", 0),
        "applied_brake_level": _value(train_state, "applied_brake_level", 0),
        "suggested_traction_level": _value(train_state, "ato_traction_level", 0),
        "suggested_brake_level": _value(train_state, "ato_brake_level", 0),
        "driver_actual_traction_level": _value(driver_input, "traction_level", 0),
        "driver_actual_brake_level": _value(driver_input, "brake_level", 0),
        "driver_actual_handle": _value(driver_input, "main_handle_raw"),
        "control_source": _value(train_state, "control_source"),
        "ato_state": _value(train_state, "ato_state"),
        "atp_intervened": _as_bool(_value(train_state, "atp_intervened"), False),
        "emergency_brake": _as_bool(_value(train_state, "emergency_brake"), False),
        "stop_result": _value(train_state, "stop_result"),
        "precheck": precheck_payload,
    }


def build_plc_feedback(
    driver_input: Mapping[str, Any] | None,
    train_state: Mapping[str, Any] | None,
    comm_state: Mapping[str, Any] | None,
    *,
    precheck: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    precheck_payload = dict(precheck or {})
    checks = precheck_payload.get("checks", {})
    door_closed = _door_closed(driver_input, train_state)
    control_source = str(_value(train_state, "control_source", "")).lower()
    driving_mode = str(_value(train_state, "driving_mode", "")).upper()
    emergency = _as_bool(_value(train_state, "emergency_brake"), False)
    network_fault = (not _comm_ok(comm_state)) or _as_bool(_value(train_state, "network_fault"), False)
    ato_active = (
        driving_mode == "AM"
        and control_source not in {"emergency", "degraded", "door_interlock", "parking_brake"}
        and not emergency
    )
    payload = {
        "vehicle_speed_kmh": _speed_kmh(train_state),
        "high_voltage_on": _as_bool(
            _first_value((train_state, "high_voltage_on"), (train_state, "high_voltage_light")),
            True,
        ),
        "brake_bad_light": _as_bool(_value(train_state, "brake_bad_light"), False),
        "door_open_light": not door_closed,
        "door_closed_light": door_closed,
        "network_fault": network_fault,
        "auto_reverse_cap": _as_bool(
            _first_value((train_state, "auto_reverse_cap"), (driver_input, "auto_reverse_cap")),
            False,
        ),
        "ato_capable": _as_bool(_value(train_state, "ato_capable"), False)
        or _as_bool(_value(driver_input, "ato_capable"), False)
        or _as_bool(checks.get("ato_capable_condition"), False),
        "wash_mode_status": _as_bool(
            _first_value((train_state, "wash_mode_status"), (driver_input, "wash_mode_status"), (driver_input, "wash_mode_switch")),
            False,
        ),
        "ato_active": ato_active,
        "auto_reverse_active": _as_bool(
            _first_value((train_state, "auto_reverse_active"), (driver_input, "auto_reverse_active")),
            False,
        ),
    }
    return {key: payload[key] for key in PLC_FEEDBACK_FIELDS}
