from __future__ import annotations

from typing import Any, Dict


TRAIN_FIELD_MAPPING = {
    "id": "vehicle_id",
    "train_id": "vehicle_id",
    "vehicleId": "vehicle_id",
    "v": "speed",
    "velocity": "speed",
    "km_post": "position",
    "kilometerPost": "position",
    "positionM": "position",
    "position_m": "position",
    "pos": "position",
    "speedKmh": "speed",
    "speed_kmh": "speed",
    "speedMps": "speed",
    "speed_mps": "speed",
    "acc": "acceleration",
    "mileageCm": "mileage",
    "mileage": "mileage",
    "cumulativeMileage": "mileage",
    "distanceCm": "position",
    "trainIndex": "train_index",
    "trainNo": "train_index",
    "directionCode": "direction_code",
    "runDir": "direction_code",
    "activeCab": "active_cab",
    "activeTc": "active_cab",
    "activeEnd": "active_cab",
    "edgeId": "edge_id",
    "sectionId": "section_id",
    "stationId": "station_id",
    "trackId": "track_id",
    "edgeOffset": "edge_offset_m",
    "edgeOffsetM": "edge_offset_m",
    "edgeOffsetCm": "edge_offset_m",
    "trainLength": "train_length",
    "ctrlMode": "mode",
    "eb": "emergency_brake",
    "emergencyBrake": "emergency_brake",
    "faultSpeedLimit": "fault_speed_limit",
    "tractionLevel": "traction_level",
    "brakeLevel": "brake_level",
    "doorMode": "door_mode",
    "doorClosedLight": "door_closed_light",
    "highVoltageLight": "high_voltage_light",
    "brakeBadLight": "brake_bad_light",
    "networkFaultLight": "network_fault_light",
    "atoActive": "ato_active",
    "parkingApply": "parking_apply",
    "parkingRelease": "parking_release",
    "routeId": "route_id",
    "route": "route_id",
    "permissionState": "permission",
    "signal": "signal_state",
    "limitSpeed": "speed_limit",
    "limitSpeedKmh": "speed_limit",
    "limitSpeedMps": "speed_limit",
    "targetVelocity": "target_speed",
    "targetSpeedKmh": "target_speed",
    "targetSpeedMps": "target_speed",
    "energy": "energy_kwh",
    "energyKwh": "energy_kwh",
    "stopDistance": "stop_distance",
    "stationName": "station_name",
    "parkingPhase": "parking_phase",
    "stopErrorCm": "stop_error_cm",
    "platformId": "platform_id",
}

DRIVER_INPUT_FIELD_MAPPING = {
    "id": "vehicle_id",
    "train_id": "vehicle_id",
    "vehicleId": "vehicle_id",
    "handle": "traction_level",
    "traction": "traction_level",
    "brake": "brake_level",
    "mode": "control_mode",
    "controlMode": "control_mode",
    "emergency": "emergency_button",
    "emergencyButton": "emergency_button",
    "tractionLevel": "traction_level",
    "brakeLevel": "brake_level",
    "tractionPercent": "traction_percent",
    "brakePercent": "brake_percent",
    "actualTractionForceN": "actual_traction_force_n",
    "actualBrakeForceN": "actual_brake_force_n",
    "atpIntervention": "atp_intervention",
    "drivingMode": "driving_mode",
    "controlSource": "control_source",
    "atoCapable": "ato_capable",
    "autoReverseCap": "auto_reverse_cap",
    "autoReverseActive": "auto_reverse_active",
    "recommendedSpeedKmh": "recommended_speed_kmh",
    "parkingBrake": "parking_brake",
    "highVoltageOn": "high_voltage_on",
    "doorOpenLight": "door_open_light",
    "externalSpeedLimitKmh": "external_speed_limit_kmh",
    "activeFaults": "active_faults",
    "tractionPercent": "traction_percent",
    "brakePercent": "brake_percent",
    "mainHandleRaw": "main_handle_raw",
    "mainHandleState": "main_handle_raw",
    "keySwitch": "key_switch",
    "atoStartBtn": "ato_start_btn",
    "atoCapable": "ato_capable",
    "atoActive": "ato_active",
    "autoReverseCap": "auto_reverse_cap",
    "autoReverseActive": "auto_reverse_active",
    "autoRevFlag": "auto_rev_flag",
    "modeUpConfirm": "mode_up_confirm",
    "modeDnConfirm": "mode_dn_confirm",
    "vigilance": "vigilance",
    "vigilanceAllow": "vigilance_allow",
    "forcedRelease": "forced_release",
    "forcedPump": "forced_pump",
    "horn": "horn",
    "confirmFlag": "confirm_flag",
    "tracAuxReset": "trac_aux_reset",
    "washModeSwitch": "wash_mode_switch",
    "frameSeq": "frame_seq",
    "messageId": "message_id",
    "parkingApply": "parking_apply",
    "parkingRelease": "parking_release",
    "brakeBadLight": "brake_bad_light",
    "networkFaultLight": "network_fault_light",
    "openLeftDoor": "open_left_door",
    "openRightDoor": "open_right_door",
    "closeLeftDoor": "close_left_door",
    "closeRightDoor": "close_right_door",
    "doorMode": "door_mode",
    "doorClosedLight": "door_closed_light",
    "highVoltageLight": "high_voltage_light",
    "directionCode": "direction_code",
    "lineId": "line_id",
}

ATO_COMMAND_FIELD_MAPPING = {
    "id": "vehicle_id",
    "train_id": "vehicle_id",
    "vehicleId": "vehicle_id",
    "lineId": "line_id",
    "targetSpeed": "target_speed",
    "targetVelocity": "target_speed",
    "targetSpeedKmh": "target_speed",
    "targetSpeedMps": "target_speed",
    "targetPosition": "target_position",
    "traction": "traction_level",
    "brake": "brake_level",
}

MA_FIELD_MAPPING = {
    "id": "vehicle_id",
    "train_id": "vehicle_id",
    "vehicleId": "vehicle_id",
    "routeId": "route_id",
    "maLimit": "ma_limit",
    "maLimitCm": "ma_limit",
    "limit": "ma_limit",
    "signal": "signal_state",
    "limitSpeed": "speed_limit",
    "limitSpeedKmh": "speed_limit",
    "limitSpeedMps": "speed_limit",
    "targetSpeed": "target_speed",
    "targetVelocity": "target_speed",
    "targetSpeedKmh": "target_speed",
    "targetSpeedMps": "target_speed",
    "frontTrainId": "front_vehicle_id",
    "safeDistance": "safe_distance",
    "distanceToMa": "distance_to_ma",
    "distanceToMaCm": "distance_to_ma",
    "frontTrainLength": "front_train_length",
    "locationUncertainty": "location_uncertainty",
    "communicationMargin": "communication_margin",
    "safetyMargin": "safety_margin",
    "frontProtectionPoint": "front_protection_point",
    "frontProtectionPointCm": "front_protection_point",
    "currentSpeed": "current_speed",
    "currentSpeedKmh": "current_speed",
    "currentSpeedMps": "current_speed",
    "routeSpeedLimit": "route_speed_limit",
    "routeSpeedLimitKmh": "route_speed_limit",
    "routeSpeedLimitMps": "route_speed_limit",
    "requiredStopDistance": "required_stop_distance",
    "requiredStopDistanceCm": "required_stop_distance",
    "emergencyStopDistance": "emergency_stop_distance",
    "emergencyStopDistanceCm": "emergency_stop_distance",
    "warningDistance": "warning_distance",
    "warningDistanceCm": "warning_distance",
    "brakingCurveSpeedLimit": "braking_curve_speed_limit",
    "brakingModel": "braking_model",
}

SECTION_FIELD_MAPPING = {
    "segment_id": "section_id",
    "sectionId": "section_id",
    "lineId": "line_id",
    "from": "start",
    "fromCm": "start",
    "to": "end",
    "toCm": "end",
    "trackSegId": "track_seg_id",
    "trackId": "track_id",
    "occupiedBy": "vehicle_id",
    "occupied_by": "occupied_by",
    "lockedByRouteId": "locked_by_route_id",
    "speedLimit": "speed_limit",
    "speedLimitKmh": "speed_limit",
    "speedLimitMps": "speed_limit",
    "stationId": "station_id",
    "stopPosition": "stop_position",
    "stopPositionCm": "stop_position",
    "receivedAt": "received_at",
    "staleAfterSeconds": "stale_after_seconds",
}

SIGNAL_FIELD_MAPPING = {
    "id": "signal_id",
    "signalId": "signal_id",
    "routeId": "route_id",
    "signalState": "signal_state",
    "colorCode": "color_code",
    "stationId": "station_id",
    "trackId": "track_id",
    "sectionId": "section_id",
    "positionM": "position",
    "positionCm": "position",
    "type": "signal_type",
    "signalType": "signal_type",
    "protectsSwitchId": "protects_switch_id",
    "protectsSectionId": "protects_section_id",
    "receivedAt": "received_at",
    "staleAfterSeconds": "stale_after_seconds",
}

SWITCH_FIELD_MAPPING = {
    "id": "switch_id",
    "switchId": "switch_id",
    "turnoutId": "turnout_id",
    "stationId": "station_id",
    "switchType": "switch_type",
    "normalTo": "normal_to",
    "reverseTo": "reverse_to",
    "routing": "routing",
    "state": "state",
    "lockedByRouteId": "locked_by_route_id",
    "relatedSection": "related_section",
    "receivedAt": "received_at",
    "staleAfterSeconds": "stale_after_seconds",
}

POWER_FIELD_MAPPING = {
    "u": "voltage",
    "voltageV": "voltage",
    "voltageKv": "voltage",
    "i": "current",
    "currentA": "current",
    "currentKa": "current",
    "p": "power",
    "powerKw": "power",
    "powerMw": "power",
    "fault": "is_fault",
    "substation": "substation_id",
    "substationId": "substation_id",
    "receivedAt": "received_at",
    "staleAfterSeconds": "stale_after_seconds",
}

ROUTE_REQUEST_FIELD_MAPPING = {
    "id": "request_id",
    "requestId": "request_id",
    "train_id": "vehicle_id",
    "vehicleId": "vehicle_id",
    "routeId": "route_id",
    "originSectionId": "origin_section_id",
    "fromSection": "origin_section_id",
    "destinationSectionId": "destination_section_id",
    "toSection": "destination_section_id",
    "startPosition": "start_position",
    "fromPosition": "start_position",
    "endPosition": "end_position",
    "toPosition": "end_position",
}


def normalize_fields(data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Return a copy with known aliases converted to protocol field names."""

    normalized: Dict[str, Any] = {}
    for key, value in data.items():
        normalized[mapping.get(key, key)] = value
    return normalized


def _as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _set_converted(
    normalized: Dict[str, Any],
    field: str,
    value: Any,
    factor: float,
) -> None:
    number = _as_number(value)
    if number is not None:
        normalized[field] = number * factor


def normalize_train(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, TRAIN_FIELD_MAPPING)
    for key in ("km_post", "kilometerPost"):
        if key in data:
            _set_converted(normalized, "position", data[key], 1000.0)
    for key in ("mileageCm", "distanceCm", "edgeOffsetCm"):
        if key in data:
            target = "edge_offset_m" if key == "edgeOffsetCm" else TRAIN_FIELD_MAPPING[key]
            _set_converted(normalized, target, data[key], 0.01)
    for key in ("speedMps", "speed_mps", "limitSpeedMps", "targetSpeedMps"):
        if key in data:
            target = TRAIN_FIELD_MAPPING[key]
            _set_converted(normalized, target, data[key], 3.6)
    return normalized


def normalize_driver_input(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, DRIVER_INPUT_FIELD_MAPPING)
    if "traction_level" in normalized:
        normalized["traction_level"] = max(0, min(int(normalized["traction_level"]), 4))
    if "brake_level" in normalized:
        normalized["brake_level"] = max(0, min(int(normalized["brake_level"]), 7))
    return normalized


def normalize_ato_command(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, ATO_COMMAND_FIELD_MAPPING)
    if "targetSpeedMps" in data:
        _set_converted(normalized, "target_speed", data["targetSpeedMps"], 3.6)
    return normalized


def normalize_ma(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, MA_FIELD_MAPPING)
    for key in (
        "maLimitCm",
        "distanceToMaCm",
        "frontProtectionPointCm",
        "requiredStopDistanceCm",
        "emergencyStopDistanceCm",
        "warningDistanceCm",
    ):
        if key in data:
            _set_converted(normalized, MA_FIELD_MAPPING[key], data[key], 0.01)
    for key in ("limitSpeedMps", "targetSpeedMps", "currentSpeedMps", "routeSpeedLimitMps"):
        if key in data:
            _set_converted(normalized, MA_FIELD_MAPPING[key], data[key], 3.6)
    return normalized


def normalize_section(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, SECTION_FIELD_MAPPING)
    for key in ("fromCm", "toCm", "stopPositionCm"):
        if key in data:
            _set_converted(normalized, SECTION_FIELD_MAPPING[key], data[key], 0.01)
    if "speedLimitMps" in data:
        _set_converted(normalized, "speed_limit", data["speedLimitMps"], 3.6)
    if "occupied_by" not in normalized and "vehicle_id" in normalized:
        normalized["occupied_by"] = normalized["vehicle_id"]
    if "vehicle_id" not in normalized and "occupied_by" in normalized:
        normalized["vehicle_id"] = normalized["occupied_by"]
    if "aspect" not in normalized:
        normalized["aspect"] = "red" if normalized.get("occupied") else "green"
    return normalized


def normalize_signal(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, SIGNAL_FIELD_MAPPING)
    if "positionCm" in data:
        _set_converted(normalized, "position", data["positionCm"], 0.01)
    if "state" not in normalized and "signal_state" in normalized:
        normalized["state"] = normalized["signal_state"]
    if "signal_state" not in normalized and "state" in normalized:
        normalized["signal_state"] = normalized["state"]
    return normalized


def normalize_switch(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, SWITCH_FIELD_MAPPING)
    route_state = normalized.get("routing") or normalized.get("state") or normalized.get("position")
    if route_state:
        normalized["position"] = route_state
        normalized["routing"] = route_state
        normalized["state"] = route_state
    if "turnout_id" not in normalized and "switch_id" in normalized:
        normalized["turnout_id"] = normalized["switch_id"]
    return normalized


def normalize_power(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, POWER_FIELD_MAPPING)
    if "voltageKv" in data:
        _set_converted(normalized, "voltage", data["voltageKv"], 1000.0)
    if "currentKa" in data:
        _set_converted(normalized, "current", data["currentKa"], 1000.0)
    if "powerMw" in data:
        _set_converted(normalized, "power", data["powerMw"], 1000.0)
    return normalized


def normalize_route_request(data: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_fields(data, ROUTE_REQUEST_FIELD_MAPPING)
