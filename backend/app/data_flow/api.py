from fastapi import APIRouter

from app.core.config import settings
from app.data_flow.message_publisher import publish_module_message
from app.data_flow.mock_service import mock_dashboard_service
from app.data_flow.schemas import DashboardSnapshot
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
