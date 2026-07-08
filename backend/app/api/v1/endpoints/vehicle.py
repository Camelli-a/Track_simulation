from fastapi import APIRouter

from app.data_flow.message_publisher import publish_module_message
from app.data_flow.state_store import state_store
from app.schemas.vehicle import (
    VehicleControlRequest,
    VehicleControlResponse,
    VehicleStatus,
)
from app.services.vehicle_service import VehicleService

router = APIRouter()
service = VehicleService()


@router.get("/status", response_model=VehicleStatus, summary="Get current vehicle status")
def get_vehicle_status():
    return service.get_status()


@router.get("/history", summary="Get vehicle trajectory history")
def get_vehicle_history(limit: int = 100):
    return service.get_history(limit)


@router.post("/control", response_model=VehicleControlResponse, summary="Send vehicle control command")
def control_vehicle(command: VehicleControlRequest) -> VehicleControlResponse:
    topic, message = _build_vehicle_control_message(command)
    published = publish_module_message(topic, message)

    if topic == "ato_command":
        state_store.update_ato_command(command.vehicle_id, message)
    else:
        state_store.update_driver_input(command.vehicle_id, message)

    return VehicleControlResponse(
        published=published,
        topic=topic,
        message=message,
    )


def _build_vehicle_control_message(command: VehicleControlRequest) -> tuple[str, dict]:
    if command.command == "ato":
        return "ato_command", {
            "vehicle_id": command.vehicle_id,
            "line_id": command.line_id,
            "control_mode": "ato",
            "target_speed": float(command.target_speed or 0.0),
            "target_position": command.target_position,
            "traction_level": command.traction_level,
            "brake_level": command.brake_level,
            "reason": command.reason,
        }

    traction_level = command.traction_level
    brake_level = command.brake_level
    emergency_button = False

    if command.command == "traction":
        brake_level = 0
    elif command.command == "brake":
        traction_level = 0
        brake_level = max(brake_level, 2)
    elif command.command == "emergency_stop":
        traction_level = 0
        brake_level = 4
        emergency_button = True

    return "driver_input", {
        "vehicle_id": command.vehicle_id,
        "line_id": command.line_id,
        "source": "frontend",
        "control_mode": "manual",
        "traction_level": traction_level,
        "brake_level": brake_level,
        "direction": command.direction,
        "emergency_button": emergency_button,
    }
