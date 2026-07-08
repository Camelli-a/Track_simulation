import math
from dataclasses import dataclass
from typing import List, Optional

from app.services.signal_track_config import (
    BRAKING_SAFETY_MARGIN,
    COMMUNICATION_MARGIN,
    DEFAULT_TRAIN_LENGTH,
    DEFAULT_ROUTE_ID,
    EMERGENCY_BRAKE_DECELERATION,
    LOCATION_UNCERTAINTY,
    REACTION_TIME,
    ROUTES,
    SAFE_DISTANCE,
    SAFETY_MARGIN,
    SECTIONS,
    SERVICE_BRAKE_DECELERATION,
    SWITCHES,
    WARNING_MARGIN,
)


@dataclass(frozen=True)
class DemoVehicle:
    vehicle_id: str
    position: float
    speed: float
    route_id: str
    train_length: float = DEFAULT_TRAIN_LENGTH


def calculate_signal_snapshot(
    train_states: list[dict],
    route_requests: list[dict] | None = None,
) -> dict:
    vehicles = _normalize_train_states(train_states)
    sections = _calculate_sections(vehicles)
    ma_limits = [_calculate_ma_limit(vehicle, vehicles) for vehicle in vehicles]
    signals = _calculate_signals(ma_limits)
    route_results = _calculate_route_results(route_requests or [])
    lights = [
        {
            "signal_id": signal["signal_id"],
            "position": signal["position"],
            "state": signal["signal_state"],
        }
        for signal in signals
    ]

    return {
        "lights": lights,
        "signals": signals,
        "sections": sections,
        "switches": [_switch_status(switch) for switch in SWITCHES],
        "ma_limits": ma_limits,
        "route_results": route_results,
    }


def build_signal_state_message(snapshot: dict) -> dict:
    return {
        "type": "signal_state",
        "timestamp": snapshot.get("timestamp"),
        "system_mode": snapshot.get("system_mode", "normal"),
        "signals": snapshot.get("signals", []),
        "sections": snapshot.get("sections", []),
        "switches": snapshot.get("switches", []),
        "route_results": snapshot.get("route_results", []),
    }


def build_ma_state_message(snapshot: dict) -> dict:
    return {
        "type": "ma_state",
        "timestamp": snapshot.get("timestamp"),
        "ma_limits": snapshot.get("ma_limits", []),
    }


def calculate_signal_status(vehicles: List[DemoVehicle]) -> dict:
    train_states = [
        {
            "vehicle_id": vehicle.vehicle_id,
            "position": vehicle.position,
            "speed": vehicle.speed,
            "route_id": vehicle.route_id,
            "train_length": vehicle.train_length,
        }
        for vehicle in vehicles
    ]
    return calculate_signal_snapshot(train_states)


def _normalize_train_states(train_states: list[dict]) -> List[DemoVehicle]:
    return [
        DemoVehicle(
            vehicle_id=str(item["vehicle_id"]),
            position=float(item["position"]),
            speed=float(item["speed"]),
            route_id=str(item["route_id"]),
            train_length=float(item.get("train_length") or DEFAULT_TRAIN_LENGTH),
        )
        for item in train_states
    ]


def _calculate_sections(vehicles: List[DemoVehicle]) -> List[dict]:
    sections = []
    for section in SECTIONS:
        occupying_vehicle = _find_vehicle_in_section(vehicles, section["start"], section["end"])
        sections.append(
            {
                **section,
                "occupied": occupying_vehicle is not None,
                "vehicle_id": occupying_vehicle.vehicle_id if occupying_vehicle else None,
                "locked": occupying_vehicle is not None,
                "locked_by_route_id": occupying_vehicle.route_id if occupying_vehicle else None,
                "condition": "normal",
            }
        )
    return sections


def _calculate_ma_limit(vehicle: DemoVehicle, vehicles: List[DemoVehicle]) -> dict:
    route = ROUTES.get(vehicle.route_id, ROUTES[DEFAULT_ROUTE_ID])
    front_vehicle = _find_front_vehicle(vehicle, vehicles)
    route_end = route["end"]

    if front_vehicle:
        front_train_length = front_vehicle.train_length
        front_protection_point = (
            front_vehicle.position
            - front_train_length
            - LOCATION_UNCERTAINTY
            - COMMUNICATION_MARGIN
            - SAFETY_MARGIN
        )
        ma_limit = min(front_protection_point, route_end)
        front_vehicle_id: Optional[str] = front_vehicle.vehicle_id
        reason = "front_vehicle_protection"
    else:
        ma_limit = route_end
        front_vehicle_id = None
        front_train_length = None
        front_protection_point = None
        reason = "route_end"

    distance_to_ma = ma_limit - vehicle.position
    signal_rule = _resolve_signal_rule(distance_to_ma, route["speed_limit"], vehicle.speed)
    protection_margin = (
        (front_train_length or 0.0)
        + LOCATION_UNCERTAINTY
        + COMMUNICATION_MARGIN
        + SAFETY_MARGIN
    )

    return {
        "vehicle_id": vehicle.vehicle_id,
        "position": vehicle.position,
        "route_id": vehicle.route_id,
        "ma_limit": round(ma_limit, 1),
        "distance_to_ma": round(distance_to_ma, 1),
        "permission": signal_rule["permission"],
        "signal_state": signal_rule["signal_state"],
        "speed_limit": signal_rule["speed_limit"],
        "target_speed": signal_rule["target_speed"],
        "reason": reason,
        "front_vehicle_id": front_vehicle_id,
        "front_train_length": front_train_length,
        "location_uncertainty": LOCATION_UNCERTAINTY,
        "communication_margin": COMMUNICATION_MARGIN,
        "safety_margin": SAFETY_MARGIN,
        "front_protection_point": round(front_protection_point, 1) if front_protection_point is not None else None,
        "safe_distance": protection_margin if front_vehicle else SAFE_DISTANCE,
        "current_speed": vehicle.speed,
        "route_speed_limit": route["speed_limit"],
        "required_stop_distance": signal_rule["required_stop_distance"],
        "emergency_stop_distance": signal_rule["emergency_stop_distance"],
        "warning_distance": signal_rule["warning_distance"],
        "braking_curve_speed_limit": signal_rule["braking_curve_speed_limit"],
        "braking_model": "simplified_atp_braking_curve",
    }


def _calculate_signals(ma_limits: List[dict]) -> List[dict]:
    return [
        {
            "signal_id": f"SIG-{index:02d}",
            "position": item["position"],
            "state": item["signal_state"],
            "route_id": item["route_id"],
            "signal_state": item["signal_state"],
            "permission": item["permission"],
        }
        for index, item in enumerate(ma_limits, start=1)
    ]


def _calculate_route_results(route_requests: list[dict]) -> List[dict]:
    return [_calculate_route_result(request) for request in route_requests]


def _calculate_route_result(route_request: dict) -> dict:
    vehicle_id = str(route_request["vehicle_id"])
    route_id = str(route_request["route_id"])
    route = ROUTES.get(route_id, ROUTES[DEFAULT_ROUTE_ID])
    required_switch = _first_required_switch(route)
    switch = _switch_by_id(required_switch["switch_id"])
    required_position = required_switch["required_position"]
    current_position = switch["position"]
    locked_by_route_id = switch["locked_by_route_id"]
    switch_conflict = (
        switch["locked"]
        and locked_by_route_id != route_id
        and current_position != required_position
    )

    return {
        "vehicle_id": vehicle_id,
        "route_id": route_id,
        "allowed": not switch_conflict,
        "reason": "switch_locked_conflict" if switch_conflict else "route_available",
        "required_switch_id": switch["switch_id"],
        "required_position": required_position,
        "current_position": current_position,
        "locked_by_route_id": locked_by_route_id,
    }


def _first_required_switch(route: dict) -> dict:
    required_switches = route.get("required_switches", [])
    if required_switches:
        return required_switches[0]
    return {
        "switch_id": SWITCHES[0]["switch_id"],
        "required_position": SWITCHES[0]["position"],
    }


def _switch_by_id(switch_id: str) -> dict:
    for switch in SWITCHES:
        if switch["switch_id"] == switch_id:
            return switch
    return SWITCHES[0]


def _switch_status(switch: dict) -> dict:
    return {
        "switch_id": switch["switch_id"],
        "position": switch["position"],
        "locked": switch["locked"],
        "locked_by_route_id": switch["locked_by_route_id"],
        "related_section": switch["related_section"],
        "reason": switch["reason"],
    }


def _resolve_signal_rule(distance_to_ma: float, route_speed_limit: float, current_speed: float) -> dict:
    required_stop_distance = _stop_distance(current_speed, SERVICE_BRAKE_DECELERATION)
    emergency_stop_distance = _stop_distance(current_speed, EMERGENCY_BRAKE_DECELERATION)
    warning_distance = required_stop_distance + WARNING_MARGIN
    braking_curve_speed_limit = _braking_curve_speed_limit(distance_to_ma)

    if distance_to_ma <= emergency_stop_distance:
        permission = "stop"
        signal_state = "red"
        speed_limit = 0.0
        target_speed = 0.0
    elif distance_to_ma <= warning_distance:
        permission = "restricted"
        signal_state = "yellow"
        speed_limit = min(route_speed_limit, braking_curve_speed_limit)
        target_speed = speed_limit
    else:
        permission = "allow"
        signal_state = "green"
        speed_limit = route_speed_limit
        target_speed = min(current_speed, route_speed_limit)

    return {
        "permission": permission,
        "signal_state": signal_state,
        "speed_limit": round(max(speed_limit, 0.0), 1),
        "target_speed": round(max(target_speed, 0.0), 1),
        "required_stop_distance": round(required_stop_distance, 1),
        "emergency_stop_distance": round(emergency_stop_distance, 1),
        "warning_distance": round(warning_distance, 1),
        "braking_curve_speed_limit": round(braking_curve_speed_limit, 1),
    }


def _stop_distance(speed_kmh: float, deceleration: float) -> float:
    speed_mps = max(speed_kmh, 0.0) / 3.6
    return (
        speed_mps * REACTION_TIME
        + speed_mps**2 / (2 * deceleration)
        + BRAKING_SAFETY_MARGIN
    )


def _braking_curve_speed_limit(distance_to_ma: float) -> float:
    available_distance = distance_to_ma - BRAKING_SAFETY_MARGIN
    if available_distance <= 0:
        return 0.0

    v_allowed_mps = (
        -SERVICE_BRAKE_DECELERATION * REACTION_TIME
        + math.sqrt(
            (SERVICE_BRAKE_DECELERATION * REACTION_TIME) ** 2
            + 2 * SERVICE_BRAKE_DECELERATION * available_distance
        )
    )
    return max(v_allowed_mps, 0.0) * 3.6


def _find_vehicle_in_section(
    vehicles: List[DemoVehicle],
    start: float,
    end: float,
) -> Optional[DemoVehicle]:
    for vehicle in vehicles:
        if start <= vehicle.position < end:
            return vehicle
    return None


def _find_front_vehicle(vehicle: DemoVehicle, vehicles: List[DemoVehicle]) -> Optional[DemoVehicle]:
    front_vehicles = [
        other
        for other in vehicles
        if other.route_id == vehicle.route_id and other.position > vehicle.position
    ]
    if not front_vehicles:
        return None
    return min(front_vehicles, key=lambda item: item.position)
