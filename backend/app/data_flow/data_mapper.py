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
    "pos": "position",
    "acc": "acceleration",
    "ctrlMode": "mode",
    "eb": "emergency_brake",
    "routeId": "route_id",
    "route": "route_id",
    "permissionState": "permission",
    "signal": "signal_state",
    "limitSpeed": "speed_limit",
    "targetVelocity": "target_speed",
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
    "emergency": "emergency_button",
    "lineId": "line_id",
}

ATO_COMMAND_FIELD_MAPPING = {
    "id": "vehicle_id",
    "train_id": "vehicle_id",
    "vehicleId": "vehicle_id",
    "lineId": "line_id",
    "targetSpeed": "target_speed",
    "targetVelocity": "target_speed",
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
    "limit": "ma_limit",
    "signal": "signal_state",
    "limitSpeed": "speed_limit",
    "targetSpeed": "target_speed",
    "targetVelocity": "target_speed",
    "frontTrainId": "front_vehicle_id",
    "safeDistance": "safe_distance",
}

SECTION_FIELD_MAPPING = {
    "segment_id": "section_id",
    "lineId": "line_id",
    "from": "start",
    "to": "end",
    "trackSegId": "track_seg_id",
    "occupiedBy": "vehicle_id",
    "occupied_by": "occupied_by",
    "lockedByRouteId": "locked_by_route_id",
    "speedLimit": "speed_limit",
    "stationId": "station_id",
    "stopPosition": "stop_position",
}

SIGNAL_FIELD_MAPPING = {
    "id": "signal_id",
    "routeId": "route_id",
    "signalState": "signal_state",
    "type": "signal_type",
    "signalType": "signal_type",
}

SWITCH_FIELD_MAPPING = {
    "id": "switch_id",
    "turnoutId": "turnout_id",
    "routing": "routing",
    "state": "state",
    "lockedByRouteId": "locked_by_route_id",
    "relatedSection": "related_section",
}

POWER_FIELD_MAPPING = {
    "u": "voltage",
    "i": "current",
    "p": "power",
    "fault": "is_fault",
    "substation": "substation_id",
}


def normalize_fields(data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Return a copy with known aliases converted to protocol field names."""

    normalized: Dict[str, Any] = {}
    for key, value in data.items():
        normalized[mapping.get(key, key)] = value
    return normalized


def normalize_train(data: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_fields(data, TRAIN_FIELD_MAPPING)


def normalize_driver_input(data: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_fields(data, DRIVER_INPUT_FIELD_MAPPING)


def normalize_ato_command(data: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_fields(data, ATO_COMMAND_FIELD_MAPPING)


def normalize_ma(data: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_fields(data, MA_FIELD_MAPPING)


def normalize_section(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, SECTION_FIELD_MAPPING)
    if "occupied_by" not in normalized and "vehicle_id" in normalized:
        normalized["occupied_by"] = normalized["vehicle_id"]
    if "vehicle_id" not in normalized and "occupied_by" in normalized:
        normalized["vehicle_id"] = normalized["occupied_by"]
    if "aspect" not in normalized:
        normalized["aspect"] = "red" if normalized.get("occupied") else "green"
    return normalized


def normalize_signal(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_fields(data, SIGNAL_FIELD_MAPPING)
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
    return normalize_fields(data, POWER_FIELD_MAPPING)
