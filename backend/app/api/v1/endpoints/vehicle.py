"""车辆仿真接口"""
from fastapi import APIRouter
from app.services.vehicle_service import VehicleService
from app.schemas.vehicle import VehicleStatus

router = APIRouter()
service = VehicleService()


@router.get("/status", response_model=VehicleStatus, summary="获取车辆当前状态")
def get_vehicle_status():
    return service.get_status()


@router.get("/history", summary="获取车辆历史轨迹数据（供图表渲染）")
def get_vehicle_history(limit: int = 100):
    return service.get_history(limit)
