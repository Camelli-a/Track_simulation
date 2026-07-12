import logging

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
logger = logging.getLogger("uvicorn.error")


@router.get("/status", response_model=VehicleStatus, summary="Get current vehicle status")
def get_vehicle_status():
    status = service.get_status()
    logger.info(
        "Vehicle status requested: vehicle_id=%s position=%.2f speed=%.2f",
        status.vehicle_id,
        status.position,
        status.speed,
    )
    return status


@router.get("/history", summary="Get vehicle trajectory history")
def get_vehicle_history(limit: int = 100):
    history = service.get_history(limit)
    logger.info("Vehicle history requested: limit=%s returned=%s", limit, len(history))
    return history


@router.post("/control", response_model=VehicleControlResponse, summary="Send vehicle control command")
def control_vehicle(command: VehicleControlRequest) -> VehicleControlResponse:
    topic, message = _build_vehicle_control_message(command)
    published = publish_module_message(topic, message)

    if topic == "ato_command":
        state_store.update_ato_command(command.vehicle_id, message)
    else:
        state_store.update_driver_input(command.vehicle_id, message)

    logger.info(
        "Vehicle control: vehicle_id=%s command=%s topic=%s traction=%s brake=%s direction=%s published=%s",
        command.vehicle_id,
        command.command,
        topic,
        message.get("traction_level"),
        message.get("brake_level"),
        message.get("direction"),
        published,
    )
    return VehicleControlResponse(
        published=published,
        topic=topic,
        message=message,
    )


@router.get("/trains", summary="List managed vehicle simulation trains")
def list_vehicle_trains() -> dict:
    logger.info("Vehicle trains listed: count=%s", len(vehicle_manager.trains))
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

    logger.info(
        "Vehicle management: type=%s vehicle_id=%s train_index=%s ok=%s published=%s active_trains=%s",
        command.type,
        command.vehicle_id,
        command.train_index,
        result.get("ok", False),
        published,
        len(trains),
    )
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
            "traction_percent": command.traction_percent,
            "brake_percent": command.brake_percent,
            "reason": command.reason,
        }

    traction_level = command.traction_level
    brake_level = command.brake_level
    traction_percent = command.traction_percent
    brake_percent = command.brake_percent
    emergency_button = False

    if command.command == "traction":
        traction_level = max(traction_level, command.level)
        brake_level = 0
        traction_percent = traction_percent or traction_level / 4 * 100.0
        brake_percent = 0.0
    elif command.command == "brake":
        traction_level = 0
        brake_level = max(brake_level, command.level, 2)
        traction_percent = 0.0
        brake_percent = brake_percent or brake_level / 7 * 100.0
    elif command.command in {"emergency_stop", "emergency_brake"}:
        traction_level = 0
        brake_level = 4
        traction_percent = 0.0
        brake_percent = 100.0
        emergency_button = True
    elif brake_level > 0:
        traction_level = 0
        traction_percent = 0.0
        brake_percent = brake_percent or brake_level / 7 * 100.0
    elif traction_level > 0:
        traction_percent = traction_percent or traction_level / 4 * 100.0

    return "driver_input", {
        "vehicle_id": command.vehicle_id,
        "line_id": command.line_id,
        "source": "frontend",
        "command_source": command.source,
        "control_mode": "manual",
        "traction_level": traction_level,
        "brake_level": brake_level,
        "traction_percent": traction_percent,
        "brake_percent": brake_percent,
        "main_handle_raw": command.main_handle_raw,
        "key_switch": command.key_switch,
        "direction": command.direction,
        "emergency_button": emergency_button,
        "open_left_door": command.open_left_door,
        "open_right_door": command.open_right_door,
        "close_left_door": command.close_left_door,
        "close_right_door": command.close_right_door,
        "door_mode": command.door_mode,
        "door_closed_light": command.door_closed_light,
        "high_voltage_light": command.high_voltage_light,
        "brake_bad_light": command.brake_bad_light,
        "network_fault_light": command.network_fault_light,
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
