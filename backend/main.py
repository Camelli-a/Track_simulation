"""
FastAPI application entry point.

DATA_SOURCE=zmq (default):
    Full pipeline is active — Train physics + ATO, PLC TCP link, ZMQ bus,
    speed-curve recorder, and dashboard WebSocket all run together.

    Data flow:
      PLC ──TCP 46B/100ms──► DriverDeskSource
                                  │ publish("driver_input")
                                  ▼
                             ZMQ MessageBus ◄── SimulationLoop publishes train_state
                                  │
                      ┌───────────┼───────────────────┐
                      ▼           ▼                   ▼
              MessageRouter  ZmqDashboardListener  PlcFeedbackAggregator
              (Train.step_   (state_store +        (build_snapshot →
               manual)        SpeedCurve)           send_to_plc)
                                                        │
                                             TCP 28B/100ms──► PLC

DATA_SOURCE=mock:
    Only mock_dashboard_service ticks; no simulation loop, no PLC connection.
    Useful for front-end-only demos.
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.communication.broker_manager import broker_process_manager
from app.core.config import settings
from app.data_flow.websocket import router as dashboard_ws_router
from app.data_flow.zmq_listener import zmq_dashboard_listener
from app.services.line_operation_service import line_operation_service
from app.services.signal_zmq_adapter import SignalZmqAdapter
from app.services.station_demo_service import station_demo_service
from app.speed_curve.websocket_router import router as speed_curve_ws_router
from app.vehicle_sim.process_manager import vehicle_process_manager

logger = logging.getLogger(__name__)

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Speed-curve recorder hook (always on) ─────────────────────────
    from app.speed_curve.zmq_listener import attach_to_zmq_listener
    attach_to_zmq_listener()

    if settings.ENABLE_ZMQ_BROKER_MANAGER:
        broker_process_manager.start()
    if settings.ENABLE_ZMQ_DASHBOARD_LISTENER:
        zmq_dashboard_listener.start()
    signal_adapter = SignalZmqAdapter() if settings.ENABLE_SIGNAL_ZMQ_ADAPTER else None
    if signal_adapter is not None:
        signal_adapter.start()

    async def _stop_common() -> None:
        await line_operation_service.stop()
        await station_demo_service.stop()
        vehicle_process_manager.stop_all()
        if signal_adapter is not None:
            signal_adapter.stop()
        if settings.ENABLE_ZMQ_DASHBOARD_LISTENER:
            await zmq_dashboard_listener.stop()
        if settings.ENABLE_ZMQ_BROKER_MANAGER:
            broker_process_manager.stop()

    if settings.DATA_SOURCE != "zmq":
        # mock mode: nothing else to start
        logger.info("DATA_SOURCE=%s — simulation loop and PLC disabled", settings.DATA_SOURCE)
        try:
            yield
        finally:
            await _stop_common()
        return

    # ══════════════════════════════════════════════════════════════════
    # ZMQ mode: full pipeline (physical PLC driver desk for TRAIN-001)
    # ══════════════════════════════════════════════════════════════════

    # Shared ZMQ bus — used by DriverDeskSource, SimulationLoop, etc.
    from app.communication.message_bus import MessageBus
    bus = MessageBus()
    bus.start()

    # Singleton TrainManager + MessageRouter (defined in vehicle endpoint)
    from app.api.v1.endpoints.vehicle import vehicle_manager, vehicle_message_router

    # DriverDeskSource — connects to the physical PLC via TCP.
    #    Retries automatically if the PLC is not reachable (no crash).
    #    Publishes driver_input and comm_state onto `bus`.
    from app.communication.driver_desk_source import DriverDeskSource
    plc_source = DriverDeskSource(
        vehicle_id="TRAIN-001",
        plc_host=settings.PLC_HOST,
        plc_port=settings.PLC_PORT,
        bus=bus,
        record_dir="logs",
        record_raw=True,
    )

    # PlcFeedbackAggregator — subscribes to train_state on `bus` and
    #    calls send_to_plc() every 100 ms so the cab display stays in sync.
    from app.communication.plc_feedback_aggregator import PlcFeedbackAggregator
    plc_aggregator = PlcFeedbackAggregator(
        send_to_plc=plc_source.send_to_plc,
        interval_sec=0.1,
        comm_timeout_sec=0.5,
    )
    plc_aggregator.attach(bus)

    # Route PLC driver_input into the vehicle simulation.
    def _on_driver_input(topic: str, data: dict) -> None:
        data.setdefault("source", "driver_tcp")
        vehicle_message_router.handle({"type": "driver_input", **data})

    def _on_comm_state(topic: str, data: dict) -> None:
        vehicle_message_router.handle({"type": "comm_state", **data})

    bus.subscribe("driver_input", _on_driver_input)
    bus.subscribe("comm_state", _on_comm_state)

    # Simulation loop — ticks every 100 ms, publishes train_state.
    from app.vehicle_sim.simulation_loop import SimulationLoop
    sim_loop = SimulationLoop(
        vehicle_manager,
        plc_aggregator=plc_aggregator,
        zmq_bus=bus,
    )

    # Start everything
    plc_source.start()
    plc_aggregator.start()
    sim_loop.start()

    logger.info(
        "Full pipeline started — PLC=%s:%s  ZMQ=%s",
        settings.PLC_HOST, settings.PLC_PORT,
        settings.ZMQ_BROKER_FRONTEND,
    )

    try:
        yield
    finally:
        await sim_loop.stop()
        plc_aggregator.stop()
        plc_source.stop()
        bus.stop()
        await _stop_common()
        logger.info("Full pipeline stopped")


app = FastAPI(
    title="Track Simulation API",
    description="Power / vehicle / track / signal simulation backend API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(dashboard_ws_router)
app.include_router(speed_curve_ws_router)
app.mount("/data", StaticFiles(directory=Path(__file__).parent / "data"), name="data")


@app.get("/", tags=["health"])
def health_check():
    return {
        "status": "ok",
        "data_source": settings.DATA_SOURCE,
        "enable_dashboard_mock": settings.ENABLE_DASHBOARD_MOCK,
        "enable_zmq_broker_manager": settings.ENABLE_ZMQ_BROKER_MANAGER,
        "enable_zmq_dashboard_listener": settings.ENABLE_ZMQ_DASHBOARD_LISTENER,
        "enable_vehicle_process_manager": settings.ENABLE_VEHICLE_PROCESS_MANAGER,
    }
