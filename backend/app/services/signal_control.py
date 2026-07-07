from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DemoVehicle:
    vehicle_id: str
    position: float
    speed: float
    route_id: str


@dataclass(frozen=True)
class DemoRoute:
    route_id: str
    start: float
    end: float
    speed_limit: float
    required_switch_position: str


DEMO_SECTIONS = [
    {"section_id": f"SEG-{index:02d}", "start": (index - 1) * 500.0, "end": index * 500.0}
    for index in range(1, 6)
]

DEMO_SWITCH = {
    "switch_id": "SW-01",
    "position": "normal",
    "locked": True,
    "locked_by_route_id": "R_MAIN",
    "related_section": "SEG-03",
    "reason": "route_locked",
}

DEMO_ROUTES: Dict[str, DemoRoute] = {
    "R_MAIN": DemoRoute(
        route_id="R_MAIN",
        start=0.0,
        end=2500.0,
        speed_limit=80.0,
        required_switch_position="normal",
    ),
    "R_BRANCH": DemoRoute(
        route_id="R_BRANCH",
        start=1000.0,
        end=1800.0,
        speed_limit=45.0,
        required_switch_position="reverse",
    ),
}

SAFE_DISTANCE = 120.0


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
        "switches": [DEMO_SWITCH],
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
        )
        for item in train_states
    ]


def _calculate_sections(vehicles: List[DemoVehicle]) -> List[dict]:
    sections = []
    for section in DEMO_SECTIONS:
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
    route = DEMO_ROUTES.get(vehicle.route_id, DEMO_ROUTES["R_MAIN"])
    front_vehicle = _find_front_vehicle(vehicle, vehicles)

    if front_vehicle:
        ma_limit = max(route.start, front_vehicle.position - SAFE_DISTANCE)
        front_vehicle_id: Optional[str] = front_vehicle.vehicle_id
        reason = "front_vehicle_protection"
    else:
        ma_limit = route.end
        front_vehicle_id = None
        reason = "route_end"

    distance_to_ma = ma_limit - vehicle.position
    permission, signal_state, speed_limit = _resolve_signal_rule(distance_to_ma, route.speed_limit)

    return {
        "vehicle_id": vehicle.vehicle_id,
        "position": vehicle.position,
        "route_id": vehicle.route_id,
        "ma_limit": round(ma_limit, 1),
        "permission": permission,
        "signal_state": signal_state,
        "speed_limit": speed_limit,
        "target_speed": min(vehicle.speed, speed_limit),
        "reason": reason,
        "front_vehicle_id": front_vehicle_id,
        "safe_distance": SAFE_DISTANCE,
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
    route = DEMO_ROUTES.get(route_id, DEMO_ROUTES["R_MAIN"])
    required_position = route.required_switch_position
    current_position = DEMO_SWITCH["position"]
    locked_by_route_id = DEMO_SWITCH["locked_by_route_id"]
    switch_conflict = (
        DEMO_SWITCH["locked"]
        and locked_by_route_id != route_id
        and current_position != required_position
    )

    return {
        "vehicle_id": vehicle_id,
        "route_id": route_id,
        "allowed": not switch_conflict,
        "reason": "switch_locked_conflict" if switch_conflict else "route_available",
        "required_switch_id": DEMO_SWITCH["switch_id"],
        "required_position": required_position,
        "current_position": current_position,
        "locked_by_route_id": locked_by_route_id,
    }


def _resolve_signal_rule(distance_to_ma: float, route_speed_limit: float):
    if distance_to_ma <= 80.0:
        return "stop", "red", 0.0
    if distance_to_ma <= 200.0:
        return "restricted", "yellow", 30.0
    return "allow", "green", route_speed_limit


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
