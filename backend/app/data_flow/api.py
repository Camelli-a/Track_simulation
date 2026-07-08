from fastapi import APIRouter

from app.core.config import settings
from app.data_flow.mock_service import mock_dashboard_service
from app.data_flow.schemas import DashboardSnapshot
from app.data_flow.state_store import state_store

router = APIRouter()


@router.get("/snapshot", response_model=DashboardSnapshot, summary="Get dashboard snapshot")
def get_dashboard_snapshot() -> DashboardSnapshot:
    if settings.DATA_SOURCE == "mock":
        mock_dashboard_service.tick()
    return state_store.get_snapshot()

