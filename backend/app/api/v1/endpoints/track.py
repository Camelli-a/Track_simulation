"""轨道仿真接口"""
from fastapi import APIRouter
from app.services.track_service import TrackService
from app.schemas.track import TrackStatus

router = APIRouter()
service = TrackService()


@router.get("/status", response_model=TrackStatus, summary="获取轨道系统当前状态")
def get_track_status():
    return service.get_status()


@router.get("/segments", summary="获取所有轨道分段信息")
def get_track_segments():
    return service.get_segments()
