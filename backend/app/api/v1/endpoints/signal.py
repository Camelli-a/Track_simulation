"""信号系统接口"""
from fastapi import APIRouter
from app.services.signal_service import SignalService
from app.schemas.signal import SignalStatus

router = APIRouter()
service = SignalService()


@router.get("/status", response_model=SignalStatus, summary="获取信号系统当前状态")
def get_signal_status():
    return service.get_status()


@router.get("/lights", summary="获取所有信号灯状态列表")
def get_all_lights():
    return service.get_all_lights()
