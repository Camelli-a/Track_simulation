from fastapi import APIRouter

from app.api.v1.endpoints import driver_desk_sim, power, signal, track, vehicle
from app.data_flow import api as dashboard
from app.data_flow import station_yard_api
from app.speed_curve import router as speed_curve_router

api_router = APIRouter()

api_router.include_router(power.router, prefix="/power", tags=["power"])
api_router.include_router(vehicle.router, prefix="/vehicle", tags=["vehicle"])
api_router.include_router(
    driver_desk_sim.router,
    prefix="/driver-desk-sim",
    tags=["driver-desk-sim"],
)
api_router.include_router(track.router, prefix="/track", tags=["track"])
api_router.include_router(signal.router, prefix="/signal", tags=["signal"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(station_yard_api.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(
    speed_curve_router.router,
    prefix="/speedcurve",
    tags=["speed-curve"],
)

