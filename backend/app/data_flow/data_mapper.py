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


def normalize_power(data: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_fields(data, POWER_FIELD_MAPPING)

