from fastapi import APIRouter
from app.api.v1.endpoints import power, vehicle, track, signal

api_router = APIRouter()

# 供电仿真
api_router.include_router(power.router,   prefix="/power",   tags=["供电仿真"])
# 车辆仿真
api_router.include_router(vehicle.router, prefix="/vehicle", tags=["车辆仿真"])
# 轨道仿真
api_router.include_router(track.router,   prefix="/track",   tags=["轨道仿真"])
# 信号系统
api_router.include_router(signal.router,  prefix="/signal",  tags=["信号系统"])
