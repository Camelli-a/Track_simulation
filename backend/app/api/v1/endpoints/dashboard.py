"""GET /api/v1/dashboard/snapshot — 协议 v1.0 REST 调试接口。"""
from fastapi import APIRouter

from app.schemas.dashboard import DashboardSnapshot
from app.services.simulation_service import simulation_service

router = APIRouter()


@router.get("/snapshot", response_model=DashboardSnapshot)
def get_dashboard_snapshot() -> DashboardSnapshot:
    return simulation_service.next_dashboard_snapshot()
