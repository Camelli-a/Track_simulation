"""供电仿真接口"""
from fastapi import APIRouter
from app.services.power_service import PowerService
from app.schemas.power import PowerStatus

router = APIRouter()
service = PowerService()


@router.get("/status", response_model=PowerStatus, summary="获取供电系统当前状态")
def get_power_status():
    return service.get_status()


@router.get("/history", summary="获取供电历史数据（供图表渲染）")
def get_power_history(limit: int = 100):
    return service.get_history(limit)
