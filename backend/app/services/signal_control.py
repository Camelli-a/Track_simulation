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
from app.services.signal_speed_limit import find_static_speed_limit_with_preview, resolve_speed_limit

ROUTE_EXTENSION_AHEAD_M = 1500.0
LINE_ROUTE_END = max(
    [float(route.get("end", 0.0) or 0.0) for route in ROUTES.values()]
    + [float(section.get("end", 0.0) or 0.0) for section in SECTIONS]
)


@dataclass(frozen=True)
class DemoVehicle:
    vehicle_id: str
    position: float
    speed: float
    route_id: str
    direction_code: int = 1
    train_length: float = DEFAULT_TRAIN_LENGTH
    fault_speed_limit: Optional[float] = None
    emergency_brake: bool = False


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
            direction_code=_normalize_direction_code(
                item.get("direction_code", item.get("direction", 1))
            ),
            train_length=float(item.get("train_length") or DEFAULT_TRAIN_LENGTH),
            fault_speed_limit=(
                float(item["fault_speed_limit"])
                if item.get("fault_speed_limit") is not None
                else None
            ),
            emergency_brake=bool(item.get("emergency_brake", False)),
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
    route = _resolve_route_for_vehicle(vehicle)
    front_vehicle = _find_front_vehicle(vehicle, vehicles)
    direction_sign = _direction_sign(vehicle)
    route_start = float(route["start"])
    route_end = float(route["end"])
    route_boundary = route_end if direction_sign > 0 else route_start

    if front_vehicle:
        front_train_length = front_vehicle.train_length
        protection_distance = (
            front_train_length
            + LOCATION_UNCERTAINTY
            + COMMUNICATION_MARGIN
            + SAFETY_MARGIN
        )
        if direction_sign > 0:
            front_protection_point = front_vehicle.position - protection_distance
            ma_limit = min(front_protection_point, route_boundary)
        else:
            front_protection_point = front_vehicle.position + protection_distance
            ma_limit = max(front_protection_point, route_boundary)
        front_vehicle_id: Optional[str] = front_vehicle.vehicle_id
        reason = "front_vehicle_protection"
    else:
        ma_limit = route_boundary
        front_vehicle_id = None
        front_train_length = None
        front_protection_point = None
        reason = "route_end"

    distance_to_ma = (ma_limit - vehicle.position) * direction_sign
    signal_rule = _resolve_signal_rule(distance_to_ma, route["speed_limit"], vehicle.speed)
    static_limit = find_static_speed_limit_with_preview(
        vehicle.position,
        direction_code=vehicle.direction_code,
        route_speed_limit=route["speed_limit"],
        decel_mps2=SERVICE_BRAKE_DECELERATION,
    )
    speed_limit_rule = resolve_speed_limit(
        permission=signal_rule["permission"],
        route_speed_limit=route["speed_limit"],
        static_speed_limit=static_limit.get("speed_limit") if static_limit else None,
        static_speed_limit_id=static_limit.get("limit_id") if static_limit else None,
        static_speed_limit_preview=bool(static_limit.get("preview")) if static_limit else False,
        upcoming_static_speed_limit=(
            static_limit.get("preview_target_speed_limit") if static_limit else None
        ),
        speed_limit_warning_distance_m=(
            static_limit.get("preview_distance_to_start_m") if static_limit else None
        ),
        fault_speed_limit=vehicle.fault_speed_limit,
        braking_curve_speed_limit=signal_rule["braking_curve_speed_limit"],
        emergency_brake=vehicle.emergency_brake,
    )
    permission = speed_limit_rule.get("permission_override", signal_rule["permission"])
    signal_state = speed_limit_rule.get("signal_state_override", signal_rule["signal_state"])
    speed_limit = speed_limit_rule["speed_limit"]
    if permission == "stop":
        target_speed = 0.0
    else:
        target_speed = min(signal_rule["target_speed"], speed_limit)
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
        "direction_code": vehicle.direction_code,
        "direction": "reverse" if direction_sign < 0 else "forward",
        "ma_limit": round(ma_limit, 1),
        "distance_to_ma": round(distance_to_ma, 1),
        "permission": permission,
        "signal_state": signal_state,
        "speed_limit": speed_limit,
        "target_speed": round(max(target_speed, 0.0), 1),
        "reason": reason,
        "front_vehicle_id": front_vehicle_id,
        "front_train_length": front_train_length,
        "location_uncertainty": LOCATION_UNCERTAINTY,
        "communication_margin": COMMUNICATION_MARGIN,
        "safety_margin": SAFETY_MARGIN,
        "front_protection_point": round(front_protection_point, 1) if front_protection_point is not None else None,
        "safe_distance": protection_margin if front_vehicle else SAFE_DISTANCE,
        "current_speed": vehicle.speed,
        "route_speed_limit": speed_limit_rule["route_speed_limit"],
        "static_speed_limit": speed_limit_rule["static_speed_limit"],
        "static_speed_limit_id": speed_limit_rule["static_speed_limit_id"],
        "static_speed_limit_source": static_limit.get("source") if static_limit else None,
        "static_speed_limit_related_switch_id": (
            static_limit.get("related_switch_id") if static_limit else None
        ),
        "static_speed_limit_preview": speed_limit_rule["static_speed_limit_preview"],
        "upcoming_static_speed_limit": speed_limit_rule["upcoming_static_speed_limit"],
        "speed_limit_warning": speed_limit_rule["speed_limit_reason"] == "static_limit_preview",
        "speed_limit_warning_distance_m": speed_limit_rule["speed_limit_warning_distance_m"],
        "fault_speed_limit": speed_limit_rule["fault_speed_limit"],
        "speed_limit_reason": speed_limit_rule["speed_limit_reason"],
        "required_stop_distance": signal_rule["required_stop_distance"],
        "emergency_stop_distance": signal_rule["emergency_stop_distance"],
        "warning_distance": signal_rule["warning_distance"],
        "braking_curve_speed_limit": speed_limit_rule["braking_curve_speed_limit"],
        "braking_model": "simplified_atp_braking_curve",
    }


def _resolve_route_for_vehicle(vehicle: DemoVehicle) -> dict:
    configured_route = ROUTES.get(vehicle.route_id)
    if vehicle.route_id == DEFAULT_ROUTE_ID:
        return _dynamic_route(vehicle, configured_route or ROUTES[DEFAULT_ROUTE_ID])
    if configured_route is not None and _route_contains_position(configured_route, vehicle.position):
        return configured_route
    if configured_route is None:
        return _dynamic_route(vehicle, ROUTES[DEFAULT_ROUTE_ID])

    containing_routes = [
        route
        for route in ROUTES.values()
        if _route_contains_position(route, vehicle.position)
    ]
    if containing_routes:
        return min(
            containing_routes,
            key=lambda route: (
                abs(float(route["end"]) - float(route["start"])),
                abs(float(route["end"]) - vehicle.position),
            ),
        )

    return _dynamic_route(vehicle, configured_route)


def _dynamic_route(vehicle: DemoVehicle, base_route: dict) -> dict:
    base_start = float(base_route.get("start", 0.0) or 0.0)
    base_end = float(base_route.get("end", base_start) or base_start)
    if _direction_sign(vehicle) < 0:
        dynamic_start = max(0.0, min(base_start, vehicle.position - ROUTE_EXTENSION_AHEAD_M))
        dynamic_end = max(base_end, LINE_ROUTE_END, vehicle.position)
    else:
        dynamic_start = min(base_start, vehicle.position)
        dynamic_end = max(base_end, LINE_ROUTE_END, vehicle.position + ROUTE_EXTENSION_AHEAD_M)
    return {
        **base_route,
        "route_id": vehicle.route_id,
        "start": dynamic_start,
        "end": dynamic_end,
        "speed_limit": float(base_route.get("speed_limit", 80.0) or 80.0),
    }


def _route_contains_position(route: dict, position: float) -> bool:
    start = float(route.get("start", 0.0) or 0.0)
    end = float(route.get("end", start) or start)
    low, high = (start, end) if start <= end else (end, start)
    return low <= float(position) <= high


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
    if _direction_sign(vehicle) < 0:
        front_vehicles = [
            other
            for other in vehicles
            if other.vehicle_id != vehicle.vehicle_id
            and other.route_id == vehicle.route_id
            and other.position < vehicle.position
        ]
        if not front_vehicles:
            return None
        return max(front_vehicles, key=lambda item: item.position)

    front_vehicles = [
        other
        for other in vehicles
        if other.vehicle_id != vehicle.vehicle_id
        and other.route_id == vehicle.route_id
        and other.position > vehicle.position
    ]
    if not front_vehicles:
        return None
    return min(front_vehicles, key=lambda item: item.position)


def _normalize_direction_code(value) -> int:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"reverse", "backward", "down", "-1", "2", "0xaa", "aa"}:
            return -1
        if normalized in {"forward", "up", "1", "0x55", "55"}:
            return 1
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 1
    if numeric in {-1, 2, 0xAA}:
        return -1
    return 1


def _direction_sign(vehicle: DemoVehicle) -> int:
    return -1 if _normalize_direction_code(vehicle.direction_code) < 0 else 1
