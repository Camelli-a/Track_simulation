from fastapi import APIRouter, HTTPException

from app.communication.driver_desk_test_rig import driver_desk_test_rig
from app.schemas.driver_desk_sim import (
    DriverDeskSimInputUpdateRequest,
    DriverDeskSimPulseRequest,
    DriverDeskSimStartRequest,
)

router = APIRouter()


@router.get("/status", summary="Get driver-desk protocol simulator status")
def get_driver_desk_sim_status() -> dict:
    return driver_desk_test_rig.snapshot()


@router.post("/start", summary="Start local driver-desk protocol simulator and backend bridge")
def start_driver_desk_sim(command: DriverDeskSimStartRequest) -> dict:
    try:
        return driver_desk_test_rig.start(
            vehicle_id=command.vehicle_id,
            simulator_host=command.simulator_host,
            simulator_port=command.simulator_port,
            pulse_width_ms=command.pulse_width_ms,
        )
    except OSError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/stop", summary="Stop local driver-desk protocol simulator and backend bridge")
def stop_driver_desk_sim() -> dict:
    return driver_desk_test_rig.stop()


@router.patch("/input", summary="Update sustained driver-desk simulator inputs")
def update_driver_desk_sim_input(command: DriverDeskSimInputUpdateRequest) -> dict:
    try:
        return driver_desk_test_rig.update_input(command.updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/pulse", summary="Pulse one momentary driver-desk simulator input")
def pulse_driver_desk_sim_input(command: DriverDeskSimPulseRequest) -> dict:
    try:
        return driver_desk_test_rig.pulse(command.field_name, command.duration_ms)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
