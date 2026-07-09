from fastapi import APIRouter

from app.data_flow.message_publisher import publish_module_message
from app.data_flow.state_store import state_store
from app.schemas.vehicle import (
    VehicleControlRequest,
    VehicleControlResponse,
    VehicleManagementRequest,
    VehicleManagementResponse,
    VehicleStatus,
)
from app.services.vehicle_service import VehicleService
from app.vehicle_sim.message_router import MessageRouter
from app.vehicle_sim.train_manager import TrainManager

router = APIRouter()
service = VehicleService()
vehicle_manager = TrainManager()
vehicle_message_router = MessageRouter(vehicle_manager)


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


@router.get("/trains", summary="List managed vehicle simulation trains")
def list_vehicle_trains() -> dict:
    return {
        "count": len(vehicle_manager.trains),
        "trains": vehicle_manager.list_trains(),
    }


@router.post("/manage", response_model=VehicleManagementResponse, summary="Manage vehicle simulation trains")
def manage_vehicle(command: VehicleManagementRequest) -> VehicleManagementResponse:
    message = _build_vehicle_management_message(command)
    result = vehicle_message_router.handle(message)
    if result is None:
        result = {"ok": False, "reason": "unsupported_vehicle_management_command"}

    topic = command.type
    published = publish_module_message(topic, _management_publish_payload(message))
    trains = vehicle_manager.list_trains()
    state_store.replace_trains(trains)

    return VehicleManagementResponse(
        ok=bool(result.get("ok", False)),
        published=published,
        topic=topic,
        result=result,
        trains=trains,
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
        traction_level = max(traction_level, command.level)
        brake_level = 0
    elif command.command == "brake":
        traction_level = 0
        brake_level = max(brake_level, command.level, 2)
    elif command.command in {"emergency_stop", "emergency_brake"}:
        traction_level = 0
        brake_level = 4
        emergency_button = True

    return "driver_input", {
        "vehicle_id": command.vehicle_id,
        "line_id": command.line_id,
        "source": "frontend",
        "command_source": command.source,
        "control_mode": "manual",
        "traction_level": traction_level,
        "brake_level": brake_level,
        "direction": command.direction,
        "emergency_button": emergency_button,
    }


def _management_publish_payload(message: dict) -> dict:
    return {
        key: value
        for key, value in message.items()
        if key not in {"type"}
    }


def _build_vehicle_management_message(command: VehicleManagementRequest) -> dict:
    if command.type == "add_train":
        message = {
            "type": command.type,
            "line_id": command.line_id,
            "position": command.position,
        }
        if command.vehicle_id is not None:
            message["vehicle_id"] = command.vehicle_id
        if command.train_index is not None:
            message["train_index"] = command.train_index
        return message

    if command.type == "remove_train":
        message = {"type": command.type}
        if command.vehicle_id is not None:
            message["vehicle_id"] = command.vehicle_id
        if command.train_index is not None:
            message["train_index"] = command.train_index
        return message

    if command.type == "reset_trains":
        return {
            "type": command.type,
            "count": 10 if command.count is None else command.count,
        }

    return {"type": command.type}
