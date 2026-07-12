from fastapi import APIRouter

from app.api.v1.endpoints import power, signal, track, vehicle
from app.data_flow import api as dashboard

api_router = APIRouter()

api_router.include_router(power.router, prefix="/power", tags=["power"])
api_router.include_router(vehicle.router, prefix="/vehicle", tags=["vehicle"])
api_router.include_router(track.router, prefix="/track", tags=["track"])
api_router.include_router(signal.router, prefix="/signal", tags=["signal"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

