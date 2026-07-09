from fastapi import APIRouter

from app.core.config import settings
from app.data_flow.message_publisher import publish_module_message
from app.data_flow.mock_service import mock_dashboard_service
from app.data_flow.schemas import (
    DashboardSnapshot,
    RouteRequestCommand,
    VehicleRegistrationCommand,
)
from app.data_flow.state_store import state_store

router = APIRouter()


@router.get("/snapshot", response_model=DashboardSnapshot, summary="Get dashboard snapshot")
def get_dashboard_snapshot() -> DashboardSnapshot:
    if settings.DATA_SOURCE == "mock":
        mock_dashboard_service.tick()
    return state_store.get_snapshot()


@router.post("/publish-track-info", summary="Publish track_info to module message bus")
def publish_track_info() -> dict:
    if settings.DATA_SOURCE == "mock" and not state_store.get_track_info_payload()["sections"]:
        mock_dashboard_service.tick()

    payload = state_store.get_track_info_payload()
    published = publish_module_message("track_info", payload)
    return {
        "accepted": True,
        "published": published,
        "topic": "track_info",
        "section_count": len(payload["sections"]),
    }


@router.post("/vehicles/register", summary="Register vehicle and publish initial state")
def register_vehicle(command: VehicleRegistrationCommand) -> dict:
    payload = command.model_dump(exclude_none=True)
    vehicle_id = state_store.register_vehicle(payload)
    published_register = publish_module_message("vehicle_register", payload)
    published_set_state = publish_module_message("set_train_state", payload)
    return {
        "accepted": vehicle_id is not None,
        "vehicle_id": vehicle_id,
        "published": published_register or published_set_state,
        "topics": {
            "vehicle_register": published_register,
            "set_train_state": published_set_state,
        },
    }


@router.post("/route-request", summary="Publish route request to module message bus")
def publish_route_request(command: RouteRequestCommand) -> dict:
    payload = command.model_dump(exclude_none=True)
    request_key = state_store.update_route_request(payload)
    published = publish_module_message("route_request", payload)
    return {
        "accepted": request_key is not None,
        "published": published,
        "topic": "route_request",
        "request_key": request_key,
    }

